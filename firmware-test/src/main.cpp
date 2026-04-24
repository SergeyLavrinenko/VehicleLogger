/*
 * VehicleLogger — Тестовый стенд
 *
 * Веб-дашборд с графиками датчиков в реальном времени.
 * ESP32 подключается к WiFi и раздаёт страницу по HTTP.
 * Данные обновляются через WebSocket (~5 раз/сек).
 *
 * Открыть в браузере: http://<IP-адрес ESP32>
 * IP выводится в Serial Monitor при старте.
 *
 * Подключение:
 *   WCMCU-230 (CAN):  CTX → GPIO22, CRX → GPIO21
 *   NEO-M8N (GPS):    TX  → GPIO16, RX  → GPIO17
 *   MPU-6050 (IMU):   SDA → GPIO18, SCL → GPIO19
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <Wire.h>
#include <LittleFS.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <driver/twai.h>
#include <TinyGPSPlus.h>
#include "config.h"
#include "j1939.h"
#include "obd2.h"

// ─── Объекты ───────────────────────────────────

WiFiMulti wifiMulti;
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");
HardwareSerial gpsSerial(2);
TinyGPSPlus gps;

unsigned long lastWsSend = 0;
bool canInitOk = false;
int canBaudKbit = 0;
enum CanProto { PROTO_UNKNOWN = 0, PROTO_J1939 = 1, PROTO_OBD2 = 2 };
CanProto canProto = PROTO_UNKNOWN;
uint32_t protoDetectDeadline = 0;
VehicleData vehicle;

// ─── Данные датчиков ───────────────────────────

struct {
  // IMU (в физических единицах)
  float ax, ay, az;       // g
  float gx, gy, gz;       // °/s
  float imuTemp;          // °C
  bool imuOk;

  // GPS
  double lat, lng;
  float speed;            // км/ч
  float altitude;         // м
  int satellites;
  bool fix;
  bool gpsOk;

  // CAN
  int framesTotal;
  uint32_t lastId;
  uint8_t lastData[8];
  uint8_t lastDlc;

  // Система
  int rssi;
  uint32_t freeHeap;
  unsigned long uptime;
} sensorData;

// Буфер последних CAN-фреймов для отображения
#define CAN_LOG_SIZE 20
struct CanFrame {
  uint32_t id;
  uint8_t data[8];
  uint8_t dlc;
  unsigned long timestamp;
};
CanFrame canLog[CAN_LOG_SIZE];
int canLogIndex = 0;

// ─── IMU ───────────────────────────────────────

void i2cRecover() {
  // Если slave держит SDA low после сброса — прокачиваем SCL
  pinMode(MPU_SDA_PIN, INPUT_PULLUP);
  pinMode(MPU_SCL_PIN, OUTPUT);
  for (int i = 0; i < 16; i++) {
    digitalWrite(MPU_SCL_PIN, LOW);
    delayMicroseconds(5);
    digitalWrite(MPU_SCL_PIN, HIGH);
    delayMicroseconds(5);
  }
  pinMode(MPU_SCL_PIN, INPUT_PULLUP);
}

void initIMU() {
  i2cRecover();
  Wire.begin(MPU_SDA_PIN, MPU_SCL_PIN);
  delay(100);

  // I2C scan
  Serial.print("[IMU] I2C scan:");
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf(" 0x%02X", addr);
      found++;
    }
  }
  Serial.printf(" (%d найдено)\n", found);

  // Проверить MPU с ретраями
  for (int attempt = 0; attempt < 3; attempt++) {
    Wire.beginTransmission(MPU_ADDR);
    if (Wire.endTransmission() == 0) {
      sensorData.imuOk = true;
      break;
    }
    delay(50);
  }

  if (sensorData.imuOk) {
    // Разбудить MPU-6050
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x6B);
    Wire.write(0x00);
    Wire.endTransmission();
    delay(50);
    Serial.println("[IMU] MPU-6050 OK");
  } else {
    Serial.println("[IMU] MPU-6050 не найден на 0x68!");
  }
}

void readIMU() {
  if (!sensorData.imuOk) return;

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)14);

  if (Wire.available() < 14) return;

  int16_t raw_ax = (Wire.read() << 8) | Wire.read();
  int16_t raw_ay = (Wire.read() << 8) | Wire.read();
  int16_t raw_az = (Wire.read() << 8) | Wire.read();
  int16_t raw_t  = (Wire.read() << 8) | Wire.read();
  int16_t raw_gx = (Wire.read() << 8) | Wire.read();
  int16_t raw_gy = (Wire.read() << 8) | Wire.read();
  int16_t raw_gz = (Wire.read() << 8) | Wire.read();

  sensorData.ax = raw_ax / 16384.0;
  sensorData.ay = raw_ay / 16384.0;
  sensorData.az = raw_az / 16384.0;
  sensorData.gx = raw_gx / 131.0;
  sensorData.gy = raw_gy / 131.0;
  sensorData.gz = raw_gz / 131.0;
  sensorData.imuTemp = raw_t / 340.0 + 36.53;
}

// ─── GPS + Спутники (GSV) ──────────────────────

#define MAX_SATS 40

enum Constellation : uint8_t {
  CON_GPS = 0, CON_GLONASS = 1, CON_GALILEO = 2, CON_BEIDOU = 3, CON_SBAS = 4, CON_UNKNOWN = 5
};

const char* conNames[] = { "GPS", "GLONASS", "Galileo", "BeiDou", "SBAS", "?" };

struct SatInfo {
  uint16_t prn;
  uint8_t  elev;          // 0-90°
  uint16_t azim;          // 0-359°
  uint8_t  snr;           // dB-Hz, 0 = не отслеживается
  uint8_t  constellation; // CON_*
};

// Отдельные буферы по созвездиям (GSV приходят раздельно для GPS/GLONASS/Galileo/BeiDou)
#define MAX_SATS_PER_CON 16
SatInfo conSats[6][MAX_SATS_PER_CON];
int conSatCount[6] = {0};

SatInfo sats[MAX_SATS];     // объединённый снимок для API
int satCount = 0;

// NMEA-буфер для парсинга GSV
char nmeaLine[128];
int nmeaPos = 0;

// Debug: последние GSV-строки
#define GSV_DEBUG_SIZE 12
char gsvDebug[GSV_DEBUG_SIZE][96];
int gsvDebugIdx = 0;

Constellation talkerToConstellation(char a, char b) {
  if (a == 'G' && b == 'P') return CON_GPS;
  if (a == 'G' && b == 'L') return CON_GLONASS;
  if (a == 'G' && b == 'A') return CON_GALILEO;
  if (a == 'G' && b == 'B') return CON_BEIDOU;
  if (a == 'B' && b == 'D') return CON_BEIDOU;
  if (a == 'G' && b == 'N') return CON_GPS;   // GN = multi-GNSS, определяем по PRN
  if (a == 'Q' && b == 'Z') return CON_GPS;   // QZSS (совместим с GPS)
  return CON_UNKNOWN;
}

// Для $GNGSV — определяем созвездие по PRN
Constellation conFromPRN(int prn) {
  if (prn >= 1   && prn <= 32)  return CON_GPS;
  if (prn >= 33  && prn <= 64)  return CON_SBAS;
  if (prn >= 65  && prn <= 96)  return CON_GLONASS;
  if (prn >= 120 && prn <= 158) return CON_SBAS;
  if (prn >= 201 && prn <= 263) return CON_BEIDOU;
  if (prn >= 301 && prn <= 336) return CON_GALILEO;
  if (prn >= 401 && prn <= 437) return CON_BEIDOU;
  return CON_UNKNOWN;
}

// CSV-токенизатор с поддержкой пустых полей (strtok их пропускает)
int splitCSV(char* str, char** tokens, int maxTokens) {
  int count = 0;
  tokens[count++] = str;
  while (*str && count < maxTokens) {
    if (*str == ',') {
      *str = '\0';
      tokens[count++] = str + 1;
    }
    str++;
  }
  return count;
}

// Объединить все созвездия в один массив sats[]
void mergeSatellites() {
  int total = 0;
  for (int c = 0; c < 6 && total < MAX_SATS; c++) {
    for (int i = 0; i < conSatCount[c] && total < MAX_SATS; i++) {
      sats[total++] = conSats[c][i];
    }
  }
  satCount = total;
}

void parseGSV(const char* line) {
  // $GPGSV,3,1,12,01,05,060,18,02,17,259,,04,56,287,25*77
  if (strlen(line) < 12) return;

  // Debug: сохраняем сырую строку
  strncpy(gsvDebug[gsvDebugIdx], line, 95);
  gsvDebug[gsvDebugIdx][95] = '\0';
  // Убрать \r\n из debug
  char* nl = strchr(gsvDebug[gsvDebugIdx], '\r');
  if (nl) *nl = '\0';
  nl = strchr(gsvDebug[gsvDebugIdx], '\n');
  if (nl) *nl = '\0';
  gsvDebugIdx = (gsvDebugIdx + 1) % GSV_DEBUG_SIZE;

  char talkerA = line[1], talkerB = line[2];
  bool isGN = (talkerA == 'G' && talkerB == 'N');
  Constellation talkerCon = talkerToConstellation(talkerA, talkerB);

  char buf[128];
  strncpy(buf, line, 127);
  buf[127] = '\0';

  // Убрать checksum
  char* star = strchr(buf, '*');
  if (star) *star = '\0';

  // Токенизация (поддерживает пустые поля, в отличие от strtok)
  char* tok[24];
  int tc = splitCSV(buf, tok, 24);

  if (tc < 4) return;
  int totalMsgs = atoi(tok[1]);
  int msgNum    = atoi(tok[2]);

  // Для GN: очищаем все буферы при первом сообщении первого набора
  // Для GP/GL/GA/GB: очищаем только свой буфер
  if (msgNum == 1) {
    if (isGN) {
      // GN шлёт всё в одном наборе — очищаем все
      for (int c = 0; c < 6; c++) conSatCount[c] = 0;
    } else {
      conSatCount[talkerCon] = 0;
    }
  }

  // Парсим спутники (по 4 поля на спутник, начиная с индекса 4)
  for (int i = 4; i + 3 < tc; i += 4) {
    int prn = atoi(tok[i]);
    if (prn == 0) continue;

    // Определяем созвездие: для GN — по PRN, иначе по talker
    Constellation con = isGN ? conFromPRN(prn) : talkerCon;

    // SBAS: PRN 33-64 у GP talker
    if (!isGN && talkerCon == CON_GPS && prn >= 33 && prn <= 64) con = CON_SBAS;

    if (conSatCount[con] >= MAX_SATS_PER_CON) continue;

    SatInfo s;
    s.prn  = prn;
    s.elev = atoi(tok[i + 1]);
    s.azim = atoi(tok[i + 2]);
    s.snr  = (strlen(tok[i + 3]) > 0) ? atoi(tok[i + 3]) : 0;
    s.constellation = con;

    conSats[con][conSatCount[con]++] = s;
  }

  // Последнее сообщение набора — объединяем и публикуем
  if (msgNum == totalMsgs) {
    mergeSatellites();
  }
}

void processNmeaChar(char c) {
  if (c == '$') nmeaPos = 0;
  if (nmeaPos < 127) nmeaLine[nmeaPos++] = c;
  if (c == '\n' || c == '\r') {
    nmeaLine[nmeaPos] = '\0';
    if (nmeaPos > 10 && strstr(nmeaLine, "GSV")) {
      parseGSV(nmeaLine);
    }
    nmeaPos = 0;
  }
}

void initGPS() {
  gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Serial.println("[GPS] UART2 OK");
}

void readGPS() {
  while (gpsSerial.available()) {
    char c = gpsSerial.read();
    gps.encode(c);
    processNmeaChar(c);
  }

  sensorData.fix = gps.location.isValid();
  sensorData.gpsOk = (gps.passedChecksum() > 0);

  if (sensorData.fix) {
    sensorData.lat = gps.location.lat();
    sensorData.lng = gps.location.lng();
  }
  if (gps.speed.isValid()) sensorData.speed = gps.speed.kmph();
  if (gps.altitude.isValid()) sensorData.altitude = gps.altitude.meters();
  if (gps.satellites.isValid()) sensorData.satellites = gps.satellites.value();
}

// ─── CAN ───────────────────────────────────────

static bool installCAN(int kbit, twai_mode_t mode) {
  twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, mode);
  twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
  esp_err_t err;
  if (kbit == 250) {
    twai_timing_config_t t = TWAI_TIMING_CONFIG_250KBITS();
    err = twai_driver_install(&g, &t, &f);
  } else {
    twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
    err = twai_driver_install(&g, &t, &f);
  }
  if (err != ESP_OK) return false;
  if (twai_start() != ESP_OK) { twai_driver_uninstall(); return false; }
  return true;
}

void initCAN() {
  j1939Init(&vehicle);
  obd2Init(&vehicle);
  if (installCAN(500, TWAI_MODE_LISTEN_ONLY)) {
    canBaudKbit = 500;
    canInitOk = true;
    Serial.println("[CAN] TWAI OK (listen-only, 500 kbit/s) - probing...");
  } else {
    Serial.println("[CAN] TWAI install FAIL @ 500");
  }
}

static void maybeSwitchBaud() {
  static uint32_t startMs = 0;
  static bool switched = false;
  if (startMs == 0) startMs = millis();
  if (switched || !canInitOk) return;
  if (sensorData.framesTotal > 0) { switched = true; return; }
  if (millis() - startMs < 3000) return;

  Serial.println("[CAN] No traffic @ 500 - switching to 250 kbit/s");
  twai_stop();
  twai_driver_uninstall();
  if (installCAN(250, TWAI_MODE_LISTEN_ONLY)) {
    canBaudKbit = 250;
    canInitOk = true;
    Serial.println("[CAN] TWAI OK (listen-only, 250 kbit/s)");
  } else {
    canInitOk = false;
    canBaudKbit = 0;
    Serial.println("[CAN] TWAI install FAIL @ 250");
  }
  switched = true;
}

static void maybeDetectProtocol() {
  if (canProto != PROTO_UNKNOWN || !canInitOk) return;
  if (vehicle.pgnKnownCount > 0) {
    canProto = PROTO_J1939;
    Serial.println("[PROTO] Detected: J1939 (listen-only)");
    return;
  }
  if (protoDetectDeadline == 0) {
    protoDetectDeadline = millis() + 3000;
    return;
  }
  if (millis() < protoDetectDeadline) return;

  canProto = PROTO_OBD2;
  Serial.printf("[PROTO] J1939 not found -> OBD-II. Reinstall NORMAL @ %d kbit/s\n", canBaudKbit);
  twai_stop();
  twai_driver_uninstall();
  if (installCAN(canBaudKbit, TWAI_MODE_NORMAL)) {
    Serial.println("[CAN] TWAI OK (normal, OBD-II queries)");
    obd2Enable(true);
  } else {
    canInitOk = false;
    Serial.println("[CAN] TWAI install FAIL normal");
  }
}

void readCAN() {
  maybeSwitchBaud();
  maybeDetectProtocol();
  if (!canInitOk) return;

  twai_message_t msg;
  while (twai_receive(&msg, 0) == ESP_OK) {
    sensorData.framesTotal++;
    sensorData.lastId = msg.identifier;
    sensorData.lastDlc = msg.data_length_code;
    memcpy(sensorData.lastData, msg.data, 8);

    if (msg.extd) {
      j1939Decode(msg.identifier, msg.data, msg.data_length_code);
    } else {
      obd2HandleResponse(msg.identifier, msg.data, msg.data_length_code);
    }

    // Добавить в лог
    canLog[canLogIndex].id = msg.identifier;
    canLog[canLogIndex].dlc = msg.data_length_code;
    memcpy(canLog[canLogIndex].data, msg.data, 8);
    canLog[canLogIndex].timestamp = millis();
    canLogIndex = (canLogIndex + 1) % CAN_LOG_SIZE;
  }
}

// ─── WebSocket ─────────────────────────────────

void buildJson(JsonDocument& doc) {
  JsonObject imu = doc["imu"].to<JsonObject>();
  imu["ax"] = round(sensorData.ax * 100) / 100.0;
  imu["ay"] = round(sensorData.ay * 100) / 100.0;
  imu["az"] = round(sensorData.az * 100) / 100.0;
  imu["gx"] = round(sensorData.gx * 10) / 10.0;
  imu["gy"] = round(sensorData.gy * 10) / 10.0;
  imu["gz"] = round(sensorData.gz * 10) / 10.0;
  imu["temp"] = round(sensorData.imuTemp * 10) / 10.0;
  imu["ok"] = sensorData.imuOk;

  JsonObject gpsObj = doc["gps"].to<JsonObject>();
  gpsObj["lat"] = sensorData.lat;
  gpsObj["lng"] = sensorData.lng;
  gpsObj["speed"] = round(sensorData.speed * 10) / 10.0;
  gpsObj["alt"] = round(sensorData.altitude);
  gpsObj["sats"] = sensorData.satellites;
  gpsObj["fix"] = sensorData.fix;
  gpsObj["ok"] = sensorData.gpsOk;
  gpsObj["chk"] = gps.passedChecksum();

  JsonObject can = doc["can"].to<JsonObject>();
  can["ok"] = canInitOk;
  can["frames"] = sensorData.framesTotal;
  can["baud"] = canBaudKbit;
  can["proto"] = (canProto == PROTO_J1939) ? "J1939" : (canProto == PROTO_OBD2) ? "OBD-II" : "unknown";
  can["obd2Responses"] = obd2ResponsesCount();

  JsonObject veh = doc["vehicle"].to<JsonObject>();
  auto stale = [](uint32_t ts, uint32_t t) { return ts == 0 || (millis() - ts) > t; };
  veh["rpm"] = round(vehicle.rpm * 10) / 10.0;
  veh["rpm_stale"] = stale(vehicle.ts_rpm, 2000);
  veh["speed"] = round(vehicle.speed * 10) / 10.0;
  veh["speed_stale"] = stale(vehicle.ts_speed, 3000);
  veh["coolant"] = round(vehicle.coolantTemp * 10) / 10.0;
  veh["coolant_stale"] = stale(vehicle.ts_coolant, 5000);
  veh["oil"] = round(vehicle.oilPressure);
  veh["oil_stale"] = stale(vehicle.ts_oil, 5000);
  veh["fuel"] = round(vehicle.fuelLevel * 10) / 10.0;
  veh["fuel_stale"] = stale(vehicle.ts_fuel, 5000);
  veh["voltage"] = round(vehicle.batteryVoltage * 100) / 100.0;
  veh["voltage_stale"] = stale(vehicle.ts_voltage, 5000);
  veh["fuelRate"] = round(vehicle.fuelRate * 10) / 10.0;
  veh["fuelRate_stale"] = stale(vehicle.ts_fuelRate, 5000);
  veh["load"] = round(vehicle.engineLoad);
  veh["load_stale"] = stale(vehicle.ts_load, 2000);
  veh["distance"] = vehicle.totalDistance;
  veh["distance_stale"] = stale(vehicle.ts_distance, 10000);
  veh["hours"] = round(vehicle.engineHours * 10) / 10.0;
  veh["hours_stale"] = stale(vehicle.ts_hours, 10000);
  veh["pgnKnown"] = vehicle.pgnKnownCount;
  veh["pgnUnknown"] = vehicle.pgnUnknownCount;
  veh["lastPgn"] = vehicle.lastPgnReceived;
  JsonArray dtcs = veh["dtcs"].to<JsonArray>();
  for (int i = 0; i < vehicle.dtcCount; i++) {
    JsonObject dtc = dtcs.add<JsonObject>();
    dtc["spn"] = vehicle.dtcs[i].spn;
    dtc["fmi"] = vehicle.dtcs[i].fmi;
    dtc["oc"] = vehicle.dtcs[i].oc;
  }

  JsonObject sys = doc["sys"].to<JsonObject>();
  sys["rssi"] = WiFi.RSSI();
  sys["heap"] = ESP.getFreeHeap();
  sys["uptime"] = millis() / 1000;
  sys["clients"] = ws.count();
}

void sendSensorData() {
  if (ws.count() == 0) return;

  JsonDocument doc;
  buildJson(doc);
  String json;
  serializeJson(doc, json);
  ws.textAll(json);
}

void onWsEvent(AsyncWebSocket* server, AsyncWebSocketClient* client,
               AwsEventType type, void* arg, uint8_t* data, size_t len) {
  if (type == WS_EVT_CONNECT) {
    Serial.printf("[WS] Клиент #%u подключён\n", client->id());
  } else if (type == WS_EVT_DISCONNECT) {
    Serial.printf("[WS] Клиент #%u отключён\n", client->id());
  }
}

// ─── Satellites API ────────────────────────────

void handleSatellites(AsyncWebServerRequest* request) {
  JsonDocument doc;
  JsonArray arr = doc.to<JsonArray>();
  for (int i = 0; i < satCount; i++) {
    JsonObject s = arr.add<JsonObject>();
    s["prn"]  = sats[i].prn;
    s["elev"] = sats[i].elev;
    s["azim"] = sats[i].azim;
    s["snr"]  = sats[i].snr;
    s["con"]  = sats[i].constellation;
    s["name"] = conNames[sats[i].constellation];
  }
  String json;
  serializeJson(doc, json);
  request->send(200, "application/json", json);
}

// ─── CAN Log API ───────────────────────────────

void handleCanLog(AsyncWebServerRequest* request) {
  JsonDocument doc;
  JsonArray arr = doc.to<JsonArray>();

  for (int i = 0; i < CAN_LOG_SIZE; i++) {
    int idx = (canLogIndex - 1 - i + CAN_LOG_SIZE) % CAN_LOG_SIZE;
    if (canLog[idx].timestamp == 0) break;

    JsonObject f = arr.add<JsonObject>();
    f["id"] = canLog[idx].id;
    f["dlc"] = canLog[idx].dlc;
    f["ts"] = canLog[idx].timestamp;

    String hexData;
    for (int j = 0; j < canLog[idx].dlc; j++) {
      if (j > 0) hexData += " ";
      if (canLog[idx].data[j] < 0x10) hexData += "0";
      hexData += String(canLog[idx].data[j], HEX);
    }
    f["data"] = hexData;
  }

  String json;
  serializeJson(doc, json);
  request->send(200, "application/json", json);
}

// ─── GSV Debug API ─────────────────────────────

void handleGsvDebug(AsyncWebServerRequest* request) {
  JsonDocument doc;
  JsonArray lines = doc["lines"].to<JsonArray>();
  for (int i = 0; i < GSV_DEBUG_SIZE; i++) {
    int idx = (gsvDebugIdx - GSV_DEBUG_SIZE + i + GSV_DEBUG_SIZE) % GSV_DEBUG_SIZE;
    if (gsvDebug[idx][0] != '\0') lines.add(gsvDebug[idx]);
  }
  doc["satCount"] = satCount;
  JsonObject counts = doc["conCounts"].to<JsonObject>();
  counts["GPS"] = conSatCount[CON_GPS];
  counts["GLONASS"] = conSatCount[CON_GLONASS];
  counts["Galileo"] = conSatCount[CON_GALILEO];
  counts["BeiDou"] = conSatCount[CON_BEIDOU];
  counts["SBAS"] = conSatCount[CON_SBAS];
  counts["Unknown"] = conSatCount[CON_UNKNOWN];
  String json;
  serializeJson(doc, json);
  request->send(200, "application/json", json);
}

// ─── WiFi ──────────────────────────────────────

void initWiFi() {
  struct Net { const char* ssid; const char* pass; };
  static const Net nets[] = { WIFI_NETWORKS };
  const size_t netsCount = sizeof(nets) / sizeof(nets[0]);

  Serial.print("[WiFi] Networks registered:");
  for (size_t i = 0; i < netsCount; i++) {
    wifiMulti.addAP(nets[i].ssid, nets[i].pass);
    Serial.print(" "); Serial.print(nets[i].ssid);
  }
  Serial.println();

  WiFi.mode(WIFI_STA);
  int attempts = 0;
  while (wifiMulti.run() != WL_CONNECTED && attempts < 60) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WiFi] Connected to: "); Serial.println(WiFi.SSID());
    Serial.print("[WiFi] IP: ");    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] RSSI: ");  Serial.print(WiFi.RSSI()); Serial.println(" dBm");
  } else {
    Serial.println("[WiFi] FAIL - перезагрузка через 5 сек...");
    delay(5000);
    ESP.restart();
  }
}

// ─── Web Server ────────────────────────────────

void initServer() {
  if (!LittleFS.begin(true)) {
    Serial.println("[FS] LittleFS FAIL");
    return;
  }
  Serial.println("[FS] LittleFS OK");

  ws.onEvent(onWsEvent);
  server.addHandler(&ws);

  server.on("/", HTTP_GET, [](AsyncWebServerRequest* request) {
    request->send(LittleFS, "/index.html", "text/html");
  });

  server.on("/api/satellites", HTTP_GET, handleSatellites);
  server.on("/api/canlog", HTTP_GET, handleCanLog);
  server.on("/api/vehicle", HTTP_GET, [](AsyncWebServerRequest* request) {
    JsonDocument doc;
    JsonObject veh = doc.to<JsonObject>();
    veh["rpm"] = round(vehicle.rpm * 10) / 10.0;
    veh["speed"] = round(vehicle.speed * 10) / 10.0;
    veh["coolant"] = round(vehicle.coolantTemp * 10) / 10.0;
    veh["oil"] = round(vehicle.oilPressure);
    veh["fuel"] = round(vehicle.fuelLevel * 10) / 10.0;
    veh["voltage"] = round(vehicle.batteryVoltage * 100) / 100.0;
    veh["fuelRate"] = round(vehicle.fuelRate * 10) / 10.0;
    veh["load"] = round(vehicle.engineLoad);
    veh["distance"] = vehicle.totalDistance;
    veh["hours"] = round(vehicle.engineHours * 10) / 10.0;
    veh["pgnKnown"] = vehicle.pgnKnownCount;
    veh["pgnUnknown"] = vehicle.pgnUnknownCount;
    veh["lastPgn"] = vehicle.lastPgnReceived;
    String json; serializeJson(doc, json);
    request->send(200, "application/json", json);
  });
  server.on("/api/gsv-debug", HTTP_GET, handleGsvDebug);

  server.on("/api/data", HTTP_GET, [](AsyncWebServerRequest* request) {
    JsonDocument doc;
    buildJson(doc);
    String json;
    serializeJson(doc, json);
    request->send(200, "application/json", json);
  });

  server.begin();
  Serial.println("[HTTP] Сервер запущен на порту 80");
}

// ─── Setup & Loop ──────────────────────────────

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("=================================");
  Serial.println("  VehicleLogger — Тестовый стенд");
  Serial.println("=================================");

  initWiFi();
  initIMU();
  initGPS();
  initCAN();
  initServer();

  Serial.println();
  Serial.println(">>> Откройте в браузере: http://" + WiFi.localIP().toString());
  Serial.println();
}

void loop() {
  readIMU();
  readGPS();
  readCAN();
  obd2Tick();

  if (millis() - lastWsSend >= WS_UPDATE_MS) {
    lastWsSend = millis();
    sendSensorData();
    ws.cleanupClients();
  }
}
