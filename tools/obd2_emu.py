"""
OBD-II ECU emulator на USBCAN-2A.
Слушает CH0 в режиме NORMAL @ 250/500 kbit/s, отвечает на запросы 0x7DF.
Значения = Volvo S80 на холостом ходу.

Запуск: python obd2_emu.py [kbit] [duration_sec]
"""
import ctypes as C, os, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
dll = C.WinDLL(os.path.join(ROOT, "ControlCAN.dll"))

VCI_USBCAN2 = 4
STATUS_OK = 1

class VCI_INIT_CONFIG(C.Structure):
    _fields_ = [("AccCode",C.c_uint32),("AccMask",C.c_uint32),
                ("Reserved",C.c_uint32),("Filter",C.c_ubyte),
                ("Timing0",C.c_ubyte),("Timing1",C.c_ubyte),("Mode",C.c_ubyte)]

class VCI_CAN_OBJ(C.Structure):
    _fields_ = [("ID",C.c_uint32),("TimeStamp",C.c_uint32),
                ("TimeFlag",C.c_ubyte),("SendType",C.c_ubyte),
                ("RemoteFlag",C.c_ubyte),("ExternFlag",C.c_ubyte),
                ("DataLen",C.c_ubyte),("Data",C.c_ubyte*8),
                ("Reserved",C.c_ubyte*3)]

# timings
TIMINGS = {
    250: (0x01, 0x1C),
    500: (0x00, 0x1C),
}

# Mode 01 PID -> (формула, значение) — возвращает payload байт A, B (или только A)
# Volvo S80 2009 на холостом: RPM=750, Speed=0, Coolant=88, Load=22%, Fuel=45%, V=14.3, Rate=1.1
def pid_response(pid):
    if pid == 0x04:   # Engine load %
        pct = 22
        A = int(pct * 255 / 100)
        return bytes([0x03, 0x41, pid, A, 0x55, 0x55, 0x55, 0x55])
    if pid == 0x05:   # Coolant °C
        temp = 88
        A = temp + 40
        return bytes([0x03, 0x41, pid, A, 0x55, 0x55, 0x55, 0x55])
    if pid == 0x0C:   # RPM
        rpm = 750
        raw = int(rpm * 4)
        return bytes([0x04, 0x41, pid, (raw >> 8) & 0xFF, raw & 0xFF, 0x55, 0x55, 0x55])
    if pid == 0x0D:   # Speed km/h
        return bytes([0x03, 0x41, pid, 0, 0x55, 0x55, 0x55, 0x55])
    if pid == 0x2F:   # Fuel level %
        pct = 45
        A = int(pct * 255 / 100)
        return bytes([0x03, 0x41, pid, A, 0x55, 0x55, 0x55, 0x55])
    if pid == 0x42:   # Control module voltage
        v = 14.3
        raw = int(v * 1000)
        return bytes([0x04, 0x41, pid, (raw >> 8) & 0xFF, raw & 0xFF, 0x55, 0x55, 0x55])
    if pid == 0x5E:   # Fuel rate L/h
        rate = 1.1
        raw = int(rate * 20)
        return bytes([0x04, 0x41, pid, (raw >> 8) & 0xFF, raw & 0xFF, 0x55, 0x55, 0x55])
    return None

def main():
    kbit = int(sys.argv[1]) if len(sys.argv) > 1 else 250
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    assert kbit in TIMINGS, "kbit: 250 or 500"
    BTR0, BTR1 = TIMINGS[kbit]

    assert dll.VCI_OpenDevice(VCI_USBCAN2, 0, 0) == STATUS_OK, "open failed"
    cfg = VCI_INIT_CONFIG(0, 0xFFFFFFFF, 0, 0, BTR0, BTR1, 0)
    assert dll.VCI_InitCAN(VCI_USBCAN2, 0, 0, C.byref(cfg)) == STATUS_OK, "init ch0"
    assert dll.VCI_StartCAN(VCI_USBCAN2, 0, 0) == STATUS_OK, "start ch0"

    print(f"[obd2-emu] CH0 NORMAL @ {kbit} kbit/s, emulating ECU 0x7E8 for {duration}s")

    t0 = time.time()
    received = 0
    sent = 0
    while time.time() - t0 < duration:
        # Принимаем до 10 пакетов в пачке
        buf = (VCI_CAN_OBJ * 10)()
        n = dll.VCI_Receive(VCI_USBCAN2, 0, 0, buf, 10, 20)  # 20 мс timeout
        if n <= 0:
            continue
        for i in range(n):
            m = buf[i]
            if m.ExternFlag != 0:
                continue  # только 11-bit
            received += 1
            if m.ID != 0x7DF:
                continue
            if m.DataLen < 3:
                continue
            # формат запроса: [len, 0x01, PID, ...]
            if m.Data[1] != 0x01:
                continue
            pid = m.Data[2]
            resp = pid_response(pid)
            if resp is None:
                continue
            out = VCI_CAN_OBJ()
            out.ID = 0x7E8  # Engine ECU
            out.SendType = 0
            out.RemoteFlag = 0
            out.ExternFlag = 0
            out.DataLen = 8
            for j, b in enumerate(resp):
                out.Data[j] = b
            r = dll.VCI_Transmit(VCI_USBCAN2, 0, 0, C.byref(out), 1)
            if r == STATUS_OK:
                sent += 1
                print(f"  RX req PID=0x{pid:02X} -> TX resp 0x7E8 {' '.join(f'{b:02X}' for b in resp)}")

    dll.VCI_ResetCAN(VCI_USBCAN2, 0, 0)
    dll.VCI_CloseDevice(VCI_USBCAN2, 0)
    print(f"\n[obd2-emu] RX={received} 11-bit frames, TX responses={sent}")

main()
