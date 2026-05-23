#include "cloud.h"
#include "config.h"
#include "nvs_store.h"
#include "gps_module.h"
#include "mqtt_client.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

namespace Cloud {

  EnrollStatus enroll(const String& subdomain,
                      const String& enrollCode,
                      String& outApiKey,
                      String& outBackendUrl,
                      uint32_t& outSendIntervalMs)
  {
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[CLOUD] no WiFi");
      return EnrollStatus::NetworkError;
    }

    String url = String("https://") + subdomain + "." + BASE_DOMAIN + "/api/devices/enroll";
    Serial.printf("[CLOUD] POST %s\n", url.c_str());

    WiFiClientSecure client;
    client.setInsecure();   // TODO: вшить Let's Encrypt ISRG Root X1 в продакшене

    HTTPClient http;
    if (!http.begin(client, url)) {
      Serial.println("[CLOUD] http.begin FAIL");
      return EnrollStatus::NetworkError;
    }
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(15000);

    JsonDocument body;
    body["serialNumber"] = NvsStore::getSerial();
    body["deviceSecret"] = NvsStore::getSecretHex();
    body["enrollCode"]   = enrollCode;
    String payload;
    serializeJson(body, payload);

    int code  = http.POST(payload);
    String rs = http.getString();
    http.end();

    Serial.printf("[CLOUD] HTTP %d  resp=%s\n", code, rs.c_str());

    if (code <= 0) return EnrollStatus::NetworkError;

    if (code == 200) {
      JsonDocument doc;
      if (deserializeJson(doc, rs)) return EnrollStatus::UnknownError;
      outApiKey         = doc["apiKey"].as<String>();
      outBackendUrl     = doc["backendUrl"].as<String>();
      outSendIntervalMs = doc["sendIntervalMs"] | 5000;
      if (!outApiKey.length() || !outBackendUrl.length()) {
        Serial.println("[CLOUD] 200 but missing apiKey/backendUrl");
        return EnrollStatus::UnknownError;
      }
      // MQTT-параметры — опциональные, выдаются только если на сервере включён брокер
      String mqttHost = doc["mqttBroker"].as<String>();
      uint16_t mqttPort = (uint16_t)(doc["mqttPort"] | 0);
      bool mqttEnabled = doc["mqttEnabled"] | false;
      if (mqttEnabled && mqttHost.length() && mqttPort > 0) {
        NvsStore::setMqttBroker(mqttHost);
        NvsStore::setMqttPort(mqttPort);
        NvsStore::setMqttEnabled(true);
        Serial.printf("[CLOUD] MQTT enabled: %s:%u\n", mqttHost.c_str(), (unsigned)mqttPort);
      } else {
        NvsStore::setMqttEnabled(false);
      }
      return EnrollStatus::Ok;
    }

    String err;
    JsonDocument doc;
    if (!deserializeJson(doc, rs)) err = doc["error"].as<String>();

