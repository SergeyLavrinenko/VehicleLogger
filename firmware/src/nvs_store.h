#pragma once
#include <Arduino.h>

// Обёртка над ESP32 Preferences (NVS). Три namespace:
//   factory/  — серийник + секрет (записывает заводской скрипт)
//   wifi/     — SSID + пароль (заполняется через captive portal)
//   cloud/    — api_key + backend_url + send_interval_ms (после /enroll)
namespace NvsStore {

  void begin();   // вызвать один раз в setup()

  // ── Factory ────────────────────────────────
  bool   hasFactoryData();
  String getSerial();
  String getSecretHex();              // 64 hex символа
  void   setSerial(const String& s);
  void   setSecretHex(const String& h);

  // Bring-up (первый запуск): если factory пустой, генерируем serial из MAC и random secret.
  // В продакшене эту функцию не вызываем — данные пишет заводской скрипт через esptool.
  void   bringUpFactoryDefaults();

  // ── WiFi ───────────────────────────────────
  bool   getWifi(String& ssid, String& password);
  void   setWifi(const String& ssid, const String& password);
  void   clearWifi();

  // ── Cloud ──────────────────────────────────
  bool     getApiKey(String& key);
  void     setApiKey(const String& key);
  void     clearApiKey();

  String   getBackendUrl();           // пусто если ещё не enrolled
  void     setBackendUrl(const String& url);

  uint32_t getSendIntervalMs(uint32_t fallback = 5000);
  void     setSendIntervalMs(uint32_t ms);

  // ── Reset ──────────────────────────────────
  void resetWifi();         // 5-сек reset: только wifi/*
  void resetCloud();         // стирает cloud/*
  void factoryReset();       // 10-сек reset: wifi/* + cloud/*, сохраняет factory/*
}
