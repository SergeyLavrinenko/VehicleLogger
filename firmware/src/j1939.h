/*
 * SAE J1939 декодер для грузовых автомобилей.
 * Работает в режиме listen-only — все параметры приходят широковещательно.
 */
#pragma once

#include <Arduino.h>

// ─── Данные автомобиля ─────────────────────────

#define MAX_DTCS 8

struct DtcEntry {
  uint32_t spn;   // Suspect Parameter Number
  uint8_t  fmi;   // Failure Mode Identifier
  uint8_t  oc;    // Occurrence Count
};

struct VehicleData {
  // Двигатель
  float    rpm;               // SPN 190, об/мин
  float    engineLoad;        // SPN 92,  %
  float    coolantTemp;       // SPN 110, °C
  float    oilPressure;       // SPN 100, кПа

  // Движение
  float    speed;             // SPN 84,  км/ч
  uint32_t totalDistance;     // SPN 245, км

  // Топливо
  float    fuelLevel;         // SPN 96,  %
  float    fuelRate;          // SPN 183, л/ч

  // Электрика
  float    batteryVoltage;    // SPN 168, В

  // Моточасы
  float    engineHours;       // SPN 247, часы

  // DTC (активные, из DM1)
  uint8_t   dtcCount;
  DtcEntry  dtcs[MAX_DTCS];

  // Таймстампы последнего обновления (millis)
  uint32_t ts_rpm, ts_load, ts_coolant, ts_oil;
  uint32_t ts_speed, ts_distance;
  uint32_t ts_fuel, ts_fuelRate;
  uint32_t ts_voltage;
  uint32_t ts_hours;
  uint32_t ts_dtc;

  // Счётчики для диагностики
  uint32_t pgnKnownCount;     // кол-во распознанных PGN
  uint32_t pgnUnknownCount;   // кол-во неизвестных PGN (29-бит)
  uint32_t lastPgnReceived;   // последний полученный PGN
};

// ─── API ───────────────────────────────────────

void j1939Init(VehicleData* v);
uint32_t j1939ExtractPGN(uint32_t canId);
uint8_t  j1939ExtractSourceAddr(uint32_t canId);
void j1939Decode(uint32_t canId, const uint8_t* data, uint8_t dlc);

// Устарели ли данные? (millis() - ts > timeoutMs)
bool j1939IsStale(uint32_t ts, uint32_t timeoutMs);
