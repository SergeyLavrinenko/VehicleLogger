#include "provisioning.h"
#include "config.h"
#include "nvs_store.h"

#include <Arduino.h>
#include <WiFi.h>
#include <DNSServer.h>
#include <ESPAsyncWebServer.h>
#include <AsyncJson.h>
#include <ArduinoJson.h>
#include <LittleFS.h>

namespace {
  AsyncWebServer server(80);
  DNSServer     dnsServer;
  IPAddress     apIP(192, 168, 4, 1);

  enum WifiState   { WIFI_IDLE, WIFI_CONNECTING, WIFI_OK, WIFI_FAIL };
  enum EnrollState { ENROLL_IDLE, ENROLL_PENDING, ENROLL_OK,
                     ENROLL_INVALID_CODE, ENROLL_INVALID_SUBDOMAIN,
                     ENROLL_ALREADY_CLAIMED, ENROLL_INVALID_SECRET,
                     ENROLL_NETWORK_ERROR };

  volatile WifiState   wifiState   = WIFI_IDLE;
  volatile EnrollState enrollState = ENROLL_IDLE;
  String   pendingSsid, pendingPass, pendingSub, pendingCode;
  uint32_t connectStartedAt = 0;
  bool     wifiBeginCalled  = false;

  String apName() {
    String s = NvsStore::getSerial();
    if (s.length() < 8) return "VehicleLogger";
    return "VehicleLogger-" + s.substring(s.length() - 8);
  }

  const char* wifiStr(WifiState s) {
    switch (s) {
      case WIFI_IDLE:       return "idle";
      case WIFI_CONNECTING: return "connecting";
      case WIFI_OK:         return "ok";
      case WIFI_FAIL:       return "fail";
    }
    return "idle";
  }
  const char* enrollStr(EnrollState s) {
    switch (s) {
      case ENROLL_IDLE:               return "idle";
      case ENROLL_PENDING:             return "pending";
      case ENROLL_OK:                  return "ok";
      case ENROLL_INVALID_CODE:        return "invalid_code";
      case ENROLL_INVALID_SUBDOMAIN:   return "invalid_subdomain";
      case ENROLL_ALREADY_CLAIMED:     return "already_claimed";
      case ENROLL_INVALID_SECRET:      return "invalid_secret";
      case ENROLL_NETWORK_ERROR:       return "network_error";
    }
    return "idle";
  }

  void handleInfo(AsyncWebServerRequest* req) {
    JsonDocument doc;
    doc["serial"]     = NvsStore::getSerial();
    doc["baseDomain"] = BASE_DOMAIN;
    String out; serializeJson(doc, out);
    req->send(200, "application/json", out);
  }

  void handleScan(AsyncWebServerRequest* req) {
    int n = WiFi.scanComplete();
    if (n == WIFI_SCAN_RUNNING) {
      req->send(202, "application/json", "{\"status\":\"scanning\"}");
      return;
    }
    if (n < 0) {
      WiFi.scanNetworks(true);
      req->send(202, "application/json", "{\"status\":\"scanning\"}");
      return;
    }
    JsonDocument doc;
    JsonArray arr = doc.to<JsonArray>();
    for (int i = 0; i < n; i++) {
      JsonObject o = arr.add<JsonObject>();
      o["ssid"]   = WiFi.SSID(i);
      o["rssi"]   = WiFi.RSSI(i);
      o["secure"] = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    }
    String out; serializeJson(doc, out);
    req->send(200, "application/json", out);
    WiFi.scanDelete();
    WiFi.scanNetworks(true);   // подгружаем следующий результат
  }

  void handleStatus(AsyncWebServerRequest* req) {
    JsonDocument doc;
    doc["wifi"]   = wifiStr(wifiState);
    doc["enroll"] = enrollStr(enrollState);
    if (wifiState == WIFI_OK) doc["ip"] = WiFi.localIP().toString();
    String out; serializeJson(doc, out);
    req->send(200, "application/json", out);
  }

  void handleSetup(AsyncWebServerRequest* req, JsonVariant& json) {
    JsonObject body = json.as<JsonObject>();
    pendingSsid = body["ssid"].as<String>();
    pendingPass = body["password"].as<String>();
    pendingSub  = body["subdomain"].as<String>();
    pendingCode = body["enrollCode"].as<String>();

    if (pendingSsid.length() == 0) {
      req->send(400, "application/json", "{\"error\":\"ssid_required\"}");
      return;
    }
    wifiBeginCalled  = false;
    wifiState        = WIFI_CONNECTING;
    enrollState      = ENROLL_IDLE;
    connectStartedAt = millis();
    Serial.printf("[PROV] Setup: ssid='%s' subdomain='%s' code='%s'\n",
                  pendingSsid.c_str(), pendingSub.c_str(), pendingCode.c_str());
    req->send(202, "application/json", "{\"accepted\":true}");
  }

  void setupRoutes() {
    server.on("/api/info",   HTTP_GET, handleInfo);
    server.on("/api/scan",   HTTP_GET, handleScan);
    server.on("/api/status", HTTP_GET, handleStatus);
    server.addHandler(new AsyncCallbackJsonWebHandler("/api/setup", handleSetup));
    server.serveStatic("/", LittleFS, "/").setDefaultFile("setup.html");
    server.onNotFound([](AsyncWebServerRequest* req) {
      // captive portal: любой запрос → редирект на главную
      req->redirect("/");
    });
  }

  void tickWifi() {
    if (wifiState != WIFI_CONNECTING) return;

    if (!wifiBeginCalled) {
      WiFi.disconnect(true, true);
      delay(100);
      WiFi.begin(pendingSsid.c_str(), pendingPass.c_str());
      wifiBeginCalled  = true;
      connectStartedAt = millis();
      return;
    }

    wl_status_t s = WiFi.status();
    if (s == WL_CONNECTED) {
      wifiState = WIFI_OK;
      Serial.printf("[PROV] WiFi OK: %s\n", WiFi.localIP().toString().c_str());

      // Этап 3: сохраняем WiFi, enroll — заглушка. Этап 5 заменит на cloud::enroll().
      NvsStore::setWifi(pendingSsid, pendingPass);
      Serial.printf("[PROV] WiFi saved. TODO enroll: subdomain='%s' code='%s'\n",
                    pendingSub.c_str(), pendingCode.c_str());
      enrollState = ENROLL_OK;
      return;
    }

    if (millis() - connectStartedAt > 15000) {
      Serial.println("[PROV] WiFi connect timeout");
      WiFi.disconnect(true, true);
      wifiState        = WIFI_FAIL;
      wifiBeginCalled  = false;
    }
  }
}

void Provisioning::start() {
  if (!LittleFS.begin(false)) {
    Serial.println("[PROV] LittleFS mount FAILED — formatting...");
    LittleFS.begin(true);
  } else {
    Serial.println("[PROV] LittleFS OK");
  }

  WiFi.mode(WIFI_AP_STA);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
  WiFi.softAP(apName().c_str(), AP_PASSWORD);
  Serial.printf("[PROV] SoftAP '%s' on %s (pass: %s)\n",
                apName().c_str(), WiFi.softAPIP().toString().c_str(), AP_PASSWORD);

  dnsServer.start(53, "*", apIP);
  WiFi.scanNetworks(true);
  setupRoutes();
  server.begin();
  Serial.println("[PROV] HTTP server up — http://192.168.4.1/");

  while (true) {
    dnsServer.processNextRequest();
    tickWifi();
    delay(10);
  }
}
