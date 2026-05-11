#include "can_module.h"
#include "config.h"
#include "obd2.h"

#include <driver/twai.h>

namespace {
  VehicleData* s_vehicle    = nullptr;
  bool         s_ok           = false;
  int          s_baudKbit     = 0;
  uint32_t     s_frames       = 0;
  uint32_t     s_initMs       = 0;
  uint32_t     s_baudSwitchMs = 0;
  int          s_switchPhase  = 0;     // 0=initial 500, 1=tried 250, 2=back to 500 (final)

  CanModule::Proto s_proto = CanModule::PROTO_UNKNOWN;
  uint32_t s_protoDeadline = 0;

  bool installCAN(int kbit, twai_mode_t mode) {
    twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_PIN, CAN_RX_PIN, mode);
    twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    esp_err_t err;
    if (kbit == 250) {
      twai_timing_config_t t = TWAI_TIMING_CONFIG_250KBITS();
      err = twai_driver_install(&g, &t, &f);
    } else {
      twai_timing_config_t t = TWAI_TIMING_CONFIG_500KBITS();
      err = twai_driver_install(&g, &t, &f);
    }
    if (err != ESP_OK) return false;
    if (twai_start() != ESP_OK) { twai_driver_uninstall(); return false; }
    return true;
  }

  void maybeSwitchBaud() {
    if (!s_ok || s_switchPhase >= 2) return;
    if (s_frames > 0) { s_switchPhase = 2; return; }   // нашли трафик — финализируемся

    uint32_t since = millis() - (s_baudSwitchMs ? s_baudSwitchMs : s_initMs);
    if (since < 8000) return;                          // даём 8 сек на каждую скорость

    if (s_switchPhase == 0) {
      Serial.println("[CAN] no traffic @ 500 — try 250");
      twai_stop();
      twai_driver_uninstall();
      if (installCAN(250, TWAI_MODE_LISTEN_ONLY)) {
        s_baudKbit     = 250;
        s_baudSwitchMs = millis();
        s_switchPhase  = 1;
        Serial.println("[CAN] TWAI OK (listen-only, 250 kbit/s)");
      } else {
        s_ok = false;
        s_baudKbit = 0;
        Serial.println("[CAN] TWAI install FAIL @ 250");
        s_switchPhase = 2;
      }
    } else if (s_switchPhase == 1) {
      Serial.println("[CAN] no traffic @ 250 — back to 500 (final)");
      twai_stop();
      twai_driver_uninstall();
      if (installCAN(500, TWAI_MODE_LISTEN_ONLY)) {
        s_baudKbit     = 500;
        s_baudSwitchMs = millis();
        Serial.println("[CAN] TWAI OK (listen-only, 500 kbit/s, final)");
      } else {
        s_ok = false;
        s_baudKbit = 0;
        Serial.println("[CAN] TWAI install FAIL @ 500 (retry)");
      }
      s_switchPhase = 2;
    }
  }

  void maybeDetectProtocol() {
    if (s_proto != CanModule::PROTO_UNKNOWN || !s_ok || !s_vehicle) return;

    if (s_vehicle->pgnKnownCount > 0) {
      s_proto = CanModule::PROTO_J1939;
      Serial.println("[PROTO] J1939 (listen-only)");
      return;
    }
    if (s_protoDeadline == 0) { s_protoDeadline = millis() + 3000; return; }
    if (millis() < s_protoDeadline) return;

    s_proto = CanModule::PROTO_OBD2;
    Serial.printf("[PROTO] J1939 not found — reinstall NORMAL @ %d kbit/s for OBD-II\n", s_baudKbit);
    twai_stop();
    twai_driver_uninstall();
    if (installCAN(s_baudKbit, TWAI_MODE_NORMAL)) {
      obd2Enable(true);
      Serial.println("[CAN] TWAI OK (normal, OBD-II poll)");
    } else {
      s_ok = false;
      Serial.println("[CAN] TWAI install FAIL normal");
    }
  }
}

namespace CanModule {

  bool begin(VehicleData* out) {
    s_vehicle = out;
    j1939Init(out);
    obd2Init(out);

    if (!installCAN(500, TWAI_MODE_LISTEN_ONLY)) {
      Serial.println("[CAN] TWAI install FAIL @ 500");
      s_ok = false;
      return false;
    }
    s_ok = true;
    s_baudKbit = 500;
    s_initMs = millis();
    Serial.println("[CAN] TWAI OK (listen-only, 500 kbit/s) — probing...");
    return true;
  }

  void tick() {
    if (!s_ok) return;
    maybeSwitchBaud();
    maybeDetectProtocol();

    twai_message_t msg;
    while (twai_receive(&msg, 0) == ESP_OK) {
      s_frames++;
      if (msg.extd) {
        j1939Decode(msg.identifier, msg.data, msg.data_length_code);
      } else {
        obd2HandleResponse(msg.identifier, msg.data, msg.data_length_code);
      }
    }

    obd2Tick();
  }

  uint32_t framesTotal() { return s_frames; }
  int      baudKbit()    { return s_baudKbit; }
  Proto    proto()       { return s_proto; }
}
