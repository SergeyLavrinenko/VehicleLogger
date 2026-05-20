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
                  (int)WiFi.RSSI());
  }

  delay(20);
}
