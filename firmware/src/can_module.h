#pragma once
#include <Arduino.h>
#include "j1939.h"

namespace CanModule {
  enum Proto { PROTO_UNKNOWN = 0, PROTO_J1939 = 1, PROTO_OBD2 = 2 };

  // Инициализирует TWAI на 500 kbit/s в listen-only, готовит auto-baud/auto-proto.
  // Привязывает структуру `out` к декодерам.
  bool begin(VehicleData* out);

  // Вызывать из loop(): драйвер TWAI приём, авто-переключение скорости/протокола.
  void tick();

  // Статистика для логов.
  uint32_t framesTotal();
  int      baudKbit();
  Proto    proto();
}
