#include "mqtt_client.h"
#include "nvs_store.h"
#include "config.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

namespace MqttClient {

  namespace {
    WiFiClientSecure s_tls;
    PubSubClient     s_client(s_tls);
    String           s_host;
    uint16_t         s_port = 8883;
    String           s_clientId;       // serial
    String           s_user;           // serial (== clientId)
    String           s_password;       // api_key
    String           s_telemetryTopic;
    String           s_pingTopic;
    bool             s_enabled = false;
    uint32_t         s_nextReconnectAt = 0;

    String inferTenantFromBackendUrl() {
      // backend_url = "https://<sub>.<base>" или "https://<base>" в legacy
      String url = NvsStore::getBackendUrl();
      if (url.startsWith("https://")) url = url.substring(8);
      else if (url.startsWith("http://")) url = url.substring(7);
      int slash = url.indexOf('/');
      if (slash >= 0) url = url.substring(0, slash);
      // url = "<sub>.<base>" or "<base>"; берём всё до первой точки как tenant.
      int dot = url.indexOf('.');
      if (dot <= 0) return "default";   // нет поддомена — общий канал
      return url.substring(0, dot);
    }
  }

  bool begin() {
    s_enabled = NvsStore::getMqttEnabled(false);
    if (!s_enabled) {
      Serial.println("[MQTT] disabled in NVS — skipping init");
      return false;
    }

    s_host = NvsStore::getMqttBroker();
    s_port = NvsStore::getMqttPort(8883);
    s_clientId = NvsStore::getSerial();
    s_user     = s_clientId;
    NvsStore::getApiKey(s_password);

    if (!s_host.length() || s_port == 0 || !s_clientId.length() || !s_password.length()) {
      Serial.println("[MQTT] config incomplete — skipping");
      s_enabled = false;
      return false;
    }

    auto tenant = inferTenantFromBackendUrl();
    s_telemetryTopic = "vl/" + tenant + "/" + s_clientId + "/telemetry";
    s_pingTopic      = "vl/" + tenant + "/" + s_clientId + "/ping";

    s_tls.setInsecure();   // TODO: вшить корневой сертификат брокера
    s_client.setBufferSize(2048);
    s_client.setKeepAlive(60);
    s_client.setServer(s_host.c_str(), s_port);

    Serial.printf("[MQTT] begin host=%s:%u client=%s tenant=%s\n",
                  s_host.c_str(), (unsigned)s_port, s_clientId.c_str(), tenant.c_str());
    return true;
  }

  static bool ensureConnected() {
    if (!s_enabled) return false;
    if (s_client.connected()) return true;
    if (WiFi.status() != WL_CONNECTED) return false;
    uint32_t now = millis();
    if (now < s_nextReconnectAt) return false;
    Serial.printf("[MQTT] connecting %s as %s...\n", s_host.c_str(), s_clientId.c_str());
    bool ok = s_client.connect(s_clientId.c_str(), s_user.c_str(), s_password.c_str());
    if (ok) {
      Serial.println("[MQTT] connected");
    } else {
      Serial.printf("[MQTT] connect failed state=%d, retry in 5s\n", s_client.state());
      s_nextReconnectAt = now + 5000;
    }
    return ok;
  }

  void loop() {
    if (!s_enabled) return;
    if (ensureConnected()) s_client.loop();
  }

  bool isConnected() {
    return s_enabled && s_client.connected();
  }

  bool publishTelemetry(const String& json) {
    if (!ensureConnected()) return false;
    bool ok = s_client.publish(s_telemetryTopic.c_str(),
                                (const uint8_t*)json.c_str(), json.length(), false);
    Serial.printf("[MQTT] publish telemetry %u bytes -> %s [%s]\n",
                  json.length(), s_telemetryTopic.c_str(), ok ? "ok" : "fail");
    return ok;
  }

  bool publishPing(const String& json) {
    if (!ensureConnected()) return false;
    bool ok = s_client.publish(s_pingTopic.c_str(),
                                (const uint8_t*)json.c_str(), json.length(), false);
    Serial.printf("[MQTT] publish ping %u bytes [%s]\n", json.length(), ok ? "ok" : "fail");
    return ok;
  }
}