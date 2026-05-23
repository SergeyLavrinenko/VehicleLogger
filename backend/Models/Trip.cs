namespace VehicleLogger.Api.Models;

public enum TripStatus
{
    Open   = 0,
    Closed = 1
}

/// Автоматически формируемая поездка — отрезок времени, когда устройство было в движении.
/// Открывается детектором при первых ≥30 секундах активности (RPM>600 или GPS-скорость>5),
/// закрывается при ≥5 минутах покоя (RPM=0 и GPS<2) либо фоновым воркером при обрыве связи >15 минут.
public class Trip
{
    public int Id { get; set; }

    public int? VehicleId { get; set; }
    public Vehicle? Vehicle { get; set; }

    public int DeviceId { get; set; }
    public Device? Device { get; set; }

    public int? TenantId { get; set; }
    public Tenant? Tenant { get; set; }

    public DateTime  StartedAt { get; set; }
    public DateTime? EndedAt   { get; set; }
    public DateTime  LastActivityAt { get; set; }
    public TripStatus Status { get; set; } = TripStatus.Open;

    public int DurationSec { get; set; }
    public int PointCount  { get; set; }

    // ── Три оценки пробега ────────────────────────────
    public double? DistanceGpsKm   { get; set; }  // Haversine по GPS-точкам
    public double? DistanceOdoKm   { get; set; }  // разность J1939-одометра
    public double? DistanceSpeedKm { get; set; }  // интеграл CAN-скорости по времени

    // ── Скорости и обороты ────────────────────────────
    public double? AvgSpeed { get; set; }
    public double? MaxSpeed { get; set; }
    public double? AvgRpm   { get; set; }
    public double? MaxRpm   { get; set; }

    // ── Топливо ───────────────────────────────────────
    public double? FuelStartPercent { get; set; }
    public double? FuelEndPercent   { get; set; }
    public double? FuelUsedPercent  { get; set; }

    // ── Геометрия ─────────────────────────────────────
    public double? StartLat { get; set; }
    public double? StartLng { get; set; }
    public double? EndLat   { get; set; }
    public double? EndLng   { get; set; }

    /// JSON-массив уникальных DTC-кодов, появившихся в течение поездки.
    public string DtcCodesJson { get; set; } = "[]";

    // ── Одометр J1939 ─────────────────────────────────
    public double? OdoStartKm { get; set; }
    public double? OdoEndKm   { get; set; }
}