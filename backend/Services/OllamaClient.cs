using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace VehicleLogger.Api.Services;

public class OllamaOptions
{
    public string ApiKey { get; set; } = "";
    public string BaseUrl { get; set; } = "https://ollama.com";
    public string Model { get; set; } = "gpt-oss:120b";
    public int TimeoutSeconds { get; set; } = 60;
}

public class OllamaClient
{
    private readonly HttpClient _http;
    private readonly OllamaOptions _opts;
    private readonly ILogger<OllamaClient> _log;

    public OllamaClient(HttpClient http, IConfiguration cfg, ILogger<OllamaClient> log)
    {
        _http = http;
        _log  = log;
        _opts = new OllamaOptions
        {
            ApiKey  = cfg["Ollama:ApiKey"]  ?? "",
            BaseUrl = cfg["Ollama:BaseUrl"] ?? "https://ollama.com",
            Model   = cfg["Ollama:Model"]   ?? "gpt-oss:120b",
            TimeoutSeconds = int.TryParse(cfg["Ollama:TimeoutSeconds"], out var t) ? t : 60
        };
        _http.Timeout = TimeSpan.FromSeconds(_opts.TimeoutSeconds);
    }

    public string Model => _opts.Model;

    public async Task<string> ChatAsync(string system, string user, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(_opts.ApiKey))
            throw new InvalidOperationException("Ollama API key не сконфигурирован (Ollama:ApiKey).");

        var body = new
        {
            model = _opts.Model,
            messages = new object[]
            {
                new { role = "system", content = system },
                new { role = "user",   content = user   }
            },
            stream = false
        };

        var json = JsonSerializer.Serialize(body);
        using var req = new HttpRequestMessage(HttpMethod.Post, $"{_opts.BaseUrl.TrimEnd('/')}/api/chat");
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _opts.ApiKey);
        req.Content = new StringContent(json, Encoding.UTF8, "application/json");

        using var resp = await _http.SendAsync(req, ct);
        var raw = await resp.Content.ReadAsStringAsync(ct);
        if (!resp.IsSuccessStatusCode)
        {
            _log.LogWarning("Ollama HTTP {Status}: {Body}", (int)resp.StatusCode, raw);
            throw new HttpRequestException($"Ollama HTTP {(int)resp.StatusCode}: {raw}");
        }

        using var doc = JsonDocument.Parse(raw);
        if (doc.RootElement.TryGetProperty("message", out var msg) &&
            msg.TryGetProperty("content", out var content))
        {
            return content.GetString() ?? "";
        }
        if (doc.RootElement.TryGetProperty("response", out var responseField))
        {
            return responseField.GetString() ?? "";
        }
        throw new InvalidOperationException("Не удалось распарсить ответ Ollama: " + raw);
    }
}
