using System.Security.Claims;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Endpoints;

public static class TripEndpoints
{
    /// Порог расхождения GPS-пробега и интеграла CAN-скорости, при котором
    /// возможен спуфинг GPS (доля от большей величины).
    private const double SpoofSuspectThreshold = 0.30;

    public static void MapTripEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/vehicles/{vehicleId:int}/trips", ListTripsForVehicle).RequireAuthorization("admin");
        app.MapGet("/api/trips/{tripId:int}",             GetTrip)             .RequireAuthorization("admin");
        app.MapGet("/api/trips/{tripId:int}/track",        GetTripTrack)        .RequireAuthorization("admin");
    }

    private static async Task<IResult> ListTripsForVehicle(
        int vehicleId, AppDbContext db, ClaimsPrincipal user,
        int? skip = 0, int? take = 20)
    {
        var tenantId = user.GetTenantId();
        var vehicle = await db.Vehicles.FindAsync(vehicleId);
        if (vehicle is null) return Results.NotFound();
        if (tenantId is not null && vehicle.TenantId != tenantId) return Results.NotFound();

        var s = Math.Max(0, skip ?? 0);
        var t = Math.Clamp(take ?? 20, 1, 200);

        var rows = await db.Trips
            .Where(tr => tr.VehicleId == vehicleId)
            .OrderByDescending(tr => tr.StartedAt)
            .Skip(s)
            .Take(t)
            .Select(tr => new
            {
                id = tr.Id,
                startedAt = tr.StartedAt,
                endedAt = tr.EndedAt,
                status = tr.Status == TripStatus.Open ? "open" : "closed",
                durationSec = tr.DurationSec,
                pointCount = tr.PointCount,
                distanceGpsKm = tr.DistanceGpsKm,
                distanceOdoKm = tr.DistanceOdoKm,
                distanceSpeedKm = tr.DistanceSpeedKm,
                avgSpeed = tr.AvgSpeed,
                maxSpeed = tr.MaxSpeed,
                fuelUsedPercent = tr.FuelUsedPercent,
                startLat = tr.StartLat, startLng = tr.StartLng,
                endLat = tr.EndLat,     endLng = tr.EndLng,
                dtcCount = ParseDtcCount(tr.DtcCodesJson),
                gpsSpoofSuspect = IsSpoofSuspect(tr)
            })
            .ToListAsync();

        var total = await db.Trips.CountAsync(tr => tr.VehicleId == vehicleId);

        return Results.Ok(new { total, skip = s, take = t, items = rows });
    }

    private static async Task<IResult> GetTrip(int tripId, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var trip = await db.Trips.AsNoTracking().FirstOrDefaultAsync(t => t.Id == tripId);
        if (trip is null) return Results.NotFound();
        if (tenantId is not null && trip.TenantId is not null && trip.TenantId != tenantId)
            return Results.NotFound();

        var dtcCodes = ParseDtc(trip.DtcCodesJson);

        return Results.Ok(new
        {
            id = trip.Id,
            vehicleId = trip.VehicleId,
            deviceId = trip.DeviceId,
            startedAt = trip.StartedAt,
            endedAt = trip.EndedAt,
            lastActivityAt = trip.LastActivityAt,
            status = trip.Status == TripStatus.Open ? "open" : "closed",
            durationSec = trip.DurationSec,
            pointCount = trip.PointCount,
            distanceGpsKm = trip.DistanceGpsKm,
            distanceOdoKm = trip.DistanceOdoKm,
            distanceSpeedKm = trip.DistanceSpeedKm,
            distancePrimaryKm = PrimaryDistance(trip),
            avgSpeed = trip.AvgSpeed,
            maxSpeed = trip.MaxSpeed,
            avgRpm = trip.AvgRpm,
            maxRpm = trip.MaxRpm,
            fuelStartPercent = trip.FuelStartPercent,
            fuelEndPercent = trip.FuelEndPercent,
            fuelUsedPercent = trip.FuelUsedPercent,
            startLat = trip.StartLat, startLng = trip.StartLng,
            endLat = trip.EndLat,     endLng = trip.EndLng,
            odoStartKm = trip.OdoStartKm,
            odoEndKm = trip.OdoEndKm,
            dtcCodes,
            gpsSpoofSuspect = IsSpoofSuspect(trip)
        });
    }

    private static async Task<IResult> GetTripTrack(int tripId, AppDbContext db, ClaimsPrincipal user)
    {
        var tenantId = user.GetTenantId();
        var trip = await db.Trips.AsNoTracking().FirstOrDefaultAsync(t => t.Id == tripId);
        if (trip is null) return Results.NotFound();
        if (tenantId is not null && trip.TenantId is not null && trip.TenantId != tenantId)
            return Results.NotFound();

        var pts = await db.Telemetry
            .Where(t => t.TripId == tripId && t.Lat.HasValue && t.Lng.HasValue)
            .OrderBy(t => t.Timestamp)
            .Select(t => new
            {
                lat = t.Lat!.Value,
                lng = t.Lng!.Value,
                spd = t.GpsSpeed ?? t.Speed,
                ts  = new DateTimeOffset(t.Timestamp, TimeSpan.Zero).ToUnixTimeSeconds()
            })
            .ToListAsync();

        // Возвращаем массив массивов — экономит трафик примерно на 60% против объектов
        var points = pts.Select(p => new object?[] { p.lat, p.lng, p.spd, p.ts }).ToList();
        return Results.Ok(new { tripId, count = points.Count, points });
    }

    // ───── helpers ──────────────────────────────────────────────

    private static double? PrimaryDistance(Trip t)
    {
        // Приоритет: одометр J1939 → Haversine GPS → интеграл CAN-скорости
        return t.DistanceOdoKm ?? t.DistanceGpsKm ?? t.DistanceSpeedKm;
    }

    private static bool IsSpoofSuspect(Trip t)
    {
        // Расхождение между GPS-пробегом и интегралом скорости > 30%
        if (!t.DistanceGpsKm.HasValue || !t.DistanceSpeedKm.HasValue) return false;
        var max = Math.Max(t.DistanceGpsKm.Value, t.DistanceSpeedKm.Value);
        if (max < 0.5) return false;     // слишком маленькая поездка — шум
        var diff = Math.Abs(t.DistanceGpsKm.Value - t.DistanceSpeedKm.Value);
        return diff / max > SpoofSuspectThreshold;
    }

    private static int ParseDtcCount(string json)
    {
        if (string.IsNullOrWhiteSpace(json) || json == "[]") return 0;
        try
        {
            var arr = JsonSerializer.Deserialize<string[]>(json);
            return arr?.Length ?? 0;
        }
        catch { return 0; }
    }

    private static string[] ParseDtc(string json)
    {
        if (string.IsNullOrWhiteSpace(json) || json == "[]") return Array.Empty<string>();
        try { return JsonSerializer.Deserialize<string[]>(json) ?? Array.Empty<string>(); }
        catch { return Array.Empty<string>(); }
    }
}