using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Endpoints;

public static class EnrollmentEndpoints
{
    private const int  CodeLifetimeMinutes  = 30;
    private const int  ApiKeyByteLength     = 32;     // 64 hex
    private const int  SendIntervalMs       = 5000;
    private const int  CodeDigits           = 6;

    public static void MapEnrollmentEndpoints(this IEndpointRouteBuilder app)
    {
        // Со стороны устройства (без авторизации, тело подтверждает владение)
        app.MapPost("/api/devices/enroll", HandleEnroll);

        // Со стороны админ-веба (JWT)
        app.MapPost  ("/api/enrollment-codes",        CreateCode) .RequireAuthorization("admin");
        app.MapGet   ("/api/enrollment-codes",        ListCodes)  .RequireAuthorization("admin");
        app.MapDelete("/api/enrollment-codes/{id:int}", RevokeCode).RequireAuthorization("admin");
    }

    public record EnrollRequest(string SerialNumber, string DeviceSecret, string EnrollCode);

    private static async Task<IResult> HandleEnroll(
        EnrollRequest req, AppDbContext db, HttpContext ctx, ILoggerFactory loggerFactory)
    {
        var log = loggerFactory.CreateLogger("Enroll");

        if (string.IsNullOrWhiteSpace(req.SerialNumber) ||
            string.IsNullOrWhiteSpace(req.DeviceSecret) ||
            string.IsNullOrWhiteSpace(req.EnrollCode))
            return Results.BadRequest(new { error = "missing_fields" });

        var tenantCtx = ctx.GetTenantContext();
        if (tenantCtx.RequestedSubdomain is not null && !tenantCtx.HasTenant)
            return Results.NotFound(new { error = "unknown_subdomain" });

        var device = await db.Devices.FirstOrDefaultAsync(d => d.SerialNumber == req.SerialNumber);
        if (device is null)
        {
            log.LogWarning("enroll unknown_device {Serial}", req.SerialNumber);
            return Results.NotFound(new { error = "unknown_device" });
        }

        var presentedSecret = DbSeeder.Sha256Hex(req.DeviceSecret);
        if (!FixedTimeEquals(presentedSecret, device.SecretHash))
        {
            log.LogWarning("enroll invalid_secret {Serial}", req.SerialNumber);
            return Results.Json(new { error = "invalid_secret" }, statusCode: 403);
        }

        if (device.Status == DeviceStatus.Deactivated)
            return Results.Json(new { error = "deactivated" }, statusCode: 410);

        if (device.Status != DeviceStatus.Manufactured)
            return Results.Conflict(new { error = "already_claimed" });

        // Если устройство уже принадлежит какому-то tenant'у — enroll возможен только на его поддомене
        if (device.TenantId is not null && device.TenantId != tenantCtx.TenantId)
            return Results.Json(new { error = "wrong_tenant" }, statusCode: 403);

        var codeHash = DbSeeder.Sha256Hex(req.EnrollCode.Trim());
        var now = DateTime.UtcNow;
        var code = await db.EnrollmentCodes
            .FirstOrDefaultAsync(c =>
                c.CodeHash == codeHash &&
                c.UsedAt == null &&
                c.ExpiresAt > now &&
                c.TenantId == tenantCtx.TenantId);   // код привязан к тенанту хоста

        if (code is null)
            return Results.BadRequest(new { error = "invalid_code" });

        var apiKey = GenerateApiKey();
        device.ApiKey    = apiKey;
        device.Status    = DeviceStatus.Active;
        device.ClaimedAt = now;
        device.TenantId  = tenantCtx.TenantId;        // привязали к тенанту

        code.UsedAt         = now;
        code.UsedByDeviceId = device.Id;

        await db.SaveChangesAsync();

        var backendUrl = $"{ctx.Request.Scheme}://{ctx.Request.Host}";
        log.LogInformation("enroll success {Serial} → device {Id}", req.SerialNumber, device.Id);

        return Results.Ok(new
        {
            apiKey,
            backendUrl,
            sendIntervalMs = SendIntervalMs
        });
    }

