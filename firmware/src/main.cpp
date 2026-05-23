/*
 * VehicleLogger — основная прошивка.
 *
 * Boot state machine:
 *   - NVS wifi/ssid пуст                → MODE_PROVISIONING (SoftAP captive portal)
 *   - WiFi есть, NVS cloud/api_key пуст → MODE_PROVISIONING (повторный enroll)
 *   - WiFi + api_key есть               → MODE_WORKING (телеметрия)
 *
 * DEV-фича: в первые 3 секунды boot — нажать любую клавишу в Serial Monitor →
 * сброс wifi+cloud (factory остаётся → серийник тот же).
 */

#include <Arduino.h>
#include <WiFi.h>
#include "config.h"
#include "nvs_store.h"
#include "provisioning.h"
#include "wifi_manager.h"
#include "cloud.h"
#include "can_module.h"
#include "j1939.h"
#include "obd2.h"
#include "gps_module.h"
#include "mqtt_client.h"

namespace SimMode {
  static bool      s_active   = false;
  static uint32_t  s_startMs  = 0;
  static const uint32_t DURATION_MS = 120000;   // 2 минуты

  void start() {
    s_active  = true;
    s_startMs = millis();
    Serial.println(F("[SIM] >>> 2-min trip simulation STARTED"));
  }

  bool isActive() { return s_active; }

  void tick(VehicleData& v) {
    if (!s_active) return;
    uint32_t now     = millis();
    uint32_t elapsed = now - s_startMs;
    if (elapsed > DURATION_MS) {
      if (s_active) Serial.println(F("[SIM] <<< trip simulation ENDED — engine off"));
      s_active = false;
      v.rpm = 0; v.speed = 0;
      v.ts_rpm = now; v.ts_speed = now;
      return;
    }
    float t = elapsed / 1000.0f;
    float speed, rpm;
    if (t < 15.0f) {                   // 0..15 s: разгон 0→60
      float k = t / 15.0f;
      speed = 60.0f * k;
      rpm   = 800.0f + 1400.0f * k;
    } else if (t < 90.0f) {            // 15..90 s: круиз 60..80 с волнами
      float phase = (t - 15.0f) / 75.0f;
      speed = 70.0f + 10.0f * sinf(phase * 6.2832f * 2.0f);
      rpm   = 2000.0f + 400.0f * sinf(phase * 6.2832f * 3.0f);
    } else {                           // 90..120 s: торможение 60→0
      float k = (t - 90.0f) / 30.0f;
      speed = 60.0f * (1.0f - k);
      rpm   = 2000.0f * (1.0f - k) + 800.0f * k;
    }
    v.rpm            = (uint16_t)rpm;
    v.speed          = speed;
    v.coolantTemp    = 60.0f + (t / 120.0f) * 30.0f;
    v.fuelLevel      = 75.0f - (t / 120.0f) * 4.0f;
    v.batteryVoltage = 13.8f - (rpm < 1000.0f ? 0.5f : 0.0f);
    v.oilPressure    = 2.0f + rpm / 1500.0f;
    v.engineLoad     = 25.0f + 55.0f * (speed / 80.0f);
    v.fuelRate       = 4.0f + 11.0f * (speed / 80.0f);
    v.ts_rpm = v.ts_speed = v.ts_coolant = v.ts_fuel = v.ts_voltage = now;
    v.ts_oil = v.ts_load = v.ts_fuelRate = now;
  }

  void pollSerial() {
    while (Serial.available()) {
      int ch = Serial.read();
      if (ch == 'S' || ch == 's') start();
    }
  }
}

enum BootMode { MODE_PROVISIONING, MODE_WORKING };

static VehicleData g_vehicle;
static uint32_t    g_telemetryIntervalMs = 5000;
static uint32_t    g_pingIntervalMs      = 60000;
static uint32_t    g_lastTelemetryMs     = 0;
static uint32_t    g_lastPingMs          = 0;
static uint32_t    g_lastStatMs          = 0;
static bool        g_workingReady        = false;

static const char* protoStr(CanModule::Proto p) {
  switch (p) {
    case CanModule::PROTO_J1939: return "J1939";
    case CanModule::PROTO_OBD2:  return "OBD-II";
    default: return "probing";
  }
}

static BootMode decideBootMode() {
  String ssid, pass;
  if (!NvsStore::getWifi(ssid, pass)) return MODE_PROVISIONING;
  String key;
  if (!NvsStore::getApiKey(key))      return MODE_PROVISIONING;
  return MODE_WORKING;
}

static void printBanner() {
  Serial.println();
  Serial.println(F("================================="));
  Serial.println(F("  VehicleLogger — Production"));
  Serial.println(F("================================="));
}

