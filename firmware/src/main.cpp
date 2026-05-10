/*
 * VehicleLogger — основная прошивка.
 *
 * Boot state machine:
 *   - NVS wifi/ssid пуст                → MODE_PROVISIONING (SoftAP captive portal)
 *   - WiFi есть, NVS cloud/api_key пуст → MODE_PROVISIONING (повторный enroll)
 *   - WiFi + api_key есть               → MODE_WORKING (телеметрия)
 *
 * DEV-фича: в первые 3 секунды boot — нажать любую клавишу в Serial Monitor →
 * сброс wifi+cloud (factory остаётся → серийник тот же). Удобно для перепривязки
 * без полной очистки NVS.
 */

#include <Arduino.h>
#include <WiFi.h>
#include "config.h"
#include "nvs_store.h"
#include "provisioning.h"

enum BootMode { MODE_PROVISIONING, MODE_WORKING };

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
  // На всякий случай прочитаем накопленный мусор в буфере — он не должен триггерить
  while (Serial.available()) Serial.read();
  uint32_t deadline = millis() + windowMs;
  while (millis() < deadline) {
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      Serial.println(F("[BOOT] СБРОС: стираем wifi + cloud NVS, factory остаётся"));
      NvsStore::factoryReset();   // wifi/* + cloud/*; factory/* нетронут
      Serial.println(F("[BOOT] Перезагрузка через 500 мс..."));
      delay(500);
      ESP.restart();
    }
    delay(20);
  }
}

static void enterWorkingMode() {
  Serial.println(F("[BOOT] Working mode (telemetry)"));
  // TODO: wifi_manager::connect();  cloud::startTelemetry();  — этап 4
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  printBanner();

  NvsStore::begin();
  NvsStore::bringUpFactoryDefaults();

  Serial.printf("[NVS] Serial: %s\n", NvsStore::getSerial().c_str());
  Serial.printf("[NVS] Secret(hex): %s\n", NvsStore::getSecretHex().c_str());

  // DEV: возможность сбросить wifi+cloud без перепрошивки
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
  delay(1000);
}