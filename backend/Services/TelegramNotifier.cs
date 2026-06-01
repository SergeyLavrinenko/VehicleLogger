using System.Net.Http.Json;

namespace VehicleLogger.Api.Services;

/// Отправляет уведомления водителям через HTTP-сервер Telegram-бота.
///
/// Адрес бота берётся из конфигурации `Telegram:NotifyUrl`
/// (в Docker задаётся переменной окружения Telegram__NotifyUrl).
/// Если адрес не задан — нотификатор считается выключенным и все вызовы
/// превращаются в no-op: бэкенд продолжает работать даже без бота.
public class TelegramNotifier
{
    private readonly HttpClient _http;
    private readonly ILogger<TelegramNotifier> _log;
    private readonly string? _notifyUrl;
    private readonly string? _notifyKey;

    public TelegramNotifier(HttpClient http, IConfiguration config, ILogger<TelegramNotifier> log)
    {
        _http = http;
        _log = log;
        _notifyUrl = config["Telegram:NotifyUrl"];
        _notifyKey = config["Telegram:NotifyKey"];
    }

    /// true, если адрес бота задан в конфигурации.
    public bool Enabled => !string.IsNullOrWhiteSpace(_notifyUrl);

    /// Отправляет текстовое сообщение водителю в Telegram.
    /// Метод НИКОГДА не бросает исключение — при ошибке (бот недоступен,
    /// водитель не нажал /start и т.п.) только пишет в лог, чтобы сбой
    /// бота не ломал приём телеметрии.
    public async Task NotifyAsync(long telegramId, string text)
    {
        if (!Enabled)
        {
            _log.LogDebug("TelegramNotifier выключен (Telegram:NotifyUrl не задан) — пропуск.");
            return;
        }

        try
        {
            using var msg = new HttpRequestMessage(HttpMethod.Post, _notifyUrl)
            {
                Content = JsonContent.Create(new { telegramId, text })
            };

            // Общий секрет между бэкендом и ботом (если настроен).
            if (!string.IsNullOrWhiteSpace(_notifyKey))
                msg.Headers.Add("X-Bot-Key", _notifyKey);

            var resp = await _http.SendAsync(msg);

            if (resp.IsSuccessStatusCode)
            {
                _log.LogInformation("Уведомление доставлено водителю tg={Tg}", telegramId);
            }
            else
            {
                var body = await resp.Content.ReadAsStringAsync();
                _log.LogWarning("Бот ответил {Status} на уведомление tg={Tg}: {Body}",
                    (int)resp.StatusCode, telegramId, body);
            }
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex, "Не удалось доставить уведомление водителю tg={Tg}", telegramId);
        }
    }
}
