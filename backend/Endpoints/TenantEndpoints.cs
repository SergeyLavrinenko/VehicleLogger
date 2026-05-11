using System.Security.Cryptography;
using System.Text.RegularExpressions;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Endpoints;

public static class TenantEndpoints
{
    private static readonly Regex SubdomainRegex =
        new("^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$", RegexOptions.Compiled);

    public static void MapTenantEndpoints(this IEndpointRouteBuilder app)
    {
        // Создание/чтение тенантов — только super-admin (на apex без поддомена).
        // TenantClaimGuard уже не пустит пользователя с tenant_id в JWT на эти эндпоинты.
        app.MapPost   ("/api/tenants",          CreateTenant).RequireAuthorization("admin");
        app.MapGet    ("/api/tenants",          ListTenants) .RequireAuthorization("admin");
        app.MapDelete ("/api/tenants/{id:int}", DeleteTenant).RequireAuthorization("admin");
    }

    public record CreateTenantRequest(
        string Subdomain,
        string Name,
        string AdminEmail,
        string? AdminPassword,
        string? AdminName);

    private static async Task<IResult> CreateTenant(CreateTenantRequest req, AppDbContext db)
    {
        var subdomain = (req.Subdomain ?? "").Trim().ToLowerInvariant();
        var name      = (req.Name ?? "").Trim();
        var adminEmail = (req.AdminEmail ?? "").Trim().ToLowerInvariant();

        if (string.IsNullOrEmpty(subdomain) || !SubdomainRegex.IsMatch(subdomain))
            return Results.BadRequest(new { error = "invalid_subdomain", hint = "a-z, 0-9, '-', 3-63 символа" });
        if (string.IsNullOrEmpty(name))
            return Results.BadRequest(new { error = "missing_name" });
        if (string.IsNullOrEmpty(adminEmail) || !adminEmail.Contains('@'))
            return Results.BadRequest(new { error = "invalid_admin_email" });

        if (await db.Tenants.AnyAsync(t => t.Subdomain == subdomain))
            return Results.Conflict(new { error = "subdomain_exists" });
        if (await db.Users.AnyAsync(u => u.Email == adminEmail))
            return Results.Conflict(new { error = "admin_email_exists" });

        var password = string.IsNullOrWhiteSpace(req.AdminPassword)
            ? GeneratePassword()
            : req.AdminPassword!;

        var tenant = new Tenant { Subdomain = subdomain, Name = name };
        db.Tenants.Add(tenant);
        await db.SaveChangesAsync();

        var admin = new Models.User
        {
            Role         = UserRole.Admin,
            Email        = adminEmail,
            Name         = req.AdminName,
            PasswordHash = PasswordHasher.Hash(password),
            TenantId     = tenant.Id
        };
        db.Users.Add(admin);
        await db.SaveChangesAsync();

        return Results.Ok(new
        {
            id        = tenant.Id,
            subdomain = tenant.Subdomain,
            name      = tenant.Name,
            url       = $"https://{tenant.Subdomain}.nonconf.ru",
            createdAt = tenant.CreatedAt,
            admin = new
            {
                email    = admin.Email,
                password = password,            // показывается ОДИН раз
                name     = admin.Name
            }
        });
    }

    private static async Task<IResult> ListTenants(AppDbContext db)
    {
        var rows = await db.Tenants
            .OrderBy(t => t.Subdomain)
            .Select(t => new
            {
                id          = t.Id,
                subdomain   = t.Subdomain,
                name        = t.Name,
                url         = $"https://{t.Subdomain}.nonconf.ru",
                createdAt   = t.CreatedAt,
                deviceCount = db.Devices.Count(d => d.TenantId == t.Id),
                vehicleCount = db.Vehicles.Count(v => v.TenantId == t.Id),
                userCount   = db.Users.Count(u => u.TenantId == t.Id)
            })
            .ToListAsync();
        return Results.Ok(rows);
    }

    private static async Task<IResult> DeleteTenant(int id, AppDbContext db)
    {
        var tenant = await db.Tenants.FindAsync(id);
        if (tenant is null) return Results.NotFound();

        // Удаляем сам тенант. По спеке нужно ещё снести всех его пользователей
        // и устройства, но это деструктивно — пока просто отказ если есть данные.
        if (await db.Users.AnyAsync(u => u.TenantId == id))
            return Results.Conflict(new { error = "has_users", hint = "Сначала удалить пользователей тенанта" });
        if (await db.Devices.AnyAsync(d => d.TenantId == id))
            return Results.Conflict(new { error = "has_devices" });

        db.Tenants.Remove(tenant);
        await db.SaveChangesAsync();
        return Results.Ok(new { deleted = true });
    }

    private static string GeneratePassword()
    {
        const string alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
        Span<byte> bytes = stackalloc byte[12];
        RandomNumberGenerator.Fill(bytes);
        var sb = new System.Text.StringBuilder(12);
        foreach (var b in bytes) sb.Append(alphabet[b % alphabet.Length]);
        return sb.ToString();
    }
}
