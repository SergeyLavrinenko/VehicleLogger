#include "nvs_store.h"
#include <Preferences.h>
#include <esp_system.h>

namespace {
  Preferences prefs;

  bool readKey(const char* ns, const char* key, String& out) {
    if (!prefs.begin(ns, true)) return false;          // RO
    bool exists = prefs.isKey(key);
    if (exists) out = prefs.getString(key, "");
    prefs.end();
    return exists && out.length() > 0;
  }

  void writeKey(const char* ns, const char* key, const String& val) {
    prefs.begin(ns, false);
    prefs.putString(key, val);
    prefs.end();
  }

  void clearNamespace(const char* ns) {
    prefs.begin(ns, false);
    prefs.clear();
    prefs.end();
  }
}

namespace NvsStore {

  void begin() {
    // nvs_flash_init() уже вызван Arduino-фреймворком до setup().
    // Эта функция оставлена как точка инициализации на будущее.
  }

  // ── Factory ────────────────────────────────
  bool hasFactoryData() {
    String s, h;
    return readKey("factory", "serial", s) && readKey("factory", "secret", h);
  }

  String getSerial() {
    String s; readKey("factory", "serial", s);
    return s;
  }

  String getSecretHex() {
    String h; readKey("factory", "secret", h);
    return h;
  }

  void setSerial(const String& s)    { writeKey("factory", "serial", s); }
  void setSecretHex(const String& h) { writeKey("factory", "secret", h); }

  void bringUpFactoryDefaults() {
    if (hasFactoryData()) return;

    uint64_t mac = ESP.getEfuseMac();
    char serial[16];
    snprintf(serial, sizeof(serial), "VL-%08X", (uint32_t)(mac >> 8));
    setSerial(serial);

    char hex[65];
    for (int i = 0; i < 32; i++) {
      snprintf(hex + i * 2, 3, "%02x", (uint8_t)(esp_random() & 0xFF));
    }
    hex[64] = 0;
    setSecretHex(hex);

    Serial.printf("[NVS] Bring-up: %s + 32-byte secret (random)\n", serial);
  }

  // ── WiFi ───────────────────────────────────
  bool getWifi(String& ssid, String& password) {
    return readKey("wifi", "ssid", ssid) && readKey("wifi", "password", password);
  }

  void setWifi(const String& ssid, const String& password) {
    prefs.begin("wifi", false);
    prefs.putString("ssid", ssid);
    prefs.putString("password", password);
    prefs.end();
  }

  void clearWifi() { clearNamespace("wifi"); }

  // ── Cloud ──────────────────────────────────
  bool getApiKey(String& key)         { return readKey("cloud", "api_key", key); }
  void setApiKey(const String& key)   { writeKey("cloud", "api_key", key); }
  void clearApiKey() {
    prefs.begin("cloud", false);
    prefs.remove("api_key");
    prefs.end();
  }

  String getBackendUrl() {
    String u; readKey("cloud", "backend_url", u);
    return u;
  }

  void setBackendUrl(const String& url) { writeKey("cloud", "backend_url", url); }

  uint32_t getSendIntervalMs(uint32_t fallback) {
    prefs.begin("cloud", true);
    uint32_t v = prefs.getUInt("send_ms", fallback);
    prefs.end();
    return v;
  }

  void setSendIntervalMs(uint32_t ms) {
    prefs.begin("cloud", false);
    prefs.putUInt("send_ms", ms);
    prefs.end();
  }

  // ── Reset ──────────────────────────────────
  void resetWifi()      { clearWifi(); }
  void resetCloud()     { clearNamespace("cloud"); }
  void factoryReset()   { clearWifi(); clearNamespace("cloud"); }
}
