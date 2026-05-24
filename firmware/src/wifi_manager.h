#pragma once
#include <Arduino.h>

namespace WifiManager {
  // Подключиться по сохранённым в NVS WiFi-кредам. Блокирующий до timeout.
  // Возвращает true если WL_CONNECTED.
  bool connectFromNvs(uint32_t timeoutMs = 20000);

  // Опросить состояние; если WL_CONNECTED — true, иначе попытка реконнекта.
  bool ensureConnected();

  // True если автоматически следует уйти в SoftAP (captive portal).
  //
  // Сценарии:
  //   - устройство только включилось и за минуту не подключилось ни разу
  //   - устройство работало, но связь потеряна более 5 минут
  //
  // Решение принимается в main.cpp: NvsStore::resetWifi() + ESP.restart()
  // вернёт устройство в SoftAP без потери api_key.
  bool shouldFallbackToSoftAp();
}