namespace VehicleLogger.Api.Models;

public enum DeviceStatus
{
    Manufactured = 0,   // изготовлено, ещё ни к кому не привязано
    Claimed      = 1,   // только что привязано админом, апи-ключ выпущен, устройство ещё не забрало
    Active       = 2,   // забрало ключ через /provision, шлёт телеметрию
    Deactivated  = 3    // отключено (потеряно/продано/скомпрометировано)
}

public class Device
{
    public int Id { get; set; }
    public string SerialNumber { get; set; } = "";

    /// SHA-256 hex от полного секрета устройства (256-битный секрет с завода).
    public string SecretHash { get; set; } = "";

    /// Первые 8 hex-символов plaintext-секрета. Печатается на QR.
    /// Используется в /api/devices/claim для подтверждения физического владения.
    public string SecretFragment { get; set; } = "";

    public DeviceStatus Status { get; set; } = DeviceStatus.Manufactured;

    /// API-ключ (plaintext). null до claim. Заполняется при claim, очищается при unclaim/rotate.
    public string? ApiKey { get; set; }

    public bool IsOnline { get; set; }
    public DateTime? LastPingAt { get; set; }
    public DateTime? ClaimedAt { get; set; }

    public int? VehicleId { get; set; }
    public Vehicle? Vehicle { get; set; }

    public int? TenantId { get; set; }
}
