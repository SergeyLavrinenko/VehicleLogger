namespace VehicleLogger.Api.Models;

public class Refuel
{
    public int Id { get; set; }
    public int VehicleId { get; set; }
    public int? UserId { get; set; }
    public DateTime Timestamp { get; set; }
    public double Liters { get; set; }
    public double Cost { get; set; }
}
