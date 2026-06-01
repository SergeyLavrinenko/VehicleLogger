using System.Globalization;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Dtos;
using VehicleLogger.Api.Models;
using VehicleLogger.Api.Services;

namespace VehicleLogger.Api.Endpoints;

public static class DeviceEndpoints
{
    private const string DeviceKeyHeader = "X-Device-Key";
    private const string AuthHeader      = "Authorization";
    private const string BearerPrefix    = "Bearer ";

    /// Окно антиспама: повторный алерт с тем же описанием по одной и той же
    /// фуре не создаётся, пока не пройдёт это время. Иначе симулятор,
    /// шлющий пакет каждые 5 секунд, наплодил бы сотни одинаковых алертов.
    private static readonly TimeSpan AlertCooldown = TimeSpan.FromMinutes(10);

    public static void MapDeviceEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/telemetry", HandleTelemetry);
        app.MapPost("/api/device/ping", HandlePing);
    }

    private static async Task<IResult> HandleTelemetry(
        HttpContext ctx,
        TelemetryRequest req,
        AppDbContext db,
        ILoggerFactory loggerFactory,
        TelegramNotifier notifier)
    {
        var log = loggerFactory.CreateLogger("Telemetry");

        var device = await AuthenticateDeviceAsync(ctx, req.DeviceId, db);
        if (device is null)
        {
            log.LogWarning("Unauthorized telemetry from deviceId={DeviceId}", req.DeviceId);
            return Results.Unauthorized();
        }

        if (req.Timestamp == default)
            return Results.BadRequest(new { error = "timestamp_required" });

        var record = new TelemetryRecord
        {
            DeviceId = device.Id,
            Timestamp = req.Timestamp.ToUniversalTime(),
            Rpm = req.Data.Rpm,
            Speed = req.Data.Speed,
            CoolantTemp = req.Data.CoolantTemp,
            OilPressure = req.Data.OilPressure,
            FuelLevel = req.Data.FuelLevel,
            Voltage = req.Data.Voltage,
            DtcCodesJson = JsonSerializer.Serialize(req.Data.DtcCodes ?? new List<string>()),
            ReceivedAt = DateTime.UtcNow
        };

        db.Telemetry.Add(record);

        device.IsOnline = true;
        device.LastPingAt = DateTime.UtcNow;

        await db.SaveChangesAsync();

        log.LogInformation(
            "Telemetry stored: device={Serial} ts={Ts} rpm={Rpm} speed={Speed}",
            device.SerialNumber, record.Timestamp, record.Rpm, record.Speed);

        // Разбор телеметрии на предмет аварийных значений → запись в Alerts
        // и уведомление водителя в Telegram.
        await EvaluateAlertsAsync(device, record, db, log, notifier);

        return Results.Ok(new { stored = true, id = record.Id });
    }

    private static async Task<IResult> HandlePing(
        HttpContext ctx,
        PingRequest req,
        AppDbContext db)
    {
        var device = await AuthenticateDeviceAsync(ctx, req.DeviceId, db);
        if (device is null) return Results.Unauthorized();

        device.IsOnline = true;
        device.LastPingAt = DateTime.UtcNow;
        await db.SaveChangesAsync();

        return Results.Ok();
    }

    // ---------------------------------------------------------------------
    //  Генерация алертов из телеметрии
    // ---------------------------------------------------------------------

    /// Прогоняет один пакет телеметрии через пороги, создаёт записи Alert
    /// для привязанной к устройству фуры и уведомляет её водителя.
    /// Каждый «вид» алерта имеет фиксированное Description — по нему же
    /// идёт антиспам-дедупликация.
    private static async Task EvaluateAlertsAsync(
        Device device, TelemetryRecord t, AppDbContext db, ILogger log, TelegramNotifier notifier)
    {
        // Алерты привязаны к фуре. Если устройство ни к чему не прикреплено — выходим.
        if (device.VehicleId is not int vehicleId) return;

        var candidates = new List<(AlertSeverity Severity, string Description, string Recommendation)>();

        // 1. Температура охлаждающей жидкости (anomaly=overheat в симуляторе).
        if (t.CoolantTemp is double temp)
        {
            if (temp >= 104)
                candidates.Add((
                    AlertSeverity.Critical,
                    "Критический перегрев двигателя",
                    $"Температура охлаждающей жидкости {Num(temp)} °C. " +
                    "Немедленно остановите ТС и заглушите двигатель."));
            else if (temp >= 99)
                candidates.Add((
                    AlertSeverity.Warning,
                    "Повышенная температура двигателя",
                    $"Температура охлаждающей жидкости {Num(temp)} °C при норме до 95 °C. " +
                    "Снизьте нагрузку, проверьте систему охлаждения."));
        }

        // 2. Давление масла (anomaly=oilpressure в симуляторе).
        if (t.OilPressure is double oil && oil <= 1.5)
            candidates.Add((
                AlertSeverity.Critical,
                "Низкое давление масла",
                $"Давление масла {Num(oil)} бар при норме 2.0-4.5 бар. " +
                "Риск повреждения двигателя — остановите ТС."));

        // 3. Напряжение бортовой сети.
        if (t.Voltage is double v && v < 12.0)
            candidates.Add((
                AlertSeverity.Warning,
                "Низкое напряжение бортовой сети",
                $"Напряжение {Num(v)} В. Проверьте генератор и аккумулятор."));

        // 4. Коды неисправностей OBD-II (anomaly=dtc в симуляторе).
        var dtc = ParseDtc(t.DtcCodesJson);
        if (dtc.Count > 0)
            candidates.Add((
                AlertSeverity.Warning,
                "Обнаружены коды неисправностей OBD-II",
                $"Считаны коды: {string.Join(", ", dtc)}. Требуется диагностика."));

        if (candidates.Count == 0) return;

        // Антиспам: какие описания уже срабатывали по этой фуре за окно AlertCooldown.
        var cutoff = DateTime.UtcNow - AlertCooldown;
        var recentDescriptions = await db.Alerts
            .Where(a => a.VehicleId == vehicleId && a.Timestamp >= cutoff)
            .Select(a => a.Description)
            .ToListAsync();

        var created = new List<Alert>();
        foreach (var c in candidates)
        {
            if (recentDescriptions.Contains(c.Description)) continue;

            var alert = new Alert
            {
                VehicleId      = vehicleId,
                Timestamp      = DateTime.UtcNow,
                Severity       = c.Severity,
                Description    = c.Description,
                Recommendation = c.Recommendation,
                IsRead         = false
            };
            db.Alerts.Add(alert);
            created.Add(alert);

            // Чтобы не задублировать в рамках одного же пакета.
            recentDescriptions.Add(c.Description);

            log.LogInformation("Alert raised: vehicle={Vid} [{Sev}] {Desc}",
                vehicleId, c.Severity, c.Description);
        }

        if (created.Count == 0) return;

        await db.SaveChangesAsync();

        // Свежесозданные алерты → пуш водителю фуры в Telegram.
        await NotifyDriverAsync(vehicleId, created, db, log, notifier);
    }

    /// Находит водителя фуры с привязанным Telegram ID и отправляет ему
    /// сообщение по каждому новому алерту.
    private static async Task NotifyDriverAsync(
        int vehicleId, List<Alert> alerts, AppDbContext db, ILogger log, TelegramNotifier notifier)
    {
        if (!notifier.Enabled) return;

        var driver = await db.Users.FirstOrDefaultAsync(u =>
            u.Role == UserRole.Driver
            && u.VehicleId == vehicleId
            && u.TelegramId != null);

        if (driver?.TelegramId is not long telegramId)
        {
            log.LogInformation(
                "У фуры {Vid} нет водителя с Telegram ID — уведомление не отправлено.", vehicleId);
            return;
        }

        var vehicle = await db.Vehicles.FirstOrDefaultAsync(v => v.Id == vehicleId);
        var vehicleLabel = vehicle is null
            ? $"фура #{vehicleId}"
            : $"{vehicle.Name} ({vehicle.LicensePlate})";

        foreach (var a in alerts)
            await notifier.NotifyAsync(telegramId, FormatAlertMessage(vehicleLabel, a));
    }

    /// Текст сообщения для водителя.
    private static string FormatAlertMessage(string vehicleLabel, Alert a)
    {
        var icon = a.Severity switch
        {
            AlertSeverity.Critical => "🔴",
            AlertSeverity.Warning  => "🟠",
            _                      => "🔵"
        };

        var sb = new StringBuilder();
        sb.Append(icon).Append(' ').AppendLine(a.Description);
        sb.Append("🚛 ").AppendLine(vehicleLabel);
        if (!string.IsNullOrWhiteSpace(a.Recommendation))
            sb.Append(a.Recommendation);
        return sb.ToString().TrimEnd();
    }

    /// Форматирование числа с точкой-разделителем, независимо от культуры сервера.
    private static string Num(double value) =>
        value.ToString("0.##", CultureInfo.InvariantCulture);

    /// Безопасный разбор JSON-массива DTC-кодов из TelemetryRecord.DtcCodesJson.
    private static List<string> ParseDtc(string json)
    {
        if (string.IsNullOrWhiteSpace(json)) return new();
        try
        {
            return JsonSerializer.Deserialize<List<string>>(json) ?? new();
        }
        catch
        {
            return new();
        }
    }

    // ---------------------------------------------------------------------

    private static async Task<Device?> AuthenticateDeviceAsync(
        HttpContext ctx, string deviceId, AppDbContext db)
    {
        var key = ExtractDeviceKey(ctx);
        if (string.IsNullOrWhiteSpace(key) || string.IsNullOrWhiteSpace(deviceId))
            return null;

        if (!ProvisioningEndpoints.IsRealKey(key)) return null;

        var device = await db.Devices.FirstOrDefaultAsync(d => d.ApiKey == key);
        if (device is null) return null;
        if (!string.Equals(device.SerialNumber, deviceId, StringComparison.Ordinal))
            return null;

        return device;
    }

    /// Принимаем ключ либо в `X-Device-Key` (legacy для device-sim),
    /// либо в `Authorization: Bearer <key>` (новая прошивка).
    private static string? ExtractDeviceKey(HttpContext ctx)
    {
        if (ctx.Request.Headers.TryGetValue(DeviceKeyHeader, out var k) && !string.IsNullOrWhiteSpace(k))
            return k.ToString();

        if (ctx.Request.Headers.TryGetValue(AuthHeader, out var auth))
        {
            var s = auth.ToString();
            if (s.StartsWith(BearerPrefix, StringComparison.OrdinalIgnoreCase))
                return s[BearerPrefix.Length..].Trim();
        }
        return null;
    }
}
