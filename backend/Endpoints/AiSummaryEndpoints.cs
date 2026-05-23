using System.Globalization;
using System.Security.Claims;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using VehicleLogger.Api.Auth;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Models;
using VehicleLogger.Api.Services;

namespace VehicleLogger.Api.Endpoints;

public static class AiSummaryEndpoints
{
    private static readonly TimeSpan FreshFor = TimeSpan.FromMinutes(5);
    private const int TelemetrySampleSize = 60;

    public static void MapAiSummaryEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet ("/api/vehicles/{id:int}/ai-summary",            GetSummary)
           .RequireAuthorization("admin");
        app.MapPost("/api/vehicles/{id:int}/ai-summary/regenerate", Regenerate)
           .RequireAuthorization("admin");
    }

    private static async Task<IResult> GetSummary(
        int id, AppDbContext db, ClaimsPrincipal user, OllamaClient ollama,
        ILogger<OllamaClient> log, CancellationToken ct)
    {
        var tenantId = user.GetTenantId();
        var v = await db.Vehicles.Include(x => x.Device).FirstOrDefaultAsync(x => x.Id == id, ct);
        if (v is null) return Results.NotFound();
        if (tenantId is not null && v.TenantId != tenantId) return Results.NotFound();

        var latest = await db.AiSummaries
            .Where(s => s.VehicleId == id)
            .OrderByDescending(s => s.GeneratedAt)
            .FirstOrDefaultAsync(ct);

        if (latest is not null && DateTime.UtcNow - latest.GeneratedAt < FreshFor)
        {
            return Results.Ok(new
            {
                content = latest.Content,
                generatedAt = latest.GeneratedAt,
                model = latest.Model,
                stale = false,
                cached = true
            });
        }

        try
        {
            var fresh = await GenerateAndSaveAsync(v, db, ollama, ct);
            return Results.Ok(new
            {
                content = fresh.Content,
                generatedAt = fresh.GeneratedAt,
                model = fresh.Model,
                stale = false,
                cached = false
            });
        }
        catch (Exception ex)
        {
            log.LogError(ex, "Не удалось сгенерировать ИИ-сводку для фуры {Id}", id);
            if (latest is not null)
            {
                return Results.Ok(new
                {
                    content = latest.Content,
                    generatedAt = latest.GeneratedAt,
                    model = latest.Model,
                    stale = true,
                    cached = true,
                    error = ex.Message
                });
            }
            return Results.Json(new { error = "ai_unavailable", message = ex.Message }, statusCode: 503);
        }
    }

    private static async Task<IResult> Regenerate(
        int id, AppDbContext db, ClaimsPrincipal user, OllamaClient ollama,
        ILogger<OllamaClient> log, CancellationToken ct)
    {
        var tenantId = user.GetTenantId();
        var v = await db.Vehicles.Include(x => x.Device).FirstOrDefaultAsync(x => x.Id == id, ct);
        if (v is null) return Results.NotFound();
        if (tenantId is not null && v.TenantId != tenantId) return Results.NotFound();

        try
        {
            var fresh = await GenerateAndSaveAsync(v, db, ollama, ct);
            return Results.Ok(new
            {
                content = fresh.Content,
                generatedAt = fresh.GeneratedAt,
                model = fresh.Model,
                stale = false,
                cached = false
            });
        }
        catch (Exception ex)
        {
            log.LogError(ex, "Не удалось пересоздать ИИ-сводку для фуры {Id}", id);
            return Results.Json(new { error = "ai_unavailable", message = ex.Message }, statusCode: 503);
        }
    }

    private static async Task<AiSummary> GenerateAndSaveAsync(
        Vehicle v, AppDbContext db, OllamaClient ollama, CancellationToken ct)
    {
        var prompt = await BuildPromptAsync(v, db, ct);

        var systemMsg =
            "Ты — диагностический ассистент автопарка. На основе телеметрии формируешь предельно краткую " +
            "сводку для администратора на русском.\n\n" +
            "Жёсткий формат ответа (никакого markdown, никаких звёздочек, никаких вступлений, " +
            "только эти строки):\n" +
            "VERDICT: <одна короткая фраза о состоянии, до 90 символов>\n" +
            "RISK: <короткий риск, до 90 символов>\n" +
            "RISK: <короткий риск, до 90 символов>\n" +
            "ACTION: <короткое действие, до 90 символов>\n" +
            "ACTION: <короткое действие, до 90 символов>\n\n" +
            "Допускается 2–3 строки RISK и 2–3 строки ACTION. Если данных мало — так и скажи во VERDICT, " +
            "а в RISK/ACTION предложи что собрать/проверить. Никаких лишних слов, никаких списков-номеров, " +
            "никаких эмодзи.";

        var content = await ollama.ChatAsync(systemMsg, prompt, ct);
        content = content.Trim();
        if (string.IsNullOrEmpty(content))
            throw new InvalidOperationException("Пустой ответ от ИИ.");

        var summary = new AiSummary
        {
            VehicleId   = v.Id,
            TenantId    = v.TenantId,
            GeneratedAt = DateTime.UtcNow,
            Content     = content,
            Model       = ollama.Model
        };
        db.AiSummaries.Add(summary);
        await db.SaveChangesAsync(ct);
        return summary;
    }

    private static async Task<string> BuildPromptAsync(Vehicle v, AppDbContext db, CancellationToken ct)
    {
        var sb = new StringBuilder();
        sb.AppendLine($"Фура: {v.Name} ({v.LicensePlate})");
        if (v.Device is not null)
        {
            sb.AppendLine($"Устройство: {v.Device.SerialNumber}");
            sb.AppendLine($"Последний ping: {Fmt(v.Device.LastPingAt)}");
        }
        else
        {
            sb.AppendLine("Устройство не привязано.");
        }

        if (v.Device is not null)
        {
            var telemetry = await db.Telemetry
                .Where(t => t.VehicleId == v.Id)
                .OrderByDescending(t => t.Timestamp)
                .Take(TelemetrySampleSize)
                .ToListAsync(ct);

            sb.AppendLine();
            sb.AppendLine($"Телеметрия (последние {telemetry.Count} пакетов, новейший первый):");
            if (telemetry.Count == 0)
            {
                sb.AppendLine("— нет данных.");
            }
            else
            {
                var rpms   = telemetry.Where(t => t.Rpm != null).Select(t => t.Rpm!.Value).ToList();
                var speeds = telemetry.Where(t => t.Speed != null).Select(t => t.Speed!.Value).ToList();
                var temps  = telemetry.Where(t => t.CoolantTemp != null).Select(t => t.CoolantTemp!.Value).ToList();
                var oils   = telemetry.Where(t => t.OilPressure != null).Select(t => t.OilPressure!.Value).ToList();
                var fuels  = telemetry.Where(t => t.FuelLevel != null).Select(t => t.FuelLevel!.Value).ToList();
                var volts  = telemetry.Where(t => t.Voltage != null).Select(t => t.Voltage!.Value).ToList();

                sb.AppendLine($"  RPM:           {Range(rpms)}");
                sb.AppendLine($"  Скорость:      {Range(speeds)} км/ч");
                sb.AppendLine($"  Темп. ОЖ:      {Range(temps)} °C");
                sb.AppendLine($"  Давление масла:{Range(oils)} бар");
                sb.AppendLine($"  Топливо:       {Range(fuels)} %");
                sb.AppendLine($"  Напряжение:    {Range(volts)} В");
                sb.AppendLine($"  Период: {Fmt(telemetry.Last().Timestamp)} → {Fmt(telemetry.First().Timestamp)}");

                var dtc = telemetry
                    .Where(t => !string.IsNullOrWhiteSpace(t.DtcCodesJson))
                    .SelectMany(t => ParseDtc(t.DtcCodesJson))
                    .Where(c => !string.IsNullOrWhiteSpace(c))
                    .GroupBy(c => c)
                    .OrderByDescending(g => g.Count())
                    .Select(g => $"{g.Key}×{g.Count()}")
                    .Take(8)
                    .ToList();
                if (dtc.Count > 0)
                    sb.AppendLine($"  DTC-коды: {string.Join(", ", dtc)}");
            }
        }

        var alerts = await db.Alerts
            .Where(a => a.VehicleId == v.Id)
            .OrderByDescending(a => a.Timestamp)
            .Take(10)
            .ToListAsync(ct);
        sb.AppendLine();
        sb.AppendLine($"Алерты (последние {alerts.Count}):");
        if (alerts.Count == 0) sb.AppendLine("— нет.");
        else foreach (var a in alerts)
            sb.AppendLine($"  [{a.Severity}] {Fmt(a.Timestamp)} — {a.Description}");

        var refuels = await db.Refuels
            .Where(r => r.VehicleId == v.Id)
            .OrderByDescending(r => r.Timestamp)
            .Take(5)
            .ToListAsync(ct);
        sb.AppendLine();
        sb.AppendLine($"Последние заправки ({refuels.Count}):");
        if (refuels.Count == 0) sb.AppendLine("— нет.");
        else foreach (var r in refuels)
            sb.AppendLine($"  {Fmt(r.Timestamp)} — {r.Liters:F1} л, {r.Cost:F0} ₽");

        sb.AppendLine();
        sb.AppendLine("Дай сводку строго в указанной структуре.");
        return sb.ToString();
    }

    private static string Fmt(DateTime? dt) =>
        dt is null ? "—" : dt.Value.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture) + " UTC";

    private static string Fmt(DateTime dt) => Fmt((DateTime?)dt);

    private static string Show<T>(T? v) where T : struct => v?.ToString() ?? "—";

    private static string Range(IReadOnlyList<int> xs)
    {
        if (xs.Count == 0) return "нет";
        var avg = xs.Average();
        return $"min={xs.Min()} avg={avg:F0} max={xs.Max()} (n={xs.Count})";
    }

    private static string Range(IReadOnlyList<double> xs)
    {
        if (xs.Count == 0) return "нет";
        var avg = xs.Average();
        return $"min={xs.Min():F2} avg={avg:F2} max={xs.Max():F2} (n={xs.Count})";
    }

    private static string[] ParseDtc(string json)
    {
        if (string.IsNullOrWhiteSpace(json)) return Array.Empty<string>();
        try { return JsonSerializer.Deserialize<string[]>(json) ?? Array.Empty<string>(); }
        catch { return Array.Empty<string>(); }
    }
}
