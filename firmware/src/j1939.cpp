#include "j1939.h"

static VehicleData* vd = nullptr;

// ─── Утилиты ───────────────────────────────────

// Извлечение PGN из 29-битного CAN ID
// PF = PDU Format (биты 23-16), PS = PDU Specific (биты 15-8), DP = Data Page (бит 24)
uint32_t j1939ExtractPGN(uint32_t canId) {
  uint8_t pf = (canId >> 16) & 0xFF;
  uint8_t ps = (canId >> 8) & 0xFF;
  uint8_t dp = (canId >> 24) & 0x01;
  if (pf < 240) {
    // PDU1: адресное сообщение, PS = destination, НЕ часть PGN
    return ((uint32_t)dp << 16) | ((uint32_t)pf << 8);
  }
  // PDU2: broadcast, PS = group extension, часть PGN
  return ((uint32_t)dp << 16) | ((uint32_t)pf << 8) | ps;
}

uint8_t j1939ExtractSourceAddr(uint32_t canId) {
  return canId & 0xFF;
}

// Чтение little-endian значений из data[]
static uint16_t read_u16_le(const uint8_t* d, uint8_t byte) {
  return (uint16_t)d[byte] | ((uint16_t)d[byte + 1] << 8);
}

static uint32_t read_u32_le(const uint8_t* d, uint8_t byte) {
  return (uint32_t)d[byte]
       | ((uint32_t)d[byte + 1] << 8)
       | ((uint32_t)d[byte + 2] << 16)
       | ((uint32_t)d[byte + 3] << 24);
}

// Проверка на "not available" значения в J1939
static bool isValid_u8(uint8_t v)   { return v != 0xFF && v != 0xFE; }
static bool isValid_u16(uint16_t v) { return v != 0xFFFF && v != 0xFEFF; }
static bool isValid_u32(uint32_t v) { return v != 0xFFFFFFFF && v != 0xFEFFFFFF; }

bool j1939IsStale(uint32_t ts, uint32_t timeoutMs) {
  if (ts == 0) return true;
  return (millis() - ts) > timeoutMs;
}

// ─── Декодирование конкретных PGN ──────────────

// PGN 61444 (0xF004) — EEC1: обороты двигателя
static void decode_EEC1(const uint8_t* d, uint8_t dlc) {
  if (dlc < 5) return;
  uint16_t raw = read_u16_le(d, 3);
  if (isValid_u16(raw)) {
    vd->rpm = raw * 0.125f;
    vd->ts_rpm = millis();
  }
}

// PGN 61443 (0xF003) — EEC2: нагрузка двигателя
static void decode_EEC2(const uint8_t* d, uint8_t dlc) {
  if (dlc < 3) return;
  // SPN 92: Engine Percent Load At Current Speed, байт 2, 1% / бит
  if (isValid_u8(d[2])) {
    vd->engineLoad = d[2];
    vd->ts_load = millis();
  }
}

// PGN 65265 (0xFEF1) — CCVS: скорость
static void decode_CCVS(const uint8_t* d, uint8_t dlc) {
  if (dlc < 3) return;
  // SPN 84: Wheel-Based Vehicle Speed, байты 1-2, 1/256 км/ч
  uint16_t raw = read_u16_le(d, 1);
  if (isValid_u16(raw)) {
    vd->speed = raw / 256.0f;
    vd->ts_speed = millis();
  }
}

// PGN 65262 (0xFEEE) — ET1: температура охлаждающей жидкости
static void decode_ET1(const uint8_t* d, uint8_t dlc) {
  if (dlc < 1) return;
  // SPN 110: байт 0, 1°C / бит, offset -40
  if (isValid_u8(d[0])) {
    vd->coolantTemp = (float)d[0] - 40.0f;
    vd->ts_coolant = millis();
  }
}

// PGN 65263 (0xFEEF) — EFL/P1: давление масла, уровень топлива
static void decode_EFLP1(const uint8_t* d, uint8_t dlc) {
  if (dlc >= 2) {
    // SPN 96: Fuel Level 1, байт 1, 0.4% / бит
    if (isValid_u8(d[1])) {
      vd->fuelLevel = d[1] * 0.4f;
      vd->ts_fuel = millis();
    }
  }
  if (dlc >= 4) {
    // SPN 100: Engine Oil Pressure, байт 3, 4 кПа / бит
    if (isValid_u8(d[3])) {
      vd->oilPressure = d[3] * 4.0f;
      vd->ts_oil = millis();
    }
  }
}

