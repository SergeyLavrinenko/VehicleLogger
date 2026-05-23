#pragma once
#include <Arduino.h>
#include <stdint.h>

namespace GpsModule {

  /// Свежий снимок данных от GPS-модуля. Все поля валидны, только если valid == true
  /// и поле hasFix / hasAlt / hasSpeed / hasCourse соответствует.
  struct Snapshot {
    double  lat        = 0.0;
    double  lng        = 0.0;
    double  altitudeM  = 0.0;
    double  speedKmh   = 0.0;
    double  courseDeg  = 0.0;
    uint8_t satellites = 0;
    uint8_t fix        = 0;     // 0=нет, 1=2D, 2=3D
    bool    valid      = false;
  };

  /// Инициализация UART к GPS-модулю. Безопасно вызвать второй раз — внутренне идемпотентно.
  void begin();

  /// Должна вызываться часто в цикле — читает входящие байты NMEA и обновляет внутреннее состояние.
  void tick();

  /// Возвращает свежий снимок, если фикс был обновлён не раньше maxAgeMs миллисекунд назад.
  /// Если данные старее — возвращает Snapshot со valid = false.
  Snapshot snapshot(uint32_t maxAgeMs = 10000);

  /// Возраст последнего валидного фикса в миллисекундах (от millis()). 0 если фикса не было.
  uint32_t lastFixAgeMs();
}