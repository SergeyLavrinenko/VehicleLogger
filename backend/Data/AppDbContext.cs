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
    public DbSet<AiSummary> AiSummaries => Set<AiSummary>();
    public DbSet<Trip> Trips => Set<Trip>();

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
            .HasIndex(t => new { t.DeviceId, t.Timestamp })
            .IsUnique();   // дедупликация по (device, timestamp) при MQTT QoS-1 ретраях

        b.Entity<TelemetryRecord>()
            .HasIndex(t => t.TripId);

        b.Entity<TelemetryRecord>()
            .HasOne(t => t.Device)
            .WithMany()
            .HasForeignKey(t => t.DeviceId)
            .OnDelete(DeleteBehavior.Cascade);

        b.Entity<TelemetryRecord>()
            .HasOne(t => t.Trip)
            .WithMany()
            .HasForeignKey(t => t.TripId)
            .OnDelete(DeleteBehavior.SetNull);

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

        b.Entity<AiSummary>()
            .HasIndex(s => new { s.VehicleId, s.GeneratedAt });

        b.Entity<Trip>()
            .HasIndex(t => new { t.VehicleId, t.StartedAt });
        b.Entity<Trip>()
            .HasIndex(t => new { t.DeviceId, t.Status });

        b.Entity<Trip>()
            .HasOne(t => t.Vehicle)
            .WithMany()
            .HasForeignKey(t => t.VehicleId)
            .OnDelete(DeleteBehavior.SetNull);

        b.Entity<Trip>()
            .HasOne(t => t.Device)
            .WithMany()
            .HasForeignKey(t => t.DeviceId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}