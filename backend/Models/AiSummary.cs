namespace VehicleLogger.Api.Models;

public class AiSummary
{
    public int Id { get; set; }
    public int VehicleId { get; set; }
    public int? TenantId { get; set; }
    public DateTime GeneratedAt { get; set; }
    public string Content { get; set; } = "";
    public string? Model { get; set; }
}
