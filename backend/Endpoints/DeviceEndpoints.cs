using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Dtos;
using VehicleLogger.Api.Models;
using VehicleLogger.Api.Services;

namespace VehicleLogger.Api.Endpoints;

public static class DeviceEndpoints
{
    private const string DeviceKeyHeader = "X-Device-Key";
    private const string AuthHeader      = "Authorization";
    private const string BearerPrefix    = "Bearer ";

    public static void MapDeviceEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/telemetry", HandleTelemetry);
        app.MapPost("/api/device/ping", HandlePing);
    }

    private static async Task<IResult> HandleTelemetry(
        HttpContext ctx,
        TelemetryRequest req,
        AppDbContext db,
        TripDetector tripDetector,
        ILoggerFactory loggerFactory)
    {
        var log = loggerFactory.CreateLogger("Telemetry");

        var device = await AuthenticateDeviceAsync(ctx, req.DeviceId, db);
        if (device is null)
        {
            log.LogWarning("Unauthorized telemetry from deviceId={DeviceId}", req.DeviceId);
            return Results.Unauthorized();
        }

        if (req.Timestamp == default)
            return Results.BadRequest(new { error = "timestamp_required" });

        var timestamp = req.Timestamp.ToUniversalTime();

        // Дедупликация: при QoS-1 MQTT-ретраях или повторе HTTPS-запроса
        // тот же (DeviceId, Timestamp) приходит дважды. Считаем дубль успехом.
        var alreadyExists = await db.Telemetry
            .AnyAsync(t => t.DeviceId == device.Id && t.Timestamp == timestamp);
        if (alreadyExists)
            return Results.Ok(new { stored = false, reason = "duplicate" });

        var record = new TelemetryRecord
        {
            DeviceId    = device.Id,
            Timestamp   = timestamp,
            Rpm         = req.Data.Rpm,
            Speed       = req.Data.Speed,
            CoolantTemp = req.Data.CoolantTemp,
            OilPressure = req.Data.OilPressure,
            FuelLevel   = req.Data.FuelLevel,
            Voltage     = req.Data.Voltage,
            DtcCodesJson = JsonSerializer.Serialize(req.Data.DtcCodes ?? new List<string>()),
            OdometerKm  = req.Data.Odometer,
            // GPS
            Lat        = req.Gps?.Lat,
            Lng        = req.Gps?.Lng,
            Altitude   = req.Gps?.Alt,
            GpsSpeed   = req.Gps?.Speed,
            Course     = req.Gps?.Course,
            Satellites = req.Gps?.Sats,
            GpsFix     = req.Gps?.Fix,
            ReceivedAt = DateTime.UtcNow
        };

        db.Telemetry.Add(record);

        device.IsOnline   = true;
        device.LastPingAt = DateTime.UtcNow;

        await db.SaveChangesAsync();

        // Детектор поездки видит свежесохранённый пакет; может открыть или закрыть Trip
        // и проставить TripId записи.
        await tripDetector.ProcessAsync(record, device);

        log.LogInformation(
            "Telemetry stored: device={Serial} ts={Ts} rpm={Rpm} speed={Speed} gps={HasGps}",
            device.SerialNumber, record.Timestamp, record.Rpm, record.Speed,
            record.Lat.HasValue);

        return Results.Ok(new { stored = true, id = record.Id, tripId = record.TripId });
    }

    private static async Task<IResult> HandlePing(
        HttpContext ctx,
        PingRequest req,
        AppDbContext db)
    {
        var device = await AuthenticateDeviceAsync(ctx, req.DeviceId, db);
        if (device is null) return Results.Unauthorized();

        device.IsOnline = true;
        device.LastPingAt = DateTime.UtcNow;
        await db.SaveChangesAsync();

        return Results.Ok();
    }

    private static async Task<Device?> AuthenticateDeviceAsync(
        HttpContext ctx, string deviceId, AppDbContext db)
    {
        var key = ExtractDeviceKey(ctx);
        if (string.IsNullOrWhiteSpace(key) || string.IsNullOrWhiteSpace(deviceId))
            return null;

        if (!ProvisioningEndpoints.IsRealKey(key)) return null;

        var device = await db.Devices.FirstOrDefaultAsync(d => d.ApiKey == key);
        if (device is null) return null;
        if (!string.Equals(device.SerialNumber, deviceId, StringComparison.Ordinal))
            return null;

        return device;
    }

    /// Принимаем ключ либо в `X-Device-Key` (legacy для device-sim),
    /// либо в `Authorization: Bearer <key>` (новая прошивка).
    private static string? ExtractDeviceKey(HttpContext ctx)
    {
        if (ctx.Request.Headers.TryGetValue(DeviceKeyHeader, out var k) && !string.IsNullOrWhiteSpace(k))
            return k.ToString();

        if (ctx.Request.Headers.TryGetValue(AuthHeader, out var auth))
        {
            var s = auth.ToString();
            if (s.StartsWith(BearerPrefix, StringComparison.OrdinalIgnoreCase))
                return s[BearerPrefix.Length..].Trim();
        }
        return null;
    }
}