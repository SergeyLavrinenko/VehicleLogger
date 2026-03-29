/*
 * VehicleLogger — Диагностика датчиков
 *
 * Тестирует все подключённые модули и выводит результаты в Serial Monitor.
 * Запускается один раз при включении, затем циклически читает данные.
 *
 * Подключение:
 *   WCMCU-230 (CAN):  CTX → GPIO22, CRX → GPIO21  (левая сторона)
 *   NEO-M8N (GPS):    TX  → GPIO16, RX  → GPIO17  (левая сторона)
 *   MPU-6050 (IMU):   SDA → GPIO18, SCL → GPIO19  (правая сторона)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <driver/twai.h>
#include <TinyGPSPlus.h>
#include "config.h"

// GPS через UART2
HardwareSerial gpsSerial(2);
TinyGPSPlus gps;

// ─────────────────────────────────────────────
// Вспомогательные функции
// ─────────────────────────────────────────────

void printHeader(const char* title) {
  Serial.println();
  Serial.println("════════════════════════════════════════");
  Serial.print("  ");
  Serial.println(title);
  Serial.println("════════════════════════════════════════");
}

void printResult(const char* label, bool ok) {
  Serial.print("  ");
  Serial.print(label);
  Serial.print(": ");
  Serial.println(ok ? "OK" : "FAIL");
}

// ─────────────────────────────────────────────
// Тест 1: Wi-Fi
// ─────────────────────────────────────────────

bool testWiFi() {
  printHeader("TEST 1: Wi-Fi");
  Serial.print("  Подключение к: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  bool ok = (WiFi.status() == WL_CONNECTED);
  if (ok) {
    Serial.print("  IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("  RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("  Не удалось подключиться за 10 секунд");
  }

  printResult("Wi-Fi", ok);
  WiFi.disconnect();
  return ok;
}

// ─────────────────────────────────────────────
// Тест 2: I2C scan + MPU-6050
// ─────────────────────────────────────────────

bool testMPU6050() {
  printHeader("TEST 2: I2C / MPU-6050");

  Wire.begin(MPU_SDA_PIN, MPU_SCL_PIN);

  // I2C scan
  Serial.println("  I2C scan...");
  int found = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("    Найдено устройство: 0x");
      Serial.println(addr, HEX);
      found++;
    }
  }
  Serial.print("  Устройств на шине: ");
  Serial.println(found);

  // Проверяем MPU-6050 по адресу 0x68
  Wire.beginTransmission(MPU_ADDR);
  bool mpuFound = (Wire.endTransmission() == 0);

  if (!mpuFound) {
    Serial.println("  MPU-6050 не найден на 0x68!");
    printResult("MPU-6050", false);
    return false;
  }

  // WHO_AM_I регистр (0x75) должен вернуть 0x68
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x75);
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)1);
  uint8_t whoAmI = Wire.read();
  Serial.print("  WHO_AM_I: 0x");
  Serial.print(whoAmI, HEX);
  bool whoAmIOk = (whoAmI == 0x68 || whoAmI == 0x70);
  if (whoAmI == 0x68) Serial.println(" (OK — MPU-6050)");
  else if (whoAmI == 0x70) Serial.println(" (OK — MPU-6500/клон)");
  else Serial.println(" (неизвестное значение)");

  // Разбудить MPU-6050 (регистр PWR_MGMT_1 = 0)
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0x00);
  Wire.endTransmission();
  delay(100);

  // Чтение акселерометра
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B); // ACCEL_XOUT_H
  Wire.endTransmission(false);
  Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)14);

  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();
  int16_t temp_raw = (Wire.read() << 8) | Wire.read();
  int16_t gx = (Wire.read() << 8) | Wire.read();
  int16_t gy = (Wire.read() << 8) | Wire.read();
  int16_t gz = (Wire.read() << 8) | Wire.read();

  float tempC = temp_raw / 340.0 + 36.53;

  Serial.println("  Акселерометр (raw):");
  Serial.print("    X="); Serial.print(ax);
  Serial.print("  Y="); Serial.print(ay);
  Serial.print("  Z="); Serial.println(az);

  Serial.println("  Гироскоп (raw):");
  Serial.print("    X="); Serial.print(gx);
  Serial.print("  Y="); Serial.print(gy);
  Serial.print("  Z="); Serial.println(gz);

  Serial.print("  Температура: ");
  Serial.print(tempC, 1);
  Serial.println(" C");

  // Если Z акселерометра ≈ 16384 (±1g), датчик работает правильно
  bool dataOk = (abs(az) > 8000);
  printResult("MPU-6050", mpuFound && whoAmIOk && dataOk);
  return mpuFound && whoAmIOk && dataOk;
}

// ─────────────────────────────────────────────
// Тест 3: CAN/TWAI — WCMCU-230
// ─────────────────────────────────────────────

bool testCAN() {
  printHeader("TEST 3: CAN / TWAI (WCMCU-230)");

  twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, TWAI_MODE_LISTEN_ONLY);
  twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS();
  twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

  esp_err_t err = twai_driver_install(&g_config, &t_config, &f_config);
  if (err != ESP_OK) {
    Serial.print("  TWAI install error: 0x");
    Serial.println(err, HEX);
    printResult("CAN init", false);
    return false;
  }
  Serial.println("  TWAI driver installed");

  err = twai_start();
  if (err != ESP_OK) {
    Serial.print("  TWAI start error: 0x");
    Serial.println(err, HEX);
    twai_driver_uninstall();
    printResult("CAN start", false);
    return false;
  }
  Serial.println("  TWAI started (listen-only, 500 kbit/s)");

  // Пробуем принять фреймы в течение 5 секунд
  Serial.println("  Ожидание CAN-фреймов (5 сек)...");
  int framesReceived = 0;
  unsigned long start = millis();
  while (millis() - start < 5000) {
    twai_message_t msg;
    if (twai_receive(&msg, pdMS_TO_TICKS(100)) == ESP_OK) {
      framesReceived++;
      if (framesReceived <= 5) { // показать первые 5 фреймов
        Serial.print("    ID: 0x");
        Serial.print(msg.identifier, HEX);
        Serial.print("  DLC: ");
        Serial.print(msg.data_length_code);
        Serial.print("  Data:");
        for (int i = 0; i < msg.data_length_code; i++) {
          Serial.print(" ");
          if (msg.data[i] < 0x10) Serial.print("0");
          Serial.print(msg.data[i], HEX);
        }
        Serial.println();
      }
    }
  }

  Serial.print("  Получено фреймов: ");
  Serial.println(framesReceived);

  twai_stop();
  twai_driver_uninstall();

  // CAN init прошёл — трансивер работает.
  // Фреймов может не быть если нет CAN-шины — это нормально.
  bool initOk = true;
  printResult("CAN/TWAI init", initOk);
  if (framesReceived == 0) {
    Serial.println("  (Фреймов нет — нормально если CAN-шина не подключена)");
  }
  return initOk;
}

// ─────────────────────────────────────────────
// Тест 4: GPS — NEO-M8N
// ─────────────────────────────────────────────

bool testGPS() {
  printHeader("TEST 4: GPS (NEO-M8N)");

  gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  delay(1000);

  Serial.println("  Чтение UART2 (10 сек)...");

  int bytesRead = 0;
  int nmeaSentences = 0;
  bool gotFix = false;
  unsigned long start = millis();

  while (millis() - start < 10000) {
    while (gpsSerial.available()) {
      char c = gpsSerial.read();
      bytesRead++;
      gps.encode(c);

      // Вывести первые сырые байты для отладки
      if (bytesRead <= 200) {
        Serial.print(c);
      } else if (bytesRead == 201) {
        Serial.println("\n  ... (дальше обрезано)");
      }
    }
    delay(10);
  }

  nmeaSentences = gps.sentencesWithFix() + gps.passedChecksum();

  Serial.println();
  Serial.print("  Байт получено: ");
  Serial.println(bytesRead);
  Serial.print("  NMEA предложений (checksum ok): ");
  Serial.println(gps.passedChecksum());
  Serial.print("  Ошибок checksum: ");
  Serial.println(gps.failedChecksum());

  if (gps.location.isValid()) {
    gotFix = true;
    Serial.print("  Координаты: ");
    Serial.print(gps.location.lat(), 6);
    Serial.print(", ");
    Serial.println(gps.location.lng(), 6);
    Serial.print("  Спутников: ");
    Serial.println(gps.satellites.value());
  } else {
    Serial.println("  Фикс не получен (нормально в помещении)");
    if (gps.satellites.isValid()) {
      Serial.print("  Спутников видно: ");
      Serial.println(gps.satellites.value());
    }
  }

  bool dataOk = (bytesRead > 0 && gps.passedChecksum() > 0);
  printResult("GPS UART", bytesRead > 0);
  printResult("GPS NMEA", dataOk);
  if (gotFix) printResult("GPS Fix", true);

  gpsSerial.end();
  return dataOk;
}

// ─────────────────────────────────────────────
// Итог
// ─────────────────────────────────────────────

void printSummary(bool wifi, bool mpu, bool can, bool gpsOk) {
  printHeader("ИТОГ ДИАГНОСТИКИ");
  printResult("Wi-Fi", wifi);
  printResult("MPU-6050 (I2C)", mpu);
  printResult("CAN/TWAI (WCMCU-230)", can);
  printResult("GPS (NEO-M8N)", gpsOk);
  Serial.println();

  if (wifi && mpu && can && gpsOk) {
    Serial.println("  >>> Все модули работают! <<<");
  } else {
    Serial.println("  >>> Есть проблемы, проверь подключение <<<");
  }
  Serial.println();
}

// ═════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  delay(2000); // подождать открытие Serial Monitor

  Serial.println();
  Serial.println("╔══════════════════════════════════════╗");
  Serial.println("║  VehicleLogger — Диагностика v1.0   ║");
  Serial.println("╚══════════════════════════════════════╝");
  Serial.println();
  Serial.println("Пины:");
  Serial.print("  CAN TX=GPIO"); Serial.print(CAN_TX_PIN);
  Serial.print("  RX=GPIO"); Serial.println(CAN_RX_PIN);
  Serial.print("  GPS RX=GPIO"); Serial.print(GPS_RX_PIN);
  Serial.print("  TX=GPIO"); Serial.println(GPS_TX_PIN);
  Serial.print("  I2C SDA=GPIO"); Serial.print(MPU_SDA_PIN);
  Serial.print("  SCL=GPIO"); Serial.println(MPU_SCL_PIN);

  bool wifiOk = testWiFi();
  bool mpuOk  = testMPU6050();
  bool canOk  = testCAN();
  bool gpsOk  = testGPS();

  printSummary(wifiOk, mpuOk, canOk, gpsOk);
}

void loop() {
  // Диагностика выполняется один раз в setup()
  // После завершения — ничего не делаем
  delay(10000);
}
