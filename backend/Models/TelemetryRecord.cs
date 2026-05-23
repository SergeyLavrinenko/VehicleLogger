namespace VehicleLogger.Api.Models;

public class TelemetryRecord
{
    public long Id { get; set; }

    public int DeviceId { get; set; }
    public Device? Device { get; set; }

    public DateTime Timestamp { get; set; }

    // ── CAN-параметры ─────────────────────────────────
    public int? Rpm { get; set; }
    public double? Speed { get; set; }
    public double? CoolantTemp { get; set; }
    public double? OilPressure { get; set; }
    public double? FuelLevel { get; set; }
    public double? Voltage { get; set; }

    /// JSON-массив строк (DTC-коды OBD-II, например ["P0301"]).
    public string DtcCodesJson { get; set; } = "[]";

    // ── GPS ──────────────────────────────────────────
    public double? Lat { get; set; }
    public double? Lng { get; set; }
    public double? Altitude { get; set; }
    public double? GpsSpeed { get; set; }   // км/ч от приёмника
    public double? Course { get; set; }     // градусы 0..359
    public int?    Satellites { get; set; }
    public int?    GpsFix { get; set; }     // 0=нет, 1=2D, 2=3D

    // ── Привязка к поездке ───────────────────────────
    /// NULL если пакет вне поездки (стоянка, обрыв связи).
    public int? TripId { get; set; }
    public Trip? Trip { get; set; }

    /// J1939 PGN 65248 (одометр) — для расчёта пробега поездки разностью.
    public double? OdometerKm { get; set; }

    public DateTime ReceivedAt { get; set; }
}