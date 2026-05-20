#pragma once
#include <Arduino.h>
#include "j1939.h"

namespace Cloud {

  enum class EnrollStatus {
    Ok,
    InvalidCode,
    InvalidSubdomain,
    AlreadyClaimed,
    InvalidSecret,
    Deactivated,
    NetworkError,
    UnknownError,
  };

  enum class PostResult {
    Ok,
    Unauthorized,      // 401 — apiKey отозван
    Deactivated,       // 410
    BadRequest,        // 400
    NetworkError,
    UnknownError,
  };

  // POST https://<subdomain>.<BASE_DOMAIN>/api/devices/enroll
  // На Ok заполняет outApiKey/outBackendUrl/outSendIntervalMs.
  EnrollStatus enroll(const String& subdomain,
                      const String& enrollCode,
                      String& outApiKey,
                      String& outBackendUrl,
                      uint32_t& outSendIntervalMs);

  // POST <backendUrl>/api/telemetry с Authorization: Bearer <apiKey>.
  // Поля, ts_xxx которых старше staleMs (или 0), отправляются как null.
  PostResult sendTelemetry(const VehicleData& v, uint32_t staleMs = 5000);

  // POST <backendUrl>/api/device/ping
  PostResult ping();
}