    if (code == 404) {
      // unknown_subdomain | unknown_device — для UX обе ситуации мапим как invalid_subdomain
      return EnrollStatus::InvalidSubdomain;
    }
    if (code == 400) return EnrollStatus::InvalidCode;
    if (code == 403) return EnrollStatus::InvalidSecret;
    if (code == 409) return EnrollStatus::AlreadyClaimed;
    if (code == 410) return EnrollStatus::Deactivated;
    return EnrollStatus::UnknownError;
  }

  // ────────── /api/telemetry, /api/device/ping ──────────

  namespace {
    bool s_timeSynced = false;

    void ensureTimeSync() {
      if (s_timeSynced) return;
      configTime(0, 0, "pool.ntp.org", "time.google.com");
      time_t now = 0;
      for (int i = 0; i < 60; i++) {
        time(&now);
        if (now >= 1700000000) break;   // > 2023-11-14 — считаем валидным
        delay(100);
      }
      time(&now);
      if (now >= 1700000000) {
        s_timeSynced = true;
        Serial.printf("[CLOUD] NTP synced, epoch=%lu\n", (unsigned long)now);
      } else {
        Serial.println("[CLOUD] NTP not synced");
      }
    }

    String isoTimestamp() {
      ensureTimeSync();
      time_t now = time(nullptr);
      struct tm tm_utc;
      gmtime_r(&now, &tm_utc);
      char buf[32];
      strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);
      return String(buf);
    }

    PostResult mapHttp(int code) {
      if (code >= 200 && code < 300) return PostResult::Ok;
      if (code == 401) return PostResult::Unauthorized;
      if (code == 410) return PostResult::Deactivated;
      if (code == 400) return PostResult::BadRequest;
      if (code <= 0)   return PostResult::NetworkError;
      return PostResult::UnknownError;
    }

    bool fresh(uint32_t ts, uint32_t staleMs) {
      return ts != 0 && (millis() - ts) < staleMs;
    }
  }

  PostResult sendTelemetry(const VehicleData& v, uint32_t staleMs) {
    if (WiFi.status() != WL_CONNECTED) return PostResult::NetworkError;

    String backend = NvsStore::getBackendUrl();
    if (backend.startsWith("http://")) backend = "https://" + backend.substring(7);
    String apiKey;
    NvsStore::getApiKey(apiKey);
    if (!backend.length() || !apiKey.length()) {
      Serial.println("[CLOUD] sendTelemetry: backendUrl/apiKey missing");
      return PostResult::UnknownError;
    }

    String url = backend + "/api/telemetry";

    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    if (!http.begin(client, url)) return PostResult::NetworkError;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", String("Bearer ") + apiKey);
    http.setTimeout(10000);

    JsonDocument doc;
    doc["deviceId"]  = NvsStore::getSerial();
    doc["timestamp"] = isoTimestamp();

    JsonObject data = doc["data"].to<JsonObject>();
    if (fresh(v.ts_rpm,     staleMs)) data["rpm"]         = (int)v.rpm;        else data["rpm"]         = nullptr;
    if (fresh(v.ts_speed,   staleMs)) data["speed"]       = v.speed;           else data["speed"]       = nullptr;
    if (fresh(v.ts_coolant, staleMs)) data["coolantTemp"] = v.coolantTemp;     else data["coolantTemp"] = nullptr;
    if (fresh(v.ts_oil,     staleMs)) data["oilPressure"] = v.oilPressure;     else data["oilPressure"] = nullptr;
    if (fresh(v.ts_fuel,    staleMs)) data["fuelLevel"]   = v.fuelLevel;       else data["fuelLevel"]   = nullptr;
    if (fresh(v.ts_voltage, staleMs)) data["voltage"]     = v.batteryVoltage;  else data["voltage"]     = nullptr;

    JsonArray dtcs = data["dtcCodes"].to<JsonArray>();
    if (fresh(v.ts_dtc, staleMs * 4)) {
      for (uint8_t i = 0; i < v.dtcCount && i < MAX_DTCS; i++) {
        char buf[24];
        snprintf(buf, sizeof(buf), "SPN%lu/FMI%u",
                 (unsigned long)v.dtcs[i].spn, v.dtcs[i].fmi);
        dtcs.add(buf);
      }
    }

    // GPS-снимок: добавляем только если фикс свежий (≤10 секунд)
    GpsModule::Snapshot gps = GpsModule::snapshot(10000);
    if (gps.valid) {
      JsonObject g = doc["gps"].to<JsonObject>();
      g["lat"]    = gps.lat;
      g["lng"]    = gps.lng;
      g["alt"]    = gps.altitudeM;
      g["speed"]  = gps.speedKmh;
      g["course"] = gps.courseDeg;
      g["sats"]   = gps.satellites;
      g["fix"]    = gps.fix;
    }

    String payload;
    serializeJson(doc, payload);

    // MQTT-канал: если подключён — публикуем туда и не ходим в HTTP.
    if (MqttClient::isConnected()) {
      http.end();  // отпускаем HTTPS-клиент, не отправляем запрос
      bool ok = MqttClient::publishTelemetry(payload);
      return ok ? PostResult::Ok : PostResult::NetworkError;
    }

    int code = http.POST(payload);
    String rs = http.getString();
    http.end();

    Serial.printf("[TELE] HTTP %d  bytes=%u  resp=%s\n",
                  code, payload.length(), rs.c_str());
    return mapHttp(code);
  }

  PostResult ping() {
    if (WiFi.status() != WL_CONNECTED) return PostResult::NetworkError;

    String backend = NvsStore::getBackendUrl();
    if (backend.startsWith("http://")) backend = "https://" + backend.substring(7);
    String apiKey;
    NvsStore::getApiKey(apiKey);
    if (!backend.length() || !apiKey.length()) return PostResult::UnknownError;

    String url = backend + "/api/device/ping";

    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    if (!http.begin(client, url)) return PostResult::NetworkError;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", String("Bearer ") + apiKey);
    http.setTimeout(8000);

    JsonDocument doc;
    doc["deviceId"] = NvsStore::getSerial();
    // GPS-снимок: добавляем только если фикс свежий (≤10 секунд)
    GpsModule::Snapshot gps = GpsModule::snapshot(10000);
    if (gps.valid) {
      JsonObject g = doc["gps"].to<JsonObject>();
      g["lat"]    = gps.lat;
      g["lng"]    = gps.lng;
      g["alt"]    = gps.altitudeM;
      g["speed"]  = gps.speedKmh;
      g["course"] = gps.courseDeg;
      g["sats"]   = gps.satellites;
      g["fix"]    = gps.fix;
    }

    String payload;
    serializeJson(doc, payload);

    if (MqttClient::isConnected()) {
      http.end();
      bool ok = MqttClient::publishPing(payload);
      return ok ? PostResult::Ok : PostResult::NetworkError;
    }

    int code = http.POST(payload);
    http.end();
    Serial.printf("[PING] HTTP %d\n", code);
    return mapHttp(code);
  }
}