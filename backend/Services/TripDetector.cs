using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Services;

/// Эвристика формирования поездок по последовательным пакетам телеметрии.
///
///   Открыть: ≥30 секунд активности подряд (rpm>RpmActiveThreshold ИЛИ gpsSpeed>GpsActiveThreshold).
///   Закрыть: ≥5 минут покоя подряд (rpm≤0 И gpsSpeed<GpsIdleThreshold).
///
/// Вызывается синхронно после сохранения каждого нового пакета.
public class TripDetector
{
    public const double  RpmActiveThreshold  = 600;
    public const double  GpsActiveThreshold  = 5;     // км/ч
    public const double  GpsIdleThreshold    = 2;     // км/ч
    public const int     TripOpenSeconds     = 30;
    public const int     TripCloseSeconds    = 300;   // 5 минут

    private readonly AppDbContext _db;
    private readonly TripStatsCalculator _stats;
    private readonly ILogger<TripDetector> _log;

    public TripDetector(AppDbContext db, TripStatsCalculator stats, ILogger<TripDetector> log)
    {
        _db = db;
        _stats = stats;
        _log = log;
    }

    public async Task ProcessAsync(TelemetryRecord record, Device device)
    {
        var active = IsActive(record);
        var idle   = IsIdle(record);

        var trip = await _db.Trips
            .Where(t => t.DeviceId == device.Id && t.Status == TripStatus.Open)
            .OrderByDescending(t => t.StartedAt)
            .FirstOrDefaultAsync();

        if (trip is null)
        {
            if (!active) return;

            // Проверяем — есть ли подряд ≥30 секунд активности.
            // Берём пакеты этого устройства, расположенные не раньше TripOpenSeconds до текущего.
            var since = record.Timestamp.AddSeconds(-TripOpenSeconds - 5);
            var recent = await _db.Telemetry
                .Where(t => t.DeviceId == device.Id && t.Timestamp >= since && t.Timestamp <= record.Timestamp)
                .OrderBy(t => t.Timestamp)
                .ToListAsync();
            if (recent.Count < 2) return;
            // Найти самый ранний активный пакет в непрерывной цепочке (без покоя между ним и текущим)
            DateTime? activeStart = null;
            foreach (var r in recent)
            {
                if (IsActive(r))
                    activeStart ??= r.Timestamp;
                else if (IsIdle(r))
                    activeStart = null;   // прервалась активность, считаем заново
            }
            if (activeStart is null) return;
            var activeDuration = (record.Timestamp - activeStart.Value).TotalSeconds;
            if (activeDuration < TripOpenSeconds) return;

            // Открываем поездку, привязываем к ней все активные пакеты, начиная с activeStart
            trip = new Trip
            {
                DeviceId       = device.Id,
                VehicleId      = device.VehicleId,
                TenantId       = device.TenantId,
                StartedAt      = activeStart.Value,
                LastActivityAt = record.Timestamp,
                Status         = TripStatus.Open
            };
            _db.Trips.Add(trip);
            await _db.SaveChangesAsync();

            await _db.Telemetry
                .Where(t => t.DeviceId == device.Id &&
                            t.Timestamp >= activeStart.Value &&
                            t.Timestamp <= record.Timestamp &&
                            t.TripId == null)
                .ExecuteUpdateAsync(s => s.SetProperty(t => t.TripId, trip.Id));

            _log.LogInformation("Trip {TripId} opened for device {Serial} at {Started}",
                trip.Id, device.SerialNumber, trip.StartedAt);
            return;
        }

        // Trip есть — привязываем пакет к ней
        record.TripId = trip.Id;
        trip.LastActivityAt = record.Timestamp;
        await _db.SaveChangesAsync();

        if (!idle) return;

        // Проверяем — не было ли ≥5 минут покоя
        var since2 = record.Timestamp.AddSeconds(-TripCloseSeconds - 5);
        var tail = await _db.Telemetry
            .Where(t => t.DeviceId == device.Id && t.Timestamp >= since2 && t.Timestamp <= record.Timestamp)
            .OrderBy(t => t.Timestamp)
            .ToListAsync();
        if (tail.Count < 2) return;

        DateTime? idleStart = null;
        var allIdle = true;
        foreach (var r in tail)
        {
            if (IsIdle(r))
                idleStart ??= r.Timestamp;
            else
            {
                idleStart = null;
                allIdle = false;
            }
        }
        if (idleStart is null || !allIdle) return;
        var idleDuration = (record.Timestamp - idleStart.Value).TotalSeconds;
        if (idleDuration < TripCloseSeconds) return;

        await CloseAsync(trip, record.Timestamp);
        _log.LogInformation("Trip {TripId} closed by idle for device {Serial}", trip.Id, device.SerialNumber);
    }

    public async Task CloseAsync(Trip trip, DateTime endedAt)
    {
        trip.Status  = TripStatus.Closed;
        trip.EndedAt = endedAt;
        await _stats.RecalculateAsync(trip);
        await _db.SaveChangesAsync();
    }

    public static bool IsActive(TelemetryRecord r)
    {
        // GPS-скорость намеренно НЕ учитываем: NEO-M8N в стационарном
        // состоянии нередко выдаёт мусор 50-150 км/ч из-за плавающего фикса.
        // Надёжные признаки активности — обороты двигателя или CAN-скорость.
        var rpmActive = r.Rpm.HasValue && r.Rpm.Value > RpmActiveThreshold;
        var canSpeedActive = r.Speed.HasValue && r.Speed.Value > GpsActiveThreshold;
        return rpmActive || canSpeedActive;
    }

    public static bool IsIdle(TelemetryRecord r)
    {
        // По той же причине: GPS из условия покоя выкинут.
        var rpmIdle = !r.Rpm.HasValue || r.Rpm.Value <= 0;
        var canIdle = !r.Speed.HasValue || r.Speed.Value < GpsIdleThreshold;
        return rpmIdle && canIdle;
    }
}