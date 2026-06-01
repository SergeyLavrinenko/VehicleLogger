using System.Security.Cryptography;
using System.Text;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Data;

public static class DbSeeder
{
    /// Telegram ID демо-водителя — связывает Telegram-бот с этим пользователем.
    private const long DemoDriverTelegramId = 1481060176;

    public static async Task SeedAsync(AppDbContext db)
    {
        // 1. Базовые тестовые фуры + устройства со статичным ApiKey
        //    (для совместимости с device-sim).
        if (!await db.Vehicles.AnyAsync())
        {
            var v1 = new Vehicle { Name = "Фура №1", LicensePlate = "А123БВ77" };
            var v2 = new Vehicle { Name = "Фура №2", LicensePlate = "К456МН77" };
            db.Vehicles.AddRange(v1, v2);
            await db.SaveChangesAsync();

            db.Devices.AddRange(
                new Device
                {
                    SerialNumber = "VL-A3F82B01",
                    ApiKey = "dev-key-001",
                    Status = DeviceStatus.Active,
                    VehicleId = v1.Id
                },
                new Device
                {
                    SerialNumber = "VL-A3F82B02",
                    ApiKey = "dev-key-002",
                    Status = DeviceStatus.Active,
                    VehicleId = v2.Id
                });

            db.Users.AddRange(
                new User
                {
                    Role = UserRole.Admin,
                    Email = "admin@vl.local",
                    Name = "Admin",
                    PasswordHash = PasswordHasher.Hash("admin1234")
                },
                new User
                {
                    Role = UserRole.Driver,
                    Email = "driver@vl.local",
                    Name = "Тестовый водитель",
                    PasswordHash = PasswordHasher.Hash("driver1234"),
                    VehicleId = v1.Id,                 // Фура №1
                    TelegramId = DemoDriverTelegramId   // привязка к Telegram-боту
                });

            await db.SaveChangesAsync();
        }
        else
        {
            // На существующей БД — добавить admin/driver если их нет
            await EnsureAdminAsync(db);
        }

        // Демо-водитель (User Id=2): гарантируем привязку к Фуре №1
        // и Telegram ID. Идемпотентно — работает и на свежей, и на уже
        // существующей БД (volume мог остаться от прошлых запусков).
        await EnsureDemoDriverAsync(db);

        // 2. Устройства для тестирования provisioning flow.
        //    Status = Manufactured. Секреты известны Сергею (см. инструкцию).
        await SeedProvisioningDeviceAsync(db,
            serial: "VL-PROV-001",
            secret: "a1b2c3d40000000000000000000000000000000000000000000000000000abcd");
        await SeedProvisioningDeviceAsync(db,
            serial: "VL-PROV-002",
            secret: "deadbeef0000000000000000000000000000000000000000000000000000feed");

        await db.SaveChangesAsync();
    }

    private static async Task EnsureAdminAsync(AppDbContext db)
    {
        if (!await db.Users.AnyAsync(u => u.Email == "admin@vl.local"))
        {
            db.Users.Add(new User
            {
                Role = UserRole.Admin,
                Email = "admin@vl.local",
                Name = "Admin",
                PasswordHash = PasswordHasher.Hash("admin1234")
            });
            await db.SaveChangesAsync();
        }
    }

    /// Гарантирует, что демо-водитель driver@vl.local (в стандартном
    /// сидинге это User Id=2) привязан к Фуре №1 и имеет Telegram ID.
    /// Если водителя нет — создаёт его.
    private static async Task EnsureDemoDriverAsync(AppDbContext db)
    {
        var driver = await db.Users.FirstOrDefaultAsync(u => u.Email == "driver@vl.local");

        // VehicleId должен быть = 1 (Фура №1). Берём фуру с Id=1, если она есть.
        var vehicle1Exists = await db.Vehicles.AnyAsync(v => v.Id == 1);

        if (driver is null)
        {
            var fallbackVehicleId = await db.Vehicles
                .OrderBy(v => v.Id)
                .Select(v => (int?)v.Id)
                .FirstOrDefaultAsync();

            db.Users.Add(new User
            {
                Role = UserRole.Driver,
                Email = "driver@vl.local",
                Name = "Тестовый водитель",
                PasswordHash = PasswordHasher.Hash("driver1234"),
                VehicleId = vehicle1Exists ? 1 : fallbackVehicleId,
                TelegramId = DemoDriverTelegramId
            });
        }
        else
        {
            // Принудительно выставляем требуемые значения.
            if (vehicle1Exists) driver.VehicleId = 1;
            driver.TelegramId = DemoDriverTelegramId;
        }

        await db.SaveChangesAsync();
    }

    private static async Task SeedProvisioningDeviceAsync(AppDbContext db, string serial, string secret)
    {
        if (await db.Devices.AnyAsync(d => d.SerialNumber == serial)) return;

        db.Devices.Add(new Device
        {
            SerialNumber = serial,
            SecretHash = Sha256Hex(secret),
            SecretFragment = secret[..8],
            Status = DeviceStatus.Manufactured,
            ApiKey = $"unclaimed:{serial}"   // плейсхолдер: NOT NULL + UNIQUE indexes остаются
        });
    }

    public static string Sha256Hex(string input)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(input));
        var sb = new StringBuilder(bytes.Length * 2);
        foreach (var b in bytes) sb.Append(b.ToString("x2"));
        return sb.ToString();
    }
}