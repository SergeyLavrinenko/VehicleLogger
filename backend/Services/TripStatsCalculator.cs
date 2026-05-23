using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Services;

/// Считает агрегаты поездки на основании всех её пакетов телеметрии.
/// Сохраняет результат в саму поездку (передаёт изменённый объект, сохранение — снаружи).
public class TripStatsCalculator
{
    private readonly AppDbContext _db;
    private readonly ILogger<TripStatsCalculator> _log;

    public TripStatsCalculator(AppDbContext db, ILogger<TripStatsCalculator> log)
    {
        _db = db;
        _log = log;
    }

    public async Task RecalculateAsync(Trip trip)
    {
        var records = await _db.Telemetry
            .Where(t => t.TripId == trip.Id)
            .OrderBy(t => t.Timestamp)
            .ToListAsync();

        if (records.Count == 0)
        {
            _log.LogWarning("Trip {TripId} has no records — leaving stats empty", trip.Id);
            return;
        }

        var first = records[0];
        var last  = records[^1];

        trip.PointCount = records.Count;
        trip.StartedAt  = first.Timestamp;
        if (trip.Status == TripStatus.Closed && trip.EndedAt is null)
            trip.EndedAt = last.Timestamp;
        var endTs = trip.EndedAt ?? last.Timestamp;
        trip.DurationSec = (int)Math.Max(0, (endTs - trip.StartedAt).TotalSeconds);

        // ── Скорости и обороты ───────────────────────────────
        var speeds = records.Where(r => r.Speed.HasValue).Select(r => r.Speed!.Value).ToList();
        var rpms   = records.Where(r => r.Rpm.HasValue).Select(r => (double)r.Rpm!.Value).ToList();
        trip.AvgSpeed = speeds.Count > 0 ? speeds.Average() : null;
        trip.MaxSpeed = speeds.Count > 0 ? speeds.Max()     : null;
        trip.AvgRpm   = rpms.Count > 0   ? rpms.Average()   : null;
        trip.MaxRpm   = rpms.Count > 0   ? rpms.Max()       : null;

        // ── Топливо ─────────────────────────────────────────
        var firstFuel = records.FirstOrDefault(r => r.FuelLevel.HasValue)?.FuelLevel;
        var lastFuel  = records.LastOrDefault(r => r.FuelLevel.HasValue)?.FuelLevel;
        trip.FuelStartPercent = firstFuel;
        trip.FuelEndPercent   = lastFuel;
        if (firstFuel.HasValue && lastFuel.HasValue)
        {
            // Если в середине поездки топливо выросло — могла быть заправка, защищаемся:
            // считаем расход как сумму отрицательных дельт.
            double burned = 0;
            double? prev = null;
            foreach (var r in records)
            {
                if (!r.FuelLevel.HasValue) continue;
                if (prev.HasValue)
                {
                    var delta = r.FuelLevel.Value - prev.Value;
                    if (delta < 0) burned += -delta;
                }
                prev = r.FuelLevel.Value;
            }
            trip.FuelUsedPercent = burned;
        }

        // ── Три оценки пробега ──────────────────────────────
        trip.DistanceGpsKm   = CalcGpsDistanceKm(records);
        trip.DistanceOdoKm   = CalcOdoDistanceKm(records, out var odoStart, out var odoEnd);
        trip.DistanceSpeedKm = CalcSpeedIntegralKm(records);
        trip.OdoStartKm = odoStart;
        trip.OdoEndKm   = odoEnd;

        // ── Геометрия ───────────────────────────────────────
        var firstGps = records.FirstOrDefault(r => r.Lat.HasValue && r.Lng.HasValue);
        var lastGps  = records.LastOrDefault (r => r.Lat.HasValue && r.Lng.HasValue);
        trip.StartLat = firstGps?.Lat;
        trip.StartLng = firstGps?.Lng;
        trip.EndLat   = lastGps?.Lat;
        trip.EndLng   = lastGps?.Lng;

        // ── DTC ─────────────────────────────────────────────
        var dtcs = new HashSet<string>(StringComparer.Ordinal);
        foreach (var r in records)
        {
            if (string.IsNullOrWhiteSpace(r.DtcCodesJson) || r.DtcCodesJson == "[]") continue;
            try
            {
                var arr = JsonSerializer.Deserialize<List<string>>(r.DtcCodesJson);
                if (arr is null) continue;
                foreach (var code in arr) if (!string.IsNullOrWhiteSpace(code)) dtcs.Add(code);
            }
            catch { /* битый JSON — пропускаем */ }
        }
        trip.DtcCodesJson = JsonSerializer.Serialize(dtcs.ToArray());
    }

    private static double? CalcGpsDistanceKm(List<TelemetryRecord> records)
    {
        TelemetryRecord? prev = null;
        double total = 0;
        var any = false;
        foreach (var r in records)
        {
            if (!r.Lat.HasValue || !r.Lng.HasValue) continue;
            if (prev is not null && prev.Lat.HasValue && prev.Lng.HasValue)
            {
                total += Haversine(prev.Lat!.Value, prev.Lng!.Value, r.Lat.Value, r.Lng.Value);
                any = true;
            }
            prev = r;
        }
        return any ? total : null;
    }

    private static double? CalcOdoDistanceKm(
        List<TelemetryRecord> records, out double? startKm, out double? endKm)
    {
        startKm = records.FirstOrDefault(r => r.OdometerKm.HasValue)?.OdometerKm;
        endKm   = records.LastOrDefault (r => r.OdometerKm.HasValue)?.OdometerKm;
        if (startKm is null || endKm is null) return null;
        var d = endKm.Value - startKm.Value;
        return d >= 0 ? d : null;
    }

    private static double? CalcSpeedIntegralKm(List<TelemetryRecord> records)
    {
        TelemetryRecord? prev = null;
        double total = 0;
        var any = false;
        foreach (var r in records)
        {
            if (prev is not null && r.Speed.HasValue && prev.Speed.HasValue)
            {
                var dtHours = (r.Timestamp - prev.Timestamp).TotalHours;
                if (dtHours > 0 && dtHours < 1.0/60.0)   // пакеты должны идти чаще минуты
                {
                    var avgKmh = (r.Speed.Value + prev.Speed.Value) / 2.0;
                    total += avgKmh * dtHours;
                    any = true;
                }
            }
            prev = r;
        }
        return any ? total : null;
    }

    /// Формула гаверсинуса. Возвращает расстояние в километрах.
    private static double Haversine(double lat1, double lng1, double lat2, double lng2)
    {
        const double R = 6371.0;   // средний радиус Земли, км
        var dLat = ToRad(lat2 - lat1);
        var dLng = ToRad(lng2 - lng1);
        var a = Math.Sin(dLat / 2) * Math.Sin(dLat / 2)
              + Math.Cos(ToRad(lat1)) * Math.Cos(ToRad(lat2))
              * Math.Sin(dLng / 2) * Math.Sin(dLng / 2);
        var c = 2 * Math.Atan2(Math.Sqrt(a), Math.Sqrt(1 - a));
        return R * c;
    }
    private static double ToRad(double deg) => deg * Math.PI / 180.0;
}