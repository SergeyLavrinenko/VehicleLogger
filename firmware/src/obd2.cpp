/*
 * Реализация OBD-II опроса.
 * Таблица PIDs → формулы → поля VehicleData.
 * Шлёт по одному запросу каждые OBD2_REQUEST_INTERVAL_MS, ротируя список.
 */
#include "obd2.h"
#include <driver/twai.h>

// ─── Конфиг ───────────────────────────────────

static const uint32_t OBD2_REQUEST_INTERVAL_MS = 100;  // интервал между запросами
static const uint32_t OBD2_FUNCTIONAL_REQ_ID   = 0x7DF; // функциональный broadcast
// Ответы: 0x7E8..0x7EF (Engine=0x7E8, Trans=0x7E9, и т.д.)

// ─── PID-таблица ──────────────────────────────

enum PidFormula : uint8_t {
  F_A,                 // A
  F_A_MINUS_40,        // A - 40          (температуры)
  F_A_X_100_DIV_255,   // A * 100 / 255   (проценты)
  F_AB_DIV_4,          // (256A+B) / 4    (RPM)
  F_AB_DIV_20,         // (256A+B) / 20   (л/ч)
  F_AB_DIV_1000,       // (256A+B) / 1000 (вольты)
  F_AB,                // (256A+B)        (километры, часы)
};

struct ObdPid {
  uint8_t      pid;          // идентификатор PID (Mode 01)
  uint8_t      formula;      // как декодировать
  size_t       fieldOffset;  // куда писать в VehicleData
  size_t       tsOffset;     // куда писать timestamp
  const char*  name;
};

#define VD_OFF(field) offsetof(VehicleData, field)

static const ObdPid PIDS[] = {
  { 0x04, F_A_X_100_DIV_255, VD_OFF(engineLoad),     VD_OFF(ts_load),     "Load"    },
  { 0x05, F_A_MINUS_40,      VD_OFF(coolantTemp),    VD_OFF(ts_coolant),  "Coolant" },
  { 0x0C, F_AB_DIV_4,        VD_OFF(rpm),            VD_OFF(ts_rpm),      "RPM"     },
  { 0x0D, F_A,               VD_OFF(speed),          VD_OFF(ts_speed),    "Speed"   },
  { 0x2F, F_A_X_100_DIV_255, VD_OFF(fuelLevel),      VD_OFF(ts_fuel),     "Fuel"    },
  { 0x42, F_AB_DIV_1000,     VD_OFF(batteryVoltage), VD_OFF(ts_voltage),  "Voltage" },
  { 0x5E, F_AB_DIV_20,       VD_OFF(fuelRate),       VD_OFF(ts_fuelRate), "FuelRate"},
};
static const size_t PIDS_COUNT = sizeof(PIDS) / sizeof(PIDS[0]);

// ─── Состояние ─────────────────────────────────

static VehicleData* vd = nullptr;
static uint32_t     lastReqMs = 0;
static size_t       nextPidIdx = 0;
static bool         enabled = false;
static uint32_t     responsesCount = 0;

// ─── Init / Enable ─────────────────────────────

void obd2Init(VehicleData* v) {
  vd = v;
  lastReqMs = 0;
  nextPidIdx = 0;
  enabled = false;
  responsesCount = 0;
}

void obd2Enable(bool on) {
  enabled = on;
  if (on) {
    Serial.println("[OBD2] Опрос включён");
  } else {
    Serial.println("[OBD2] Опрос выключен");
  }
}

bool obd2IsEnabled() { return enabled; }
uint32_t obd2ResponsesCount() { return responsesCount; }

// ─── Запрос ────────────────────────────────────

static bool sendRequest(uint8_t pid) {
  twai_message_t msg = {};
  msg.identifier = OBD2_FUNCTIONAL_REQ_ID;
  msg.extd = 0;               // 11-бит
  msg.data_length_code = 8;
  msg.data[0] = 0x02;          // длина полезной нагрузки (Mode + PID)
  msg.data[1] = 0x01;          // Mode 01: current data
  msg.data[2] = pid;
  msg.data[3] = 0x55;          // padding (ISO 15765 требует DLC=8)
  msg.data[4] = 0x55;
  msg.data[5] = 0x55;
  msg.data[6] = 0x55;
  msg.data[7] = 0x55;
  return twai_transmit(&msg, pdMS_TO_TICKS(10)) == ESP_OK;
}

bool obd2Tick() {
  if (!enabled || !vd) return false;
  uint32_t now = millis();
  if (now - lastReqMs < OBD2_REQUEST_INTERVAL_MS) return false;
  lastReqMs = now;

  const ObdPid& p = PIDS[nextPidIdx];
  sendRequest(p.pid);
  nextPidIdx = (nextPidIdx + 1) % PIDS_COUNT;
  return true;
}

// ─── Разбор ответа ─────────────────────────────

static float applyFormula(uint8_t formula, uint8_t A, uint8_t B) {
  switch (formula) {
    case F_A:               return (float)A;
    case F_A_MINUS_40:      return (float)A - 40.0f;
    case F_A_X_100_DIV_255: return (float)A * 100.0f / 255.0f;
    case F_AB_DIV_4:        return (float)((uint16_t)A * 256 + B) / 4.0f;
    case F_AB_DIV_20:       return (float)((uint16_t)A * 256 + B) / 20.0f;
    case F_AB_DIV_1000:     return (float)((uint16_t)A * 256 + B) / 1000.0f;
    case F_AB:              return (float)((uint16_t)A * 256 + B);
  }
  return 0;
}

static void writeField(const ObdPid& p, float value) {
  uint8_t* base = (uint8_t*)vd;
  // Целочисленное поле только для distance (uint32_t).
  if (p.fieldOffset == VD_OFF(totalDistance)) {
    *(uint32_t*)(base + p.fieldOffset) = (uint32_t)value;
  } else {
    *(float*)(base + p.fieldOffset) = value;
  }
  *(uint32_t*)(base + p.tsOffset) = millis();
}

bool obd2HandleResponse(uint32_t canId, const uint8_t* data, uint8_t dlc) {
  // Ответы: 0x7E8..0x7EF
  if (canId < 0x7E8 || canId > 0x7EF) return false;
  if (dlc < 3) return false;
  // data[0] = длина, data[1] должен быть 0x41 (Mode 01 ответ), data[2] = PID
  if (data[1] != 0x41) return false;

  uint8_t pid = data[2];
  for (size_t i = 0; i < PIDS_COUNT; i++) {
    if (PIDS[i].pid != pid) continue;
    uint8_t A = (dlc > 3) ? data[3] : 0;
    uint8_t B = (dlc > 4) ? data[4] : 0;
    float v = applyFormula(PIDS[i].formula, A, B);
    writeField(PIDS[i], v);
    responsesCount++;
    return true;
  }
  return false; // PID не в нашей таблице — игнорируем
}
