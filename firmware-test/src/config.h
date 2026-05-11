#pragma once

// ─── CAN (TWAI) ─────────────────────────────
#define CAN_TX_PIN    GPIO_NUM_22
#define CAN_RX_PIN    GPIO_NUM_21

// ─── GPS (NEO-M8N) — UART2 ──────────────────
#define GPS_RX_PIN    16
#define GPS_TX_PIN    17
#define GPS_BAUD      9600

// ─── IMU (MPU-6050) — I2C ───────────────────
#define MPU_SDA_PIN   18
#define MPU_SCL_PIN   19
#define MPU_ADDR      0x68

// ─── Веб-дашборд ─────────────────────────────
#define WS_UPDATE_MS  200

// ─── WiFi сети (можно несколько) ────────────
// Оставить пустой массив — устройство просто не пойдёт в сеть и будет
// крутить CAN/IMU/GPS диагностику только в Serial.
#define WIFI_NETWORKS \
  { "iPhone", "claudeloves" }
