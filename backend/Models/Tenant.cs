namespace VehicleLogger.Api.Models;

public class Tenant
{
    public int Id { get; set; }
    /// Субдомен компании, lowercase, RFC 1035: ^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])?$
    public string Subdomain { get; set; } = "";
    public string Name { get; set; } = "";
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
