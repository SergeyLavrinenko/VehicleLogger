namespace VehicleLogger.Api.Dtos;

public class TelemetryRequest
{
    public string DeviceId { get; set; } = "";
    public DateTime Timestamp { get; set; }
    public TelemetryData Data { get; set; } = new();
}

public class TelemetryData
{
    public int? Rpm { get; set; }
    public double? Speed { get; set; }
    public double? CoolantTemp { get; set; }
    public double? OilPressure { get; set; }
    public double? FuelLevel { get; set; }
    public double? Voltage { get; set; }
    public List<string>? DtcCodes { get; set; }
}
