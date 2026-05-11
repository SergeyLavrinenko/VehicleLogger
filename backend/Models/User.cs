namespace VehicleLogger.Api.Models;

public enum UserRole { Admin, Driver }

public class User
{
    public int Id { get; set; }
    public UserRole Role { get; set; }

    public string Email { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public string? Name { get; set; }

    public long? TelegramId { get; set; }

    public int? VehicleId { get; set; }
    public Vehicle? Vehicle { get; set; }

    public int? TenantId { get; set; }
}
