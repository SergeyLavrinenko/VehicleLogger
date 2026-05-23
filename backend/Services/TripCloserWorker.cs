using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Services;

/// Фоновый воркер, закрывающий поездки при обрыве связи: поездки со статусом
/// Open и LastActivityAt старше N минут (нет новых пакетов) закрываются по
/// последнему известному пакету.
public class TripCloserWorker : BackgroundService
{
    private const int InactivityMinutes = 15;
    private static readonly TimeSpan TickInterval = TimeSpan.FromMinutes(1);

    private readonly IServiceProvider _sp;
    private readonly ILogger<TripCloserWorker> _log;

    public TripCloserWorker(IServiceProvider sp, ILogger<TripCloserWorker> log)
    {
        _sp = sp;
        _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _log.LogInformation("TripCloserWorker started; tick every {Tick}", TickInterval);
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await TickAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _log.LogError(ex, "TripCloserWorker tick failed");
            }
            try { await Task.Delay(TickInterval, stoppingToken); }
            catch (TaskCanceledException) { break; }
        }
    }

    private async Task TickAsync(CancellationToken ct)
    {
        using var scope = _sp.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var stats = scope.ServiceProvider.GetRequiredService<TripStatsCalculator>();

        var deadline = DateTime.UtcNow.AddMinutes(-InactivityMinutes);
        var stale = await db.Trips
            .Where(t => t.Status == TripStatus.Open && t.LastActivityAt < deadline)
            .ToListAsync(ct);

        if (stale.Count == 0) return;

        foreach (var trip in stale)
        {
            trip.Status  = TripStatus.Closed;
            trip.EndedAt = trip.LastActivityAt;
            await stats.RecalculateAsync(trip);
            _log.LogInformation("Trip {TripId} (device {DeviceId}) closed by timeout, ended at {EndedAt}",
                trip.Id, trip.DeviceId, trip.EndedAt);
        }
        await db.SaveChangesAsync(ct);
    }
}