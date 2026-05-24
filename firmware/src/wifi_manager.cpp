#include "wifi_manager.h"
#include "nvs_store.h"

#include <WiFi.h>

namespace {
  String   s_ssid, s_pass;
  bool     s_credsLoaded = false;
  uint32_t s_lastTry      = 0;
  uint32_t s_lastSuccessMs = 0;
  bool     s_everConnected = false;

  // Уйти в SoftAP, если за это время после boot не было ни одного успешного connect.
  static const uint32_t INITIAL_FAILBACK_MS = 90 * 1000;     // 90 секунд
  // Уйти в SoftAP, если связь была, но потеряна на это время.
  static const uint32_t LOST_FAILBACK_MS    = 5 * 60 * 1000; // 5 минут

  bool loadCreds() {
    if (s_credsLoaded) return true;
    if (!NvsStore::getWifi(s_ssid, s_pass)) return false;
    s_credsLoaded = true;
    return true;
  }

  void noteConnected() {
    s_lastSuccessMs = millis();
    s_everConnected = true;
  }
}

namespace WifiManager {

  bool connectFromNvs(uint32_t timeoutMs) {
    if (!loadCreds()) {
      Serial.println("[WIFI] no creds in NVS");
      return false;
    }
    WiFi.mode(WIFI_STA);
    WiFi.persistent(false);
    WiFi.setAutoReconnect(true);
    WiFi.disconnect(true, true);
    delay(100);

    Serial.printf("[WIFI] connecting to '%s'...\n", s_ssid.c_str());
    WiFi.begin(s_ssid.c_str(), s_pass.c_str());

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
      delay(250);
      Serial.print('.');
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
      noteConnected();
      Serial.printf("[WIFI] OK ip=%s rssi=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      return true;
    }
    Serial.println("[WIFI] timeout");
    return false;
  }

  bool ensureConnected() {
    if (WiFi.status() == WL_CONNECTED) {
      noteConnected();
      return true;
    }
    if (millis() - s_lastTry < 5000) return false;
    s_lastTry = millis();
    if (!loadCreds()) return false;
    Serial.println("[WIFI] reconnect...");
    WiFi.disconnect(false, false);
    WiFi.begin(s_ssid.c_str(), s_pass.c_str());
    return false;
  }

  bool shouldFallbackToSoftAp() {
    if (!s_everConnected) {
      // Никогда не подключались с момента boot — даём 90 секунд и сваливаемся в SoftAP.
      return millis() > INITIAL_FAILBACK_MS;
    }
    // Подключались, но связь потеряна.
    if (WiFi.status() == WL_CONNECTED) return false;
    return millis() - s_lastSuccessMs > LOST_FAILBACK_MS;
  }
}