#pragma once

namespace Provisioning {
  // Запускает SoftAP + captive portal. Блокирующий вызов: после успешной
  // настройки выполняет ESP.restart() и не возвращается.
  // На этапе 3 после WiFi connect — сохраняет ssid/password в NVS и
  // переводит enroll state в "ok" (заглушка до этапа 5 / cloud::enroll).
  void start();
}
