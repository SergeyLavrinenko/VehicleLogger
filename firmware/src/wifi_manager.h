#pragma once
#include <Arduino.h>

namespace WifiManager {
  // Подключиться по сохранённым в NVS WiFi-кредам. Блокирующий до timeout.
  // Возвращает true если WL_CONNECTED.
  bool connectFromNvs(uint32_t timeoutMs = 20000);

  // Опросить состояние; если WL_CONNECTED — true, иначе попытка реконнекта.
  bool ensureConnected();
}