// PGN 65271 (0xFEF7) — EP1: напряжение бортовой сети
static void decode_EP1(const uint8_t* d, uint8_t dlc) {
  if (dlc < 6) return;
  // SPN 168: Battery Potential (Voltage), байты 4-5, 0.05 В / бит
  uint16_t raw = read_u16_le(d, 4);
  if (isValid_u16(raw)) {
    vd->batteryVoltage = raw * 0.05f;
    vd->ts_voltage = millis();
  }
}

// PGN 65266 (0xFEF2) — LFE: расход топлива
static void decode_LFE(const uint8_t* d, uint8_t dlc) {
  if (dlc < 2) return;
  // SPN 183: Engine Fuel Rate, байты 0-1, 0.05 л/ч
  uint16_t raw = read_u16_le(d, 0);
  if (isValid_u16(raw)) {
    vd->fuelRate = raw * 0.05f;
    vd->ts_fuelRate = millis();
  }
}

// PGN 65248 (0xFEE0) — VD: общий пробег
static void decode_VD(const uint8_t* d, uint8_t dlc) {
  if (dlc < 4) return;
  // SPN 245: Total Vehicle Distance, байты 0-3, 0.125 км / бит
  uint32_t raw = read_u32_le(d, 0);
  if (isValid_u32(raw)) {
    vd->totalDistance = (uint32_t)(raw * 0.125f);
    vd->ts_distance = millis();
  }
}

// PGN 65253 (0xFEE5) — HOURS: моточасы
static void decode_HOURS(const uint8_t* d, uint8_t dlc) {
  if (dlc < 4) return;
  // SPN 247: Engine Total Hours, байты 0-3, 0.05 часа / бит
  uint32_t raw = read_u32_le(d, 0);
  if (isValid_u32(raw)) {
    vd->engineHours = raw * 0.05f;
    vd->ts_hours = millis();
  }
}

// PGN 65226 (0xFECA) — DM1: активные DTC
// Формат: байты 0-1 = лампы, далее блоки по 4 байта = DTC
// DTC = SPN(19 бит) + FMI(5 бит) + CM(1 бит) + OC(7 бит)
static void decode_DM1(const uint8_t* d, uint8_t dlc) {
  if (dlc < 2) return;
  vd->dtcCount = 0;
  vd->ts_dtc = millis();
  // Обрабатываем только single-frame (до ~1 DTC в 8-байтном фрейме)
  // Multi-frame (TP.CM) — задача следующего этапа
  for (int i = 2; i + 3 < dlc && vd->dtcCount < MAX_DTCS; i += 4) {
    uint8_t b0 = d[i], b1 = d[i+1], b2 = d[i+2], b3 = d[i+3];
    // Пустой блок (все FF) — конец списка
    if (b0 == 0xFF && b1 == 0xFF && b2 == 0xFF) break;
    // SPN: байты 0-1 (младшие 16 бит) + биты 5-7 байта 2 (старшие 3 бита)
    uint32_t spn = b0 | ((uint32_t)b1 << 8) | (((uint32_t)(b2 >> 5) & 0x07) << 16);
    uint8_t  fmi = b2 & 0x1F;
    uint8_t  oc  = b3 & 0x7F;
    if (spn == 0) continue;
    vd->dtcs[vd->dtcCount].spn = spn;
    vd->dtcs[vd->dtcCount].fmi = fmi;
    vd->dtcs[vd->dtcCount].oc  = oc;
    vd->dtcCount++;
  }
}

// ─── Главный диспетчер ─────────────────────────

void j1939Init(VehicleData* v) {
  vd = v;
  memset(vd, 0, sizeof(VehicleData));
}

void j1939Decode(uint32_t canId, const uint8_t* data, uint8_t dlc) {
  if (!vd) return;
  uint32_t pgn = j1939ExtractPGN(canId);
  vd->lastPgnReceived = pgn;

  bool known = true;
  switch (pgn) {
    case 61444: decode_EEC1(data, dlc);   break;
    case 61443: decode_EEC2(data, dlc);   break;
    case 65265: decode_CCVS(data, dlc);   break;
    case 65262: decode_ET1(data, dlc);    break;
    case 65263: decode_EFLP1(data, dlc);  break;
    case 65271: decode_EP1(data, dlc);    break;
    case 65266: decode_LFE(data, dlc);    break;
    case 65248: decode_VD(data, dlc);     break;
    case 65253: decode_HOURS(data, dlc);  break;
    case 65226: decode_DM1(data, dlc);    break;
    default: known = false; break;
  }
  if (known) vd->pgnKnownCount++;
  else       vd->pgnUnknownCount++;
}
