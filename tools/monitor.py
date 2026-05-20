#!/usr/bin/env python3
"""Capture Serial output from ESP32 for N seconds.
   DTR/RTS reset on connect, so we always see boot log."""

import sys, time, serial

PORT = "COM3"
BAUD = 115200
SECS = int(sys.argv[1]) if len(sys.argv) > 1 else 40

s = serial.Serial(PORT, BAUD, timeout=0.5)
# pulse DTR/RTS to reset ESP32
s.setDTR(False); s.setRTS(True); time.sleep(0.1)
s.setRTS(False); time.sleep(0.1)
s.reset_input_buffer()
print(f"--- {PORT} {BAUD} | reset, capturing {SECS}s ---", flush=True)

end = time.time() + SECS
buf = b""
while time.time() < end:
    data = s.read(4096)
    if not data: continue
    buf += data
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        try:
            print(line.decode("utf-8", errors="replace").rstrip("\r"), flush=True)
        except Exception:
            print(repr(line), flush=True)

if buf:
    try: print(buf.decode("utf-8", errors="replace"), end="", flush=True)
    except Exception: pass

s.close()
