/*
 * VehicleLogger — основная прошивка.
 *
 * Boot state machine:
 *   - NVS wifi/ssid пуст                → MODE_PROVISIONING (SoftAP captive portal)
 *   - WiFi есть, NVS cloud/api_key пуст → MODE_PROVISIONING (повторный enroll)
 *   - WiFi + api_key есть               → MODE_WORKING (телеметрия)
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

static void enterWorkingMode() {
  Serial.println(F("[BOOT] Working mode (telemetry)"));
  // TODO: wifi_manager::connect();  cloud::startTelemetry();  — этап 5
}

void setup() {
  Serial.begin(115200);
  delay(1500);

  printBanner();

  NvsStore::begin();
  NvsStore::bringUpFactoryDefaults();

  Serial.printf("[NVS] Serial: %s\n", NvsStore::getSerial().c_str());
  Serial.printf("[NVS] Secret hash known: %s\n",
                NvsStore::getSecretHex().length() == 64 ? "yes" : "NO");

  String ssid, pass, apiKey, url;
  bool hasWifi = NvsStore::getWifi(ssid, pass);
  bool hasKey  = NvsStore::getApiKey(apiKey);
  url          = NvsStore::getBackendUrl();

  Serial.printf("[NVS] WiFi:    %s\n", hasWifi ? ssid.c_str() : "(не настроено)");
  Serial.printf("[NVS] API key: %s\n", hasKey ? "есть" : "(нет)");
  Serial.printf("[NVS] Backend: %s\n", url.length() ? url.c_str() : "(не настроено)");

  if (decideBootMode() == MODE_PROVISIONING) {
    Serial.println(F("[BOOT] Provisioning mode (SoftAP)"));
    Provisioning::start();   // блокирующий, не возвращается
  } else {
    enterWorkingMode();
  }
}

void loop() {
  delay(1000);
}
