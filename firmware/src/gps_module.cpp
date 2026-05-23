#include "gps_module.h"
#include "config.h"
#include <HardwareSerial.h>
#include <TinyGPSPlus.h>

namespace GpsModule {

  namespace {
    HardwareSerial gpsSerial(2);   // UART2
    TinyGPSPlus    gps;
    bool           inited        = false;
    uint32_t       lastFixMillis = 0;
  }

  void begin() {
    if (inited) return;
    gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    inited = true;
    Serial.printf("[GPS] UART2 init RX=%d TX=%d baud=%d\n",
                  (int)GPS_RX_PIN, (int)GPS_TX_PIN, (int)GPS_BAUD);
  }

  void tick() {
    if (!inited) return;
    while (gpsSerial.available()) {
      char c = gpsSerial.read();
      if (gps.encode(c)) {
        // Полное предложение собрано
        if (gps.location.isValid() && gps.location.isUpdated()) {
          lastFixMillis = millis();
        }
      }
    }
  }

  Snapshot snapshot(uint32_t maxAgeMs) {
    Snapshot s;
    if (!inited) return s;
    if (lastFixMillis == 0) return s;
    if (millis() - lastFixMillis > maxAgeMs) return s;
    s.valid      = true;
    s.lat        = gps.location.lat();
    s.lng        = gps.location.lng();
    s.altitudeM  = gps.altitude.isValid() ? gps.altitude.meters() : 0.0;
    s.speedKmh   = gps.speed.isValid()    ? gps.speed.kmph()       : 0.0;
    s.courseDeg  = gps.course.isValid()   ? gps.course.deg()       : 0.0;
    s.satellites = gps.satellites.isValid() ? (uint8_t)gps.satellites.value() : 0;
    // Тип фикса: TinyGPSPlus напрямую не выдаёт, оцениваем по числу спутников и валидности
    s.fix = (s.satellites >= 4) ? 2 : (s.satellites >= 3 ? 1 : 0);
    return s;
  }

  uint32_t lastFixAgeMs() {
    if (lastFixMillis == 0) return 0;
    return millis() - lastFixMillis;
  }
}