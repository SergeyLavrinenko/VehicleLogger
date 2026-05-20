using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Endpoints;

public static class DeviceListEndpoints
{
    private const int OnlineThresholdSeconds = 60;

    public static void MapDeviceListEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet ("/api/devices", GetDevices)     .RequireAuthorization("admin");
        app.MapPost("/api/devices", RegisterDevice) .RequireAuthorization("admin");
    }

    private static async Task<IResult> GetDevices(AppDbContext db, ClaimsPrincipal user, string? status = null)
    {
        var tenantId = user.GetTenantId();
        var threshold = DateTime.UtcNow.AddSeconds(-OnlineThresholdSeconds);

        var q = db.Devices.Include(d => d.Vehicle).AsQueryable();
        if (tenantId is not null) q = q.Where(d => d.TenantId == tenantId);

        if (!string.IsNullOrWhiteSpace(status) &&
            Enum.TryParse<DeviceStatus>(status, ignoreCase: true, out var st))
            q = q.Where(d => d.Status == st);

        var rows = await q
            .OrderBy(d => d.SerialNumber)
            .Select(d => new
            {
                id             = d.Id,
                serialNumber   = d.SerialNumber,
                status         = d.Status.ToString().ToLowerInvariant(),
                isOnline       = d.LastPingAt != null && d.LastPingAt > threshold,
                lastPingAt     = d.LastPingAt,
                vehicleId      = d.VehicleId,
                vehicleName    = d.Vehicle != null ? d.Vehicle.Name : null,
                vehiclePlate   = d.Vehicle != null ? d.Vehicle.LicensePlate : null,
                secretFragment = d.SecretFragment,
                claimedAt      = d.ClaimedAt,
                hasApiKey      = !string.IsNullOrEmpty(d.ApiKey)
                                 && !d.ApiKey.StartsWith("unclaimed:")
            })
            .ToListAsync();

        return Results.Ok(rows);
    }

    public record RegisterDeviceRequest(string SerialNumber, string? DeviceSecret);

    private static async Task<IResult> RegisterDevice(
        RegisterDeviceRequest req, AppDbContext db, ClaimsPrincipal user)
    {
        if (string.IsNullOrWhiteSpace(req.SerialNumber))
            return Results.BadRequest(new { error = "missing_serial" });

        var serial = req.SerialNumber.Trim();
        if (serial.Length is < 3 or > 64)
            return Results.BadRequest(new { error = "serial_length" });

        if (await db.Devices.AnyAsync(d => d.SerialNumber == serial))
            return Results.Conflict(new { error = "serial_exists" });

        string secret;
        if (!string.IsNullOrWhiteSpace(req.DeviceSecret))
        {
            var s = req.DeviceSecret.Trim().ToLowerInvariant();
            if (s.Length != 64 || !IsHex(s))
                return Results.BadRequest(new { error = "secret_must_be_64_hex" });
            secret = s;
        }
        else
        {
            secret = GenerateSecret();
        }

        var device = new Device
        {
            SerialNumber   = serial,
            SecretHash     = DbSeeder.Sha256Hex(secret),
            SecretFragment = secret[..8],
            Status         = DeviceStatus.Manufactured,
            ApiKey         = $"unclaimed:{serial}",
            TenantId       = user.GetTenantId()
        };
        db.Devices.Add(device);
        await db.SaveChangesAsync();

        return Results.Ok(new
        {
            id             = device.Id,
            serialNumber   = device.SerialNumber,
            deviceSecret   = secret,
            secretFragment = device.SecretFragment,
            status         = device.Status.ToString().ToLowerInvariant()
        });
    }

    private static bool IsHex(string s)
    {
        foreach (var c in s)
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        return true;
    }

    private static string GenerateSecret()
    {
        Span<byte> bytes = stackalloc byte[32];
        RandomNumberGenerator.Fill(bytes);
        var hex = new char[64];
        for (var i = 0; i < 32; i++)
        {
            hex[2 * i]     = ToHex(bytes[i] >> 4);
            hex[2 * i + 1] = ToHex(bytes[i] & 0xF);
        }
        return new string(hex);
    }

    private static char ToHex(int n) => (char)(n < 10 ? '0' + n : 'a' + (n - 10));
}
