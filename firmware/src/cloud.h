#pragma once
#include <Arduino.h>

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

  // POST https://<subdomain>.<BASE_DOMAIN>/api/devices/enroll
  // На Ok заполняет outApiKey/outBackendUrl/outSendIntervalMs.
  EnrollStatus enroll(const String& subdomain,
                      const String& enrollCode,
                      String& outApiKey,
                      String& outBackendUrl,
                      uint32_t& outSendIntervalMs);
}