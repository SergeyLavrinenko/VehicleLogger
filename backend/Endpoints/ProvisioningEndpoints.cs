using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Endpoints;

public static class ProvisioningEndpoints
{
    private const int ApiKeyByteLength = 32;       // 64 hex
    private const int SendIntervalMs   = 5000;

    public static void MapProvisioningEndpoints(this IEndpointRouteBuilder app)
    {
        // Со стороны устройства
        app.MapPost("/api/devices/provision", HandleProvision);

        // Со стороны админ-веба — требует JWT с ролью admin
        app.MapPost("/api/devices/claim",                 HandleClaim).RequireAuthorization("admin");
        app.MapPost("/api/devices/{id:int}/unclaim",      HandleUnclaim).RequireAuthorization("admin");
        app.MapPut ("/api/devices/{id:int}/vehicle",      HandleAssignVehicle).RequireAuthorization("admin");
        app.MapPost("/api/devices/{id:int}/rotate-key",   HandleRotateKey).RequireAuthorization("admin");
    }

    public record ProvisionRequest(string SerialNumber, string DeviceSecret);

    private static async Task<IResult> HandleProvision(
        ProvisionRequest req, AppDbContext db, HttpContext ctx)
    {
        if (string.IsNullOrWhiteSpace(req.SerialNumber) ||
            string.IsNullOrWhiteSpace(req.DeviceSecret))
            return Results.BadRequest(new { error = "missing_fields" });

        var device = await db.Devices.FirstOrDefaultAsync(d => d.SerialNumber == req.SerialNumber);
        if (device is null)
            return Results.Json(new { error = "unknown_serial" }, statusCode: 403);

        // Сравниваем хеш в постоянное время, чтобы не утекало через таймер.
        var presentedHash = DbSeeder.Sha256Hex(req.DeviceSecret);
        if (!FixedTimeEquals(presentedHash, device.SecretHash))
            return Results.Json(new { error = "invalid_secret" }, statusCode: 403);

        if (device.Status == DeviceStatus.Deactivated)
            return Results.Json(new { error = "deactivated" }, statusCode: 410);

        // Устройство привязано админом, забирает ключ.
        if (device.Status == DeviceStatus.Claimed)
        {
            device.Status = DeviceStatus.Active;
            await db.SaveChangesAsync();
        }

        if (device.Status == DeviceStatus.Active && IsRealKey(device.ApiKey))
        {
            var backendUrl = $"{ctx.Request.Scheme}://{ctx.Request.Host}";
            return Results.Ok(new
            {
                apiKey         = device.ApiKey,
                backendUrl     = backendUrl,
                sendIntervalMs = SendIntervalMs
            });
        }

        return Results.Json(new { status = "waiting_for_claim" }, statusCode: 202);
    }

    public record ClaimRequest(string SerialNumber, string DeviceSecretFragment, int? VehicleId);

    private static async Task<IResult> HandleClaim(ClaimRequest req, AppDbContext db, ClaimsPrincipal user)
    {
        if (string.IsNullOrWhiteSpace(req.SerialNumber) ||
            string.IsNullOrWhiteSpace(req.DeviceSecretFragment))
            return Results.BadRequest(new { error = "missing_fields" });

        var tenantId = user.GetTenantId();
        var device = await db.Devices.FirstOrDefaultAsync(d => d.SerialNumber == req.SerialNumber);
        if (device is null) return Results.NotFound(new { error = "not_found" });

        if (device.TenantId is not null && tenantId is not null && device.TenantId != tenantId)
            return Results.Json(new { error = "wrong_tenant" }, statusCode: 403);

        if (!string.Equals(device.SecretFragment, req.DeviceSecretFragment, StringComparison.OrdinalIgnoreCase))
            return Results.BadRequest(new { error = "fragment_mismatch" });

        if (device.Status != DeviceStatus.Manufactured)
            return Results.Conflict(new { error = "already_claimed", status = device.Status.ToString().ToLowerInvariant() });

        if (req.VehicleId is not null)
        {
            var vehicle = await db.Vehicles.FindAsync(req.VehicleId.Value);
            if (vehicle is null) return Results.NotFound(new { error = "vehicle_not_found" });
            if (tenantId is not null && vehicle.TenantId != tenantId)
                return Results.Json(new { error = "wrong_tenant_vehicle" }, statusCode: 403);
            device.VehicleId = vehicle.Id;
        }

        device.ApiKey    = GenerateApiKey();
        device.Status    = DeviceStatus.Claimed;
        device.ClaimedAt = DateTime.UtcNow;
        device.TenantId  = tenantId ?? device.TenantId;
        await db.SaveChangesAsync();

        return Results.Ok(new
        {
            deviceId     = device.Id,
            serialNumber = device.SerialNumber,
            status       = "claimed",
            // ApiKey возвращаем только одной стороне — админу через claim — чтобы он мог
            // зашить устройство (для дев-flow это удобно). В проде — только устройству через /provision.
            apiKey       = device.ApiKey
        });
    }

    private static async Task<IResult> HandleUnclaim(int id, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var device = await db.Devices.FindAsync(id);
        if (device is null) return Results.NotFound();
        if (tenantId is not null && device.TenantId != tenantId) return Results.NotFound();

        device.ApiKey    = $"unclaimed:{device.SerialNumber}";
        device.VehicleId = null;
        device.Status    = DeviceStatus.Manufactured;
        device.ClaimedAt = null;
        device.IsOnline  = false;
        await db.SaveChangesAsync();
        return Results.Ok(new { status = "manufactured" });
    }

    public record AssignVehicleRequest(int? VehicleId);

    private static async Task<IResult> HandleAssignVehicle(
        int id, AssignVehicleRequest req, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var device = await db.Devices.FindAsync(id);
        if (device is null) return Results.NotFound();
        if (tenantId is not null && device.TenantId != tenantId) return Results.NotFound();

        if (req.VehicleId is null)
        {
            device.VehicleId = null;
        }
        else
        {
            var v = await db.Vehicles.FindAsync(req.VehicleId.Value);
            if (v is null) return Results.NotFound(new { error = "vehicle_not_found" });
            if (tenantId is not null && v.TenantId != tenantId)
                return Results.Json(new { error = "wrong_tenant_vehicle" }, statusCode: 403);
            device.VehicleId = v.Id;
        }

        await db.SaveChangesAsync();
        return Results.Ok(new { deviceId = device.Id, vehicleId = device.VehicleId });
    }

    private static async Task<IResult> HandleRotateKey(int id, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var device = await db.Devices.FindAsync(id);
        if (device is null) return Results.NotFound();
        if (tenantId is not null && device.TenantId != tenantId) return Results.NotFound();
        if (device.Status == DeviceStatus.Manufactured)
            return Results.Conflict(new { error = "not_claimed" });

        device.ApiKey = GenerateApiKey();
        device.Status = DeviceStatus.Claimed;
        await db.SaveChangesAsync();
        return Results.Ok(new { rotated = true });
    }

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

    private static char ToHex(int n) => (char)(n < 10 ? '0' + n : 'a' + (n - 10));

    public static bool IsRealKey(string? key) =>
        !string.IsNullOrEmpty(key) && !key.StartsWith("unclaimed:", StringComparison.Ordinal);

    private static bool FixedTimeEquals(string a, string b)
    {
        if (a.Length != b.Length) return false;
        var diff = 0;
        for (var i = 0; i < a.Length; i++) diff |= a[i] ^ b[i];
        return diff == 0;
    }
}
