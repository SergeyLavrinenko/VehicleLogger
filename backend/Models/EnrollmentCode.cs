namespace VehicleLogger.Api.Models;

/// Одноразовый 6-значный код, выдаваемый админом установщику.
/// Установщик вводит код в captive-portal ESP32 → ESP шлёт его в /api/devices/enroll.
public class EnrollmentCode
{
    public int Id { get; set; }

    /// SHA-256 hex от plaintext-кода. Plaintext возвращается админу один раз при создании.
    public string CodeHash { get; set; } = "";

    /// Префикс plaintext-кода (первые 2 символа), для идентификации в списке без раскрытия секрета.
    public string CodePrefix { get; set; } = "";

    public DateTime ExpiresAt { get; set; }
    public DateTime? UsedAt { get; set; }
    public int? UsedByDeviceId { get; set; }

    public int? CreatedByUserId { get; set; }
    public string? Label { get; set; }

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public int? TenantId { get; set; }
}