// DEV-окно сброса: 3 сек слушаем Serial, любой символ → factoryReset + restart.
static void serialResetWindow(uint32_t windowMs = 3000) {
  Serial.printf("[BOOT] Нажми любую клавишу за %lu сек для сброса wifi+cloud...\n",
                (unsigned long)(windowMs / 1000));
  while (Serial.available()) Serial.read();
  uint32_t deadline = millis() + windowMs;
  while (millis() < deadline) {
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      Serial.println(F("[BOOT] СБРОС: стираем wifi + cloud NVS, factory остаётся"));
      NvsStore::factoryReset();
      Serial.println(F("[BOOT] Перезагрузка через 500 мс..."));
      delay(500);
      ESP.restart();
    }
    delay(20);
  }
}

static void enterWorkingMode() {
  Serial.println(F("[BOOT] Working mode (telemetry)"));

  if (!WifiManager::connectFromNvs(20000)) {
    Serial.println("[WORK] WiFi connect failed — ждём в loop()");
    return;
  }

  g_telemetryIntervalMs = NvsStore::getSendIntervalMs(5000);
  Serial.printf("[WORK] telemetry interval: %lu ms\n",
                (unsigned long)g_telemetryIntervalMs);

  CanModule::begin(&g_vehicle);

  // MQTT — если NVS говорит что включён, поднимаем клиент;
  // иначе fallback в Cloud::* по HTTPS остаётся в силе.
  MqttClient::begin();

  // Принудительный первый пинг чтобы LastPingAt появился сразу.
  Cloud::ping();
  g_lastPingMs = millis();

  g_workingReady = true;
  Serial.println("[WORK] ready");
}

static void handleAuthFailure() {
  Serial.println("[WORK] apiKey rejected — clearing NVS cloud and restart");
  NvsStore::clearApiKey();
  delay(2000);
  ESP.restart();
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  printBanner();

  NvsStore::begin();
  NvsStore::bringUpFactoryDefaults();

  GpsModule::begin();   // GPS поднимаем сразу — фикс может занять минуты

  Serial.printf("[NVS] Serial: %s\n", NvsStore::getSerial().c_str());
  Serial.printf("[NVS] Secret(hex): %s\n", NvsStore::getSecretHex().c_str());

  serialResetWindow(3000);

  String ssid, pass, apiKey, url;
  bool hasWifi = NvsStore::getWifi(ssid, pass);
  bool hasKey  = NvsStore::getApiKey(apiKey);
  url          = NvsStore::getBackendUrl();

  Serial.printf("[NVS] WiFi:    %s\n", hasWifi ? ssid.c_str() : "(не настроено)");
  Serial.printf("[NVS] API key: %s\n", hasKey ? "есть" : "(нет)");
  Serial.printf("[NVS] Backend: %s\n", url.length() ? url.c_str() : "(не настроено)");

  if (decideBootMode() == MODE_PROVISIONING) {
    Serial.println(F("[BOOT] Provisioning mode (SoftAP)"));
    Provisioning::start();
  } else {
    enterWorkingMode();
  }
}

void loop() {
  if (!g_workingReady) {
    // WiFi не поднялся при старте — пробуем повторно.
    if (WifiManager::connectFromNvs(15000)) {
      CanModule::begin(&g_vehicle);
      g_telemetryIntervalMs = NvsStore::getSendIntervalMs(5000);
      MqttClient::begin();
      Cloud::ping();
      g_lastPingMs   = millis();
      g_workingReady = true;
      Serial.println("[WORK] late-ready");
    } else {
      delay(5000);
      return;
    }
  }

  WifiManager::ensureConnected();
  CanModule::tick();
  GpsModule::tick();
  MqttClient::loop();
  SimMode::pollSerial();
  SimMode::tick(g_vehicle);

  uint32_t now = millis();

  if (now - g_lastTelemetryMs >= g_telemetryIntervalMs) {
    g_lastTelemetryMs = now;
    Cloud::PostResult r = Cloud::sendTelemetry(g_vehicle, 5000);
    if (r == Cloud::PostResult::Unauthorized) handleAuthFailure();
  }

  if (now - g_lastPingMs >= g_pingIntervalMs) {
    g_lastPingMs = now;
    Cloud::PostResult r = Cloud::ping();
    if (r == Cloud::PostResult::Unauthorized) handleAuthFailure();
  }

  if (now - g_lastStatMs >= 5000) {
    g_lastStatMs = now;
    Serial.printf("[STAT] frames=%lu baud=%d proto=%s pgnKnown=%lu pgnUnknown=%lu obdResp=%lu rssi=%d\n",
                  (unsigned long)CanModule::framesTotal(),
                  CanModule::baudKbit(),
                  protoStr(CanModule::proto()),
                  (unsigned long)g_vehicle.pgnKnownCount,
                  (unsigned long)g_vehicle.pgnUnknownCount,
                  (unsigned long)obd2ResponsesCount(),
                  (int)WiFi.RSSI(),
                  (unsigned long)GpsModule::lastFixAgeMs(),
                  MqttClient::isConnected() ? "on" : "off");
  }

  delay(20);
}