    public record CreateCodeRequest(string? Label);

    private static async Task<IResult> CreateCode(
        CreateCodeRequest req, AppDbContext db, ClaimsPrincipal user)
    {
        var plaintext = GenerateCode(CodeDigits);
        var hash      = DbSeeder.Sha256Hex(plaintext);
        var prefix    = plaintext[..2];

        var code = new EnrollmentCode
        {
            CodeHash        = hash,
            CodePrefix      = prefix,
            ExpiresAt       = DateTime.UtcNow.AddMinutes(CodeLifetimeMinutes),
            CreatedByUserId = user.GetUserId(),
            TenantId        = user.GetTenantId(),     // код принадлежит тенанту админа
            Label           = string.IsNullOrWhiteSpace(req.Label) ? null : req.Label.Trim()
        };
        db.EnrollmentCodes.Add(code);
        await db.SaveChangesAsync();

        return Results.Ok(new
        {
            id        = code.Id,
            code      = plaintext,                       // показывается ОДИН раз
            prefix    = code.CodePrefix,
            label     = code.Label,
            expiresAt = code.ExpiresAt
        });
    }

    private static async Task<IResult> ListCodes(AppDbContext db, ClaimsPrincipal user, bool? includeUsed = false)
    {
        var tenantId = user.GetTenantId();
        var now = DateTime.UtcNow;
        var q = db.EnrollmentCodes.AsQueryable();
        if (tenantId is not null) q = q.Where(c => c.TenantId == tenantId);
        if (includeUsed != true)
            q = q.Where(c => c.UsedAt == null && c.ExpiresAt > now);

        var rows = await q
            .OrderByDescending(c => c.CreatedAt)
            .Select(c => new
            {
                id            = c.Id,
                prefix        = c.CodePrefix,
                label         = c.Label,
                expiresAt     = c.ExpiresAt,
                usedAt        = c.UsedAt,
                usedByDeviceId = c.UsedByDeviceId,
                createdAt     = c.CreatedAt,
                isExpired     = c.UsedAt == null && c.ExpiresAt <= now
            })
            .ToListAsync();

        return Results.Ok(rows);
    }

    private static async Task<IResult> RevokeCode(int id, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var code = await db.EnrollmentCodes.FindAsync(id);
        if (code is null) return Results.NotFound();
        if (tenantId is not null && code.TenantId != tenantId) return Results.NotFound();
        if (code.UsedAt is not null) return Results.Conflict(new { error = "already_used" });

        // помечаем как использованный без устройства = отозван
        code.UsedAt = DateTime.UtcNow;
        await db.SaveChangesAsync();
        return Results.Ok(new { revoked = true });
    }

    // ----- хелперы -----

    private static string GenerateApiKey()
    {
        Span<byte> bytes = stackalloc byte[ApiKeyByteLength];
        RandomNumberGenerator.Fill(bytes);
        var hex = new char[bytes.Length * 2];
        for (var i = 0; i < bytes.Length; i++)
        {
            hex[2 * i]     = ToHex(bytes[i] >> 4);
            hex[2 * i + 1] = ToHex(bytes[i] & 0xF);
        }
        return new string(hex);
    }

    private static string GenerateCode(int digits)
    {
        // 6 десятичных цифр через RandomNumberGenerator
        Span<byte> bytes = stackalloc byte[4];
        RandomNumberGenerator.Fill(bytes);
        var num = BitConverter.ToUInt32(bytes);
        var max = (uint)Math.Pow(10, digits);
        return (num % max).ToString().PadLeft(digits, '0');
    }

    private static char ToHex(int n) => (char)(n < 10 ? '0' + n : 'a' + (n - 10));

    private static bool FixedTimeEquals(string a, string b)
    {
        if (a.Length != b.Length) return false;
        var diff = 0;
        for (var i = 0; i < a.Length; i++) diff |= a[i] ^ b[i];
        return diff == 0;
    }
}
