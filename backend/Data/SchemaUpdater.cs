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
            "CREATE INDEX IF NOT EXISTS IX_AiSummaries_VehicleId_GeneratedAt ON AiSummaries(VehicleId, GeneratedAt)"
        };
        foreach (var sql in statements)
        {
            try { await db.Database.ExecuteSqlRawAsync(sql); }
            catch { /* колонка уже есть — игнор */ }
        }
    }
}
