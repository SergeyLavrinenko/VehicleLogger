using Microsoft.EntityFrameworkCore;

namespace VehicleLogger.Api.Data;

/// Идемпотентное добавление колонок в существующую БД (без EF Migrations).
/// SQLite — каждый ALTER TABLE ADD COLUMN либо проходит, либо кидает,
/// если колонка уже есть. Ловим и игнорируем.
public static class SchemaUpdater
{
    public static async Task UpdateAsync(AppDbContext db)
    {
        var statements = new[]
        {
            "ALTER TABLE Devices ADD COLUMN SecretHash TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE Devices ADD COLUMN SecretFragment TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE Devices ADD COLUMN Status INTEGER NOT NULL DEFAULT 2",   // существующие = Active
            "ALTER TABLE Devices ADD COLUMN ClaimedAt TEXT NULL",
            "ALTER TABLE Users ADD COLUMN Email TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE Users ADD COLUMN PasswordHash TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE Users ADD COLUMN Name TEXT NULL",
            // EnrollmentCodes — таблица создаётся EnsureCreated, но если БД старая — добавим вручную
            @"CREATE TABLE IF NOT EXISTS EnrollmentCodes (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                CodeHash TEXT NOT NULL DEFAULT '',
                CodePrefix TEXT NOT NULL DEFAULT '',
                ExpiresAt TEXT NOT NULL,
                UsedAt TEXT NULL,
                UsedByDeviceId INTEGER NULL,
                CreatedByUserId INTEGER NULL,
                Label TEXT NULL,
                CreatedAt TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
            )",
            "CREATE INDEX IF NOT EXISTS IX_EnrollmentCodes_CodeHash ON EnrollmentCodes(CodeHash)",
            "CREATE INDEX IF NOT EXISTS IX_EnrollmentCodes_UsedAt ON EnrollmentCodes(UsedAt)",
            // Tenants и TenantId-колонки
            @"CREATE TABLE IF NOT EXISTS Tenants (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                Subdomain TEXT NOT NULL DEFAULT '',
                Name TEXT NOT NULL DEFAULT '',
                CreatedAt TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
            )",
            "CREATE UNIQUE INDEX IF NOT EXISTS IX_Tenants_Subdomain ON Tenants(Subdomain)",
            "ALTER TABLE Devices ADD COLUMN TenantId INTEGER NULL",
            "ALTER TABLE Vehicles ADD COLUMN TenantId INTEGER NULL",
            "ALTER TABLE Users ADD COLUMN TenantId INTEGER NULL",
            "ALTER TABLE EnrollmentCodes ADD COLUMN TenantId INTEGER NULL",
            @"CREATE TABLE IF NOT EXISTS AiSummaries (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                VehicleId INTEGER NOT NULL,
                TenantId INTEGER NULL,
                GeneratedAt TEXT NOT NULL,
                Content TEXT NOT NULL DEFAULT '',
                Model TEXT NULL
            )",
            "CREATE INDEX IF NOT EXISTS IX_AiSummaries_VehicleId_GeneratedAt ON AiSummaries(VehicleId, GeneratedAt)",

            // ── GPS + поездки ────────────────────────────────────────────
            "ALTER TABLE Telemetry ADD COLUMN Lat REAL NULL",
            "ALTER TABLE Telemetry ADD COLUMN Lng REAL NULL",
            "ALTER TABLE Telemetry ADD COLUMN Altitude REAL NULL",
            "ALTER TABLE Telemetry ADD COLUMN GpsSpeed REAL NULL",
            "ALTER TABLE Telemetry ADD COLUMN Course REAL NULL",
            "ALTER TABLE Telemetry ADD COLUMN Satellites INTEGER NULL",
            "ALTER TABLE Telemetry ADD COLUMN GpsFix INTEGER NULL",
            "ALTER TABLE Telemetry ADD COLUMN TripId INTEGER NULL",
            "ALTER TABLE Telemetry ADD COLUMN OdometerKm REAL NULL",
            "CREATE INDEX IF NOT EXISTS IX_Telemetry_TripId ON Telemetry(TripId)",
            // VehicleId/TenantId snapshot в TelemetryRecord — чтобы при перепривязке
            // устройства старые пакеты оставались у прежнего тенанта/фуры.
            "ALTER TABLE Telemetry ADD COLUMN VehicleId INTEGER NULL",
            "ALTER TABLE Telemetry ADD COLUMN TenantId INTEGER NULL",
            "CREATE INDEX IF NOT EXISTS IX_Telemetry_VehicleId_Timestamp ON Telemetry(VehicleId, Timestamp)",
            // Однократный backfill: проставляем VehicleId/TenantId по ТЕКУЩЕМУ
            // Device.VehicleId / Device.TenantId. После этого изменения Device.VehicleId
            // на новые пакеты не повлияют.
            "UPDATE Telemetry SET VehicleId = (SELECT VehicleId FROM Devices WHERE Devices.Id = Telemetry.DeviceId) WHERE VehicleId IS NULL",
            "UPDATE Telemetry SET TenantId  = (SELECT TenantId  FROM Devices WHERE Devices.Id = Telemetry.DeviceId) WHERE TenantId  IS NULL",


            @"CREATE TABLE IF NOT EXISTS Trips (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                VehicleId INTEGER NULL,
                DeviceId INTEGER NOT NULL,
                TenantId INTEGER NULL,
                StartedAt TEXT NOT NULL,
                EndedAt TEXT NULL,
                LastActivityAt TEXT NOT NULL,
                Status INTEGER NOT NULL DEFAULT 0,
                DurationSec INTEGER NOT NULL DEFAULT 0,
                PointCount INTEGER NOT NULL DEFAULT 0,
                DistanceGpsKm REAL NULL,
                DistanceOdoKm REAL NULL,
                DistanceSpeedKm REAL NULL,
                AvgSpeed REAL NULL,
                MaxSpeed REAL NULL,
                AvgRpm REAL NULL,
                MaxRpm REAL NULL,
                FuelStartPercent REAL NULL,
                FuelEndPercent REAL NULL,
                FuelUsedPercent REAL NULL,
                StartLat REAL NULL,
                StartLng REAL NULL,
                EndLat REAL NULL,
                EndLng REAL NULL,
                DtcCodesJson TEXT NOT NULL DEFAULT '[]',
                OdoStartKm REAL NULL,
                OdoEndKm REAL NULL
            )",
            "CREATE INDEX IF NOT EXISTS IX_Trips_VehicleId_StartedAt ON Trips(VehicleId, StartedAt)",
            "CREATE INDEX IF NOT EXISTS IX_Trips_DeviceId_Status ON Trips(DeviceId, Status)"
        };
        foreach (var sql in statements)
        {
            try { await db.Database.ExecuteSqlRawAsync(sql); }
            catch { /* колонка уже есть — игнор */ }
        }
    }
}