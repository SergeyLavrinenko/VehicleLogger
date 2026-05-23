using System.Diagnostics;
using BCrypt.Net;

namespace VehicleLogger.Api.Services;

/// Управляет учётной записью устройства в файле паролей Mosquitto.
/// Структура файла: одна строка на пользователя — `username:hash`
/// (Mosquitto читает PBKDF2 / Argon2 / bcrypt; мы кладём bcrypt-хеш).
///
/// При выдаче нового api_key (enroll, rotate-key) вызывается SetPasswordAsync,
/// при unclaim — RemoveUserAsync. После каждого изменения — ReloadAsync (HUP-сигнал).
///
/// На сервере процесс backend должен иметь право писать в passwd-файл и вызывать
/// команду перезагрузки (через sudoers или общую группу с mosquitto).
public class MosquittoUserManager
{
    private readonly IConfiguration _cfg;
    private readonly ILogger<MosquittoUserManager> _log;

    public MosquittoUserManager(IConfiguration cfg, ILogger<MosquittoUserManager> log)
    {
        _cfg = cfg;
        _log = log;
    }

    public bool Enabled => _cfg.GetValue<bool>("Mqtt:Enabled");

    /// Записывает (или обновляет) учётную запись `username:bcrypt(password)` в passwd-файле.
    public async Task SetPasswordAsync(string username, string password)
    {
        if (!Enabled)
        {
            _log.LogInformation("MQTT отключён в конфиге, MosquittoUserManager.SetPasswordAsync пропущен");
            return;
        }
        var path = _cfg["Mqtt:PasswdFile"] ?? "/etc/mosquitto/passwd";
        var hash = BCrypt.Net.BCrypt.HashPassword(password, workFactor: 10);
        try
        {
            var lines = File.Exists(path)
                ? (await File.ReadAllLinesAsync(path)).ToList()
                : new List<string>();
            var prefix = username + ":";
            var idx = lines.FindIndex(l => l.StartsWith(prefix, StringComparison.Ordinal));
            var entry = username + ":" + hash;
            if (idx >= 0) lines[idx] = entry; else lines.Add(entry);
            await File.WriteAllLinesAsync(path, lines);
            await ReloadAsync();
            _log.LogInformation("Mosquitto passwd updated for {User}", username);
        }
        catch (Exception ex)
        {
            _log.LogError(ex, "Не удалось записать Mosquitto passwd для {User}", username);
        }
    }

    public async Task RemoveUserAsync(string username)
    {
        if (!Enabled) return;
        var path = _cfg["Mqtt:PasswdFile"] ?? "/etc/mosquitto/passwd";
        try
        {
            if (!File.Exists(path)) return;
            var lines = (await File.ReadAllLinesAsync(path)).ToList();
            var prefix = username + ":";
            var removed = lines.RemoveAll(l => l.StartsWith(prefix, StringComparison.Ordinal));
            if (removed > 0)
            {
                await File.WriteAllLinesAsync(path, lines);
                await ReloadAsync();
                _log.LogInformation("Mosquitto passwd removed user {User}", username);
            }
        }
        catch (Exception ex)
        {
            _log.LogError(ex, "Не удалось удалить пользователя Mosquitto {User}", username);
        }
    }

    /// Выполняет команду перечитывания конфига брокера (по умолчанию `systemctl reload mosquitto`).
    private async Task ReloadAsync()
    {
        var cmd = _cfg["Mqtt:ReloadCommand"];
        if (string.IsNullOrWhiteSpace(cmd)) return;
        try
        {
            var psi = new ProcessStartInfo("sh", $"-c \"{cmd}\"")
            {
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using var p = Process.Start(psi);
            if (p is null) return;
            await p.WaitForExitAsync();
            if (p.ExitCode != 0)
            {
                var err = await p.StandardError.ReadToEndAsync();
                _log.LogWarning("Mosquitto reload exit {Code}: {Err}", p.ExitCode, err);
            }
        }
        catch (Exception ex)
        {
            _log.LogError(ex, "Mosquitto reload command failed: {Cmd}", cmd);
        }
    }
}