#pragma once
#include <Arduino.h>
#include <stdint.h>

namespace MqttClient {

  /// Инициализация: читает из NVS адрес брокера, порт, серийник, api_key, тенант.
  /// Возвращает true если конфигурация валидна и клиент готов к подключению.
  bool begin();

  /// Должен вызываться часто в основном цикле для обработки входящих пакетов и keepalive.
  void loop();

  /// Возвращает true если есть активное соединение с брокером.
  bool isConnected();

  /// Публикует тело телеметрии в топик vl/{tenant}/{serial}/telemetry с QoS=1.
  bool publishTelemetry(const String& json);

  /// Публикует heartbeat в топик vl/{tenant}/{serial}/ping с QoS=1.
  bool publishPing(const String& json);
}