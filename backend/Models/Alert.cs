namespace VehicleLogger.Api.Models;

public enum AlertSeverity { Info, Warning, Critical }

public class Alert
{
    public int Id { get; set; }
    public int VehicleId { get; set; }
    public DateTime Timestamp { get; set; }
    public AlertSeverity Severity { get; set; }
    public string Description { get; set; } = "";
    public string? Recommendation { get; set; }
    public bool IsRead { get; set; }
}
