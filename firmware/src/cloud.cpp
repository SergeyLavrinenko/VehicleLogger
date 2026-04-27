#include "cloud.h"
#include "config.h"
#include "nvs_store.h"

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
}