namespace VehicleLogger.Api.Models;

public class TelemetryRecord
{
    public long Id { get; set; }

    public int DeviceId { get; set; }
    public Device? Device { get; set; }

    public DateTime Timestamp { get; set; }

    public int? Rpm { get; set; }
    public double? Speed { get; set; }
    public double? CoolantTemp { get; set; }
    public double? OilPressure { get; set; }
    public double? FuelLevel { get; set; }
    public double? Voltage { get; set; }

    /// JSON-массив строк (DTC-коды OBD-II, например ["P0301"]).
    public string DtcCodesJson { get; set; } = "[]";

    public DateTime ReceivedAt { get; set; }
}
