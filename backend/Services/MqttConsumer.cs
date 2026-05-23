using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using MQTTnet;
using MQTTnet.Client;
using MQTTnet.Protocol;
using VehicleLogger.Api.Data;
using VehicleLogger.Api.Dtos;
using VehicleLogger.Api.Models;

namespace VehicleLogger.Api.Services;

/// Подписывается на MQTT-брокер и принимает телеметрию устройств.
///
/// Топики:
///   vl/{tenant}/{deviceSerial}/telemetry — VehicleLogger пакеты телеметрии
///   vl/{tenant}/{deviceSerial}/ping      — heartbeat
///
/// Для отключенного MQTT (Mqtt:Enabled=false) — никаких действий не выполняет.
/// Это позволяет запускать backend в средах без брокера (dev, CI), не падая.
public class MqttConsumer : BackgroundService
{
    private readonly IServiceProvider _sp;
    private readonly IConfiguration _cfg;
    private readonly ILogger<MqttConsumer> _log;

    public MqttConsumer(IServiceProvider sp, IConfiguration cfg, ILogger<MqttConsumer> log)
    {
        _sp = sp;
        _cfg = cfg;
        _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!_cfg.GetValue<bool>("Mqtt:Enabled"))
        {
            _log.LogInformation("MQTT disabled in config — MqttConsumer не подключается к брокеру");
            return;
        }

        var host = _cfg["Mqtt:Broker"] ?? "localhost";
        var port = _cfg.GetValue<int>("Mqtt:Port", 8883);
        var useTls = _cfg.GetValue<bool>("Mqtt:UseTls", true);
        var user = _cfg["Mqtt:Username"];
        var pass = _cfg["Mqtt:Password"];

        var factory = new MqttFactory();
        var client = factory.CreateMqttClient();

        client.ApplicationMessageReceivedAsync += OnMessageAsync;
        client.DisconnectedAsync += async args =>
        {
            _log.LogWarning("MQTT disconnected: {Reason}", args.ReasonString);
            await Task.CompletedTask;
        };

        var optsBuilder = new MqttClientOptionsBuilder()
            .WithClientId($"vl-backend-{Environment.MachineName}")
            .WithTcpServer(host, port)
            .WithCredentials(user, pass)
            .WithCleanSession(false);
        if (useTls)
            optsBuilder.WithTlsOptions(o => o.UseTls(true).WithCertificateValidationHandler(_ => true));
        var opts = optsBuilder.Build();

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                if (!client.IsConnected)
                {
                    _log.LogInformation("MQTT connecting to {Host}:{Port}…", host, port);
                    await client.ConnectAsync(opts, stoppingToken);
                    _log.LogInformation("MQTT connected. Subscribing to vl/+/+/telemetry and vl/+/+/ping");
                    await client.SubscribeAsync(new MqttClientSubscribeOptionsBuilder()
                        .WithTopicFilter("vl/+/+/telemetry", MqttQualityOfServiceLevel.AtLeastOnce)
                        .WithTopicFilter("vl/+/+/ping",      MqttQualityOfServiceLevel.AtLeastOnce)
                        .Build(), stoppingToken);
                }
                await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken);
            }
            catch (OperationCanceledException) { break; }
            catch (Exception ex)
            {
                _log.LogError(ex, "MQTT loop error — retry in 5s");
                try { await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken); }
                catch (OperationCanceledException) { break; }
            }
        }

        try { await client.DisconnectAsync(); } catch { /* ignore */ }
    }

    private async Task OnMessageAsync(MqttApplicationMessageReceivedEventArgs e)
    {
        try
        {
            var topic = e.ApplicationMessage.Topic;
            var parts = topic.Split('/');
            // vl / {tenant} / {serial} / telemetry|ping
            if (parts.Length < 4 || parts[0] != "vl")
            {
                _log.LogWarning("Unexpected topic: {Topic}", topic);
                return;
            }
            var kind = parts[3];
            var serial = parts[2];
            var payloadBytes = e.ApplicationMessage.Payload ?? Array.Empty<byte>();
            var json = Encoding.UTF8.GetString(payloadBytes);

            using var scope = _sp.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            var detector = scope.ServiceProvider.GetRequiredService<TripDetector>();

            var device = await db.Devices.FirstOrDefaultAsync(d => d.SerialNumber == serial);
            if (device is null)
            {
                _log.LogWarning("MQTT message for unknown device {Serial}", serial);
                return;
            }

            if (kind == "ping")
            {
                device.IsOnline = true;
                device.LastPingAt = DateTime.UtcNow;
                await db.SaveChangesAsync();
                return;
            }

            if (kind != "telemetry")
            {
                _log.LogWarning("Unknown topic kind: {Kind}", kind);
                return;
            }

            TelemetryRequest? req;
            try
            {
                req = JsonSerializer.Deserialize<TelemetryRequest>(json, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });
            }
            catch (Exception parseEx)
            {
                _log.LogWarning(parseEx, "Bad telemetry JSON from {Serial}", serial);
                return;
            }
            if (req is null || req.Timestamp == default) return;

            var ts = req.Timestamp.ToUniversalTime();
            // Дедупликация по (DeviceId, Timestamp) при QoS-1 ретраях
            var exists = await db.Telemetry.AnyAsync(t => t.DeviceId == device.Id && t.Timestamp == ts);
            if (exists) return;

            var record = new TelemetryRecord
            {
                DeviceId   = device.Id,
                Timestamp  = ts,
                Rpm        = req.Data.Rpm,
                Speed      = req.Data.Speed,
                CoolantTemp = req.Data.CoolantTemp,
                OilPressure = req.Data.OilPressure,
                FuelLevel   = req.Data.FuelLevel,
                Voltage     = req.Data.Voltage,
                DtcCodesJson = JsonSerializer.Serialize(req.Data.DtcCodes ?? new List<string>()),
                OdometerKm  = req.Data.Odometer,
                Lat        = req.Gps?.Lat,
                Lng        = req.Gps?.Lng,
                Altitude   = req.Gps?.Alt,
                GpsSpeed   = req.Gps?.Speed,
                Course     = req.Gps?.Course,
                Satellites = req.Gps?.Sats,
                GpsFix     = req.Gps?.Fix,
                ReceivedAt = DateTime.UtcNow
            };
            db.Telemetry.Add(record);
            device.IsOnline = true;
            device.LastPingAt = DateTime.UtcNow;
            await db.SaveChangesAsync();

            await detector.ProcessAsync(record, device);
        }
        catch (Exception ex)
        {
            _log.LogError(ex, "MQTT message handling failed");
        }
    }
}