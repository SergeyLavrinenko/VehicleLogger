using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<Vehicle> Vehicles => Set<Vehicle>();
    public DbSet<Device> Devices => Set<Device>();
    public DbSet<TelemetryRecord> Telemetry => Set<TelemetryRecord>();
    public DbSet<User> Users => Set<User>();
    public DbSet<Refuel> Refuels => Set<Refuel>();
    public DbSet<Alert> Alerts => Set<Alert>();
    public DbSet<EnrollmentCode> EnrollmentCodes => Set<EnrollmentCode>();
    public DbSet<Tenant> Tenants => Set<Tenant>();

    protected override void ConfigureConventions(ModelConfigurationBuilder cb)
    {
        cb.Properties<DateTime>().HaveConversion(typeof(UtcDateTimeConverter));
        cb.Properties<DateTime?>().HaveConversion(typeof(UtcNullableDateTimeConverter));
    }

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Device>()
            .HasIndex(d => d.SerialNumber).IsUnique();
        b.Entity<Device>()
            .HasIndex(d => d.ApiKey).IsUnique();

        b.Entity<Device>()
            .HasOne(d => d.Vehicle)
            .WithOne(v => v.Device!)
            .HasForeignKey<Device>(d => d.VehicleId)
            .OnDelete(DeleteBehavior.SetNull);

        b.Entity<TelemetryRecord>()
            .HasIndex(t => new { t.DeviceId, t.Timestamp });

        b.Entity<TelemetryRecord>()
            .HasOne(t => t.Device)
            .WithMany()
            .HasForeignKey(t => t.DeviceId)
            .OnDelete(DeleteBehavior.Cascade);

        b.Entity<Alert>()
            .HasIndex(a => new { a.VehicleId, a.Timestamp });

        b.Entity<Refuel>()
            .HasIndex(r => new { r.VehicleId, r.Timestamp });

        b.Entity<EnrollmentCode>()
            .HasIndex(c => c.CodeHash);
        b.Entity<EnrollmentCode>()
            .HasIndex(c => c.UsedAt);

        b.Entity<Tenant>()
            .HasIndex(t => t.Subdomain).IsUnique();
    }
}
