namespace VehicleLogger.Api.Dtos;

public class TelemetryRequest
{
    public string DeviceId { get; set; } = "";
    public DateTime Timestamp { get; set; }
    public TelemetryData Data { get; set; } = new();
    /// GPS-снимок. Отсутствует целиком, если фикс старый или приёмник не дал данных.
    public GpsData? Gps { get; set; }
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

    /// Одометр J1939 PGN 65248, км. Передаётся отдельно от gps.speed —
    /// нужен для альтернативной оценки пробега поездки.
    public double? Odometer { get; set; }
}