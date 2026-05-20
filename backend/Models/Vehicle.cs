namespace VehicleLogger.Api.Models;

public class Vehicle
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string LicensePlate { get; set; } = "";

    public Device? Device { get; set; }

    public int? TenantId { get; set; }
}
