import serial, sys, time
port = sys.argv[1] if len(sys.argv) > 1 else 'COM6'
dur  = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
s = serial.Serial(port, 115200, timeout=0.2)
t0 = time.time()
while time.time() - t0 < dur:
    line = s.readline()
    if line:
        try:
            print(line.decode('utf-8', errors='replace').rstrip())
        except Exception:
            print(repr(line))
        sys.stdout.flush()
s.close()
