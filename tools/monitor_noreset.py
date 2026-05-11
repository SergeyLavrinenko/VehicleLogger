#!/usr/bin/env python3
"""Read serial WITHOUT touching DTR/RTS (no reset)."""
import sys, time, serial

PORT = "COM3"
BAUD = 115200
SECS = int(sys.argv[1]) if len(sys.argv) > 1 else 20

# dsrdtr=False / rtscts=False prevents auto-toggle on some platforms
s = serial.Serial()
s.port = PORT
s.baudrate = BAUD
s.timeout = 0.5
s.dsrdtr = False
s.rtscts = False
# Force lines HIGH so ESP32 doesn't reset on open
s.dtr = True
s.rts = True
s.open()
print(f"--- {PORT} {BAUD} | no-reset | capturing {SECS}s ---", flush=True)

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
s.close()
