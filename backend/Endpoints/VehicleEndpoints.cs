using System.Security.Claims;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Endpoints;

public static class VehicleEndpoints
{
    public static void MapVehicleEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet   ("/api/vehicles",                    GetVehicles)  .RequireAuthorization("admin");
        app.MapPost  ("/api/vehicles",                    CreateVehicle).RequireAuthorization("admin");
        app.MapGet   ("/api/vehicles/{id:int}",           GetVehicle)   .RequireAuthorization("admin");
        app.MapDelete("/api/vehicles/{id:int}",           DeleteVehicle).RequireAuthorization("admin");
        app.MapGet   ("/api/vehicles/{id:int}/telemetry", GetTelemetry) .RequireAuthorization("admin");
        app.MapGet   ("/api/vehicles/{id:int}/alerts",    GetAlerts)    .RequireAuthorization("admin");
        app.MapGet   ("/api/vehicles/{id:int}/refuels",   GetRefuels)   .RequireAuthorization("admin");
        app.MapGet   ("/api/dashboard",                   GetDashboard) .RequireAuthorization("admin");
    }

    public record CreateVehicleRequest(string? Name, string? LicensePlate);

    private static async Task<IResult> CreateVehicle(
        CreateVehicleRequest body, AppDbContext db, ClaimsPrincipal user, HttpContext http)
    {
        var name  = body.Name?.Trim() ?? "";
        var plate = body.LicensePlate?.Trim() ?? "";
        if (name.Length is < 2 or > 100) return Results.BadRequest(new { error = "name_length" });
        if (plate.Length is < 1 or > 20) return Results.BadRequest(new { error = "plate_length" });

        var tenantId = user.GetTenantId() ?? http.GetTenantContext().Tenant?.Id;
        if (tenantId is null)
            return Results.BadRequest(new { error = "use_subdomain", message = "Создавать фуры можно только из поддомена тенанта." });

        var v = new Vehicle { Name = name, LicensePlate = plate, TenantId = tenantId };
        db.Vehicles.Add(v);
        await db.SaveChangesAsync();
        return Results.Created($"/api/vehicles/{v.Id}", new { id = v.Id, name = v.Name, licensePlate = v.LicensePlate });
    }

    private static async Task<IResult> DeleteVehicle(int id, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var v = await db.Vehicles.Include(x => x.Device).FirstOrDefaultAsync(x => x.Id == id);
        if (v is null) return Results.NotFound();
        if (tenantId is not null && v.TenantId != tenantId) return Results.NotFound();
        if (v.Device is not null)
            return Results.Conflict(new { error = "vehicle_has_device", message = "Сначала отвяжите устройство от фуры." });

        db.Vehicles.Remove(v);
        await db.SaveChangesAsync();
        return Results.NoContent();
    }

    private const int OnlineThresholdSeconds = 60;

    private static async Task<IResult> GetVehicles(AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var threshold = DateTime.UtcNow.AddSeconds(-OnlineThresholdSeconds);

        var rows = await db.Vehicles
            .Where(v => tenantId == null || v.TenantId == tenantId)
            .Select(v => new
            {
                id = v.Id,
                name = v.Name,
                licensePlate = v.LicensePlate,
                device = v.Device == null ? null : new
                {
                    isOnline = v.Device.LastPingAt != null && v.Device.LastPingAt > threshold,
                    lastPingAt = v.Device.LastPingAt,
                    serialNumber = v.Device.SerialNumber
                },
                lastTelemetryAt = db.Telemetry
                    .Where(t => t.VehicleId == v.Id)
                    .OrderByDescending(t => t.Timestamp)
                    .Select(t => (DateTime?)t.Timestamp)
                    .FirstOrDefault()
            })
            .ToListAsync();

        return Results.Ok(rows);
    }

    private static async Task<IResult> GetVehicle(int id, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var threshold = DateTime.UtcNow.AddSeconds(-OnlineThresholdSeconds);

        var v = await db.Vehicles
            .Include(x => x.Device)
            .FirstOrDefaultAsync(x => x.Id == id);
        if (v is null) return Results.NotFound();
        if (tenantId is not null && v.TenantId != tenantId) return Results.NotFound();

        var lastT = v.Device == null ? null
            : await db.Telemetry
                .Where(t => t.VehicleId == v.Id)
                .OrderByDescending(t => t.Timestamp)
                .Select(t => new
                {
                    timestamp = t.Timestamp,
                    rpm = t.Rpm, speed = t.Speed, coolantTemp = t.CoolantTemp,
                    oilPressure = t.OilPressure, fuelLevel = t.FuelLevel,
                    voltage = t.Voltage, dtcCodesJson = t.DtcCodesJson
                })
                .FirstOrDefaultAsync();

        return Results.Ok(new
        {
            id = v.Id,
            name = v.Name,
            licensePlate = v.LicensePlate,
            device = v.Device == null ? null : new
            {
                serialNumber = v.Device.SerialNumber,
                isOnline = v.Device.LastPingAt != null && v.Device.LastPingAt > threshold,
                lastPingAt = v.Device.LastPingAt
            },
            latest = lastT == null ? null : new
            {
                timestamp = lastT.timestamp,
                rpm = lastT.rpm, speed = lastT.speed, coolantTemp = lastT.coolantTemp,
                oilPressure = lastT.oilPressure, fuelLevel = lastT.fuelLevel,
                voltage = lastT.voltage,
                dtcCodes = ParseDtc(lastT.dtcCodesJson)
            }
        });
    }

    private static async Task<IResult> GetTelemetry(
        int id, AppDbContext db, ClaimsPrincipal user,
        DateTime? from = null, DateTime? to = null, int limit = 200)
    {
        var tenantId = user.GetTenantId();
        var v = await db.Vehicles.Include(x => x.Device).FirstOrDefaultAsync(x => x.Id == id);
        if (v is null || v.Device is null) return Results.Ok(Array.Empty<object>());
        if (tenantId is not null && v.TenantId != tenantId) return Results.Ok(Array.Empty<object>());

        limit = Math.Clamp(limit, 1, 2000);
        var q = db.Telemetry.Where(t => t.VehicleId == v.Id);
        if (from is not null) q = q.Where(t => t.Timestamp >= from);
        if (to   is not null) q = q.Where(t => t.Timestamp <= to);

        var rows = await q
            .OrderByDescending(t => t.Timestamp)
            .Take(limit)
            .Select(t => new
            {
                timestamp = t.Timestamp,
                rpm = t.Rpm, speed = t.Speed, coolantTemp = t.CoolantTemp,
                oilPressure = t.OilPressure, fuelLevel = t.FuelLevel,
                voltage = t.Voltage,
                dtcCodesJson = t.DtcCodesJson
            })
            .ToListAsync();

        var result = rows
            .OrderBy(r => r.timestamp)
            .Select(r => new
            {
                r.timestamp, r.rpm, r.speed, r.coolantTemp,
                r.oilPressure, r.fuelLevel, r.voltage,
                dtcCodes = ParseDtc(r.dtcCodesJson)
            });

        return Results.Ok(result);
    }

    private static async Task<IResult> GetAlerts(int id, AppDbContext db, ClaimsPrincipal user, int limit = 50)
    {
        var tenantId = user.GetTenantId();
        var v = await db.Vehicles.FirstOrDefaultAsync(x => x.Id == id);
        if (v is null) return Results.Ok(Array.Empty<object>());
        if (tenantId is not null && v.TenantId != tenantId) return Results.Ok(Array.Empty<object>());

        limit = Math.Clamp(limit, 1, 500);
        var rows = await db.Alerts
            .Where(a => a.VehicleId == id)
            .OrderByDescending(a => a.Timestamp)
            .Take(limit)
            .Select(a => new
            {
                id = a.Id,
                timestamp = a.Timestamp,
                severity = a.Severity.ToString().ToLowerInvariant(),
                description = a.Description,
                recommendation = a.Recommendation,
                isRead = a.IsRead
            })
            .ToListAsync();
        return Results.Ok(rows);
    }

    private static async Task<IResult> GetRefuels(int id, AppDbContext db, ClaimsPrincipal user, int limit = 50)
    {
        var tenantId = user.GetTenantId();
        var v = await db.Vehicles.FirstOrDefaultAsync(x => x.Id == id);
        if (v is null) return Results.Ok(Array.Empty<object>());
        if (tenantId is not null && v.TenantId != tenantId) return Results.Ok(Array.Empty<object>());

        limit = Math.Clamp(limit, 1, 500);
        var rows = await db.Refuels
            .Where(r => r.VehicleId == id)
            .OrderByDescending(r => r.Timestamp)
            .Take(limit)
            .Select(r => new
            {
                id = r.Id,
                timestamp = r.Timestamp,
                liters = r.Liters,
                cost = r.Cost
            })
            .ToListAsync();
        return Results.Ok(rows);
    }

    private static async Task<IResult> GetDashboard(AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var threshold = DateTime.UtcNow.AddSeconds(-OnlineThresholdSeconds);
        var todayUtc = DateTime.UtcNow.Date;

        var vehiclesTotal = await db.Vehicles
            .Where(v => tenantId == null || v.TenantId == tenantId).CountAsync();
        var devicesOnline = await db.Devices
            .Where(d => tenantId == null || d.TenantId == tenantId)
            .CountAsync(d => d.LastPingAt != null && d.LastPingAt > threshold);
        var alertsUnread = await db.Alerts
            .Where(a => !a.IsRead &&
                (tenantId == null || db.Vehicles.Any(v => v.Id == a.VehicleId && v.TenantId == tenantId)))
            .CountAsync();
        var refuelsToday = await db.Refuels
            .Where(r => r.Timestamp >= todayUtc &&
                (tenantId == null || db.Vehicles.Any(v => v.Id == r.VehicleId && v.TenantId == tenantId)))
            .CountAsync();

        return Results.Ok(new { vehiclesTotal, devicesOnline, alertsUnread, refuelsToday });
    }

    private static string[] ParseDtc(string json)
    {
        if (string.IsNullOrWhiteSpace(json)) return Array.Empty<string>();
        try { return JsonSerializer.Deserialize<string[]>(json) ?? Array.Empty<string>(); }
        catch { return Array.Empty<string>(); }
    }
}
