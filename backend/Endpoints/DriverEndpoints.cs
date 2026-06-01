using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Endpoints;

public static class DriverEndpoints
{
    public static void MapDriverEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/drivers/register", Register);
        app.MapPost("/api/refuel",            AddRefuel);
        app.MapGet ("/api/status",            GetStatus);
        app.MapGet ("/api/alerts",            GetAlerts);
    }

    public record RegisterRequest(long TelegramId);
    public record RefuelRequest(long TelegramId, double Liters, double Price);

    // Находит уже существующего водителя по telegramId.
    private static async Task<User?> FindDriver(AppDbContext db, long tgId) =>
        await db.Users.FirstOrDefaultAsync(u =>
            u.TelegramId == tgId && u.Role == UserRole.Driver);

    private static async Task<IResult> Register(RegisterRequest req, AppDbContext db)
    {
        // Регистрация: помечаем существующего driver-пользователя его telegramId.
        // В реальной системе привязку telegramId↔водитель лучше делать
        // через одноразовый код из веб-панели, а не доверять любому /start.
        var user = await FindDriver(db, req.TelegramId);
        if (user is null)
            return Results.Json(new { error = "driver_not_found" }, statusCode: 404);
        return Results.Ok(new { ok = true, driverId = user.Id });
    }

    private static async Task<IResult> AddRefuel(RefuelRequest req, AppDbContext db)
    {
        var user = await FindDriver(db, req.TelegramId);
        if (user?.VehicleId is null)
            return Results.Json(new { error = "no_vehicle" }, statusCode: 404);

        db.Refuels.Add(new Refuel {
            VehicleId = user.VehicleId.Value,
            UserId    = user.Id,
            Timestamp = DateTime.UtcNow,
            Liters    = req.Liters,
            Cost      = req.Price          // bot шлёт "price" → пишем в Cost
        });
        await db.SaveChangesAsync();
        return Results.Ok(new { ok = true });
    }

    private static async Task<IResult> GetStatus(long telegramId, AppDbContext db)
    {
        var user = await FindDriver(db, telegramId);
        if (user?.VehicleId is null) return Results.Ok(new { temp = "N/A", rpm = "N/A", fuel = "N/A" });

        var v = await db.Vehicles.Include(x => x.Device)
                                 .FirstOrDefaultAsync(x => x.Id == user.VehicleId);
        var t = v?.Device == null ? null : await db.Telemetry
            .Where(x => x.DeviceId == v.Device.Id)
            .OrderByDescending(x => x.Timestamp).FirstOrDefaultAsync();

        return Results.Ok(new {
            temp = (object?)t?.CoolantTemp ?? "N/A",
            rpm  = (object?)t?.Rpm         ?? "N/A",
            fuel = (object?)t?.FuelLevel   ?? "N/A"
        });
    }

    private static async Task<IResult> GetAlerts(long telegramId, AppDbContext db)
    {
        var user = await FindDriver(db, telegramId);
        if (user?.VehicleId is null) return Results.Ok(Array.Empty<string>());

        var alerts = await db.Alerts
            .Where(a => a.VehicleId == user.VehicleId)
            .OrderByDescending(a => a.Timestamp).Take(10)
            .Select(a => a.Description).ToListAsync();
        return Results.Ok(alerts);     // список строк — как ждёт бот
    }
}