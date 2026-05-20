#include "wifi_manager.h"
#include "nvs_store.h"

#include <WiFi.h>

namespace {
  String  s_ssid, s_pass;
  bool    s_credsLoaded = false;
  uint32_t s_lastTry    = 0;

  bool loadCreds() {
    if (s_credsLoaded) return true;
    if (!NvsStore::getWifi(s_ssid, s_pass)) return false;
    s_credsLoaded = true;
    return true;
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
      Serial.printf("[WIFI] OK ip=%s rssi=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      return true;
    }
    Serial.println("[WIFI] timeout");
    return false;
  }

  bool ensureConnected() {
    if (WiFi.status() == WL_CONNECTED) return true;
    if (millis() - s_lastTry < 5000) return false;
    s_lastTry = millis();
    if (!loadCreds()) return false;
    Serial.println("[WIFI] reconnect...");
    WiFi.disconnect(false, false);
    WiFi.begin(s_ssid.c_str(), s_pass.c_str());
    return false;
  }
}
