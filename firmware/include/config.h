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

// ─── Провизионинг ───────────────────────────
#define AP_PASSWORD          "setup1234"          // пароль SoftAP, печатается на наклейке
#define BASE_DOMAIN          "example.com"        // <subdomain>.example.com
#define WIFI_RETRY_COUNT     5

// ─── Сброс / индикация ──────────────────────
#define RESET_BUTTON_PIN     GPIO_NUM_0           // BOOT-кнопка на DevKit
#define LED_PIN              GPIO_NUM_2
