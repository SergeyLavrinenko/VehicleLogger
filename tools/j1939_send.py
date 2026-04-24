"""
J1939 frame sender for USBCAN-2A.
Opens both CH0+CH1 at 250 kbit/s NORMAL mode so they ACK each other
(firmware-test is in LISTEN_ONLY и сам не даёт ACK).
Отсылает через CH0 реалистичные J1939-кадры.
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

# 250 kbit/s SJA1000 @16 MHz
BTR0, BTR1 = 0x01, 0x1C

def build_j1939_id(prio, pgn, sa):
    # broadcast: PF >= 240 → PS уже в PGN, DP=0
    # ID = prio(3) | R(1)=0 | DP(1)=0 | PF(8) | PS(8) | SA(8)
    return ((prio & 7) << 26) | ((pgn & 0xFFFF) << 8) | (sa & 0xFF)

# Набор кадров: значения = «грузовик на холостом»
#  RPM=800, Speed=0, Coolant=85°C, Oil=300 kPa, Fuel=65%, V=24.5В, Load=15%, FuelRate=5.2 л/ч, Distance=123456 км, Hours=1500.5
def build_payload_eec1():
    # PGN 61444, SPN 190 RPM в байтах 3-4 (LE), res=0.125, offset=0
    rpm = 800
    raw = int(rpm / 0.125) & 0xFFFF
    return bytes([0xFF,0xFF,0xFF, raw & 0xFF, (raw>>8) & 0xFF, 0xFF,0xFF,0xFF])

def build_payload_ccvs():
    # PGN 65265, SPN 84 Speed байты 1-2 (LE), res=1/256
    speed = 0
    raw = int(speed * 256) & 0xFFFF
    return bytes([0xFF, raw & 0xFF, (raw>>8) & 0xFF, 0xFF,0xFF,0xFF,0xFF,0xFF])

def build_payload_et1():
    # PGN 65262, SPN 110 Coolant байт 0, res=1, offset=-40
    coolant_c = 85
    raw = int(coolant_c - (-40)) & 0xFF
    return bytes([raw, 0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF])

def build_payload_eflp1():
    # PGN 65263, SPN 100 Oil pressure байт 3, res=4, offset=0
    # SPN 96 Fuel level байт 1, res=0.4, offset=0
    oil_kpa = 300
    fuel_pct = 65
    return bytes([0xFF, int(fuel_pct/0.4) & 0xFF, 0xFF, int(oil_kpa/4) & 0xFF, 0xFF,0xFF,0xFF,0xFF])

def build_payload_ep1():
    # PGN 65271, SPN 168 Voltage байты 4-5 LE, res=0.05
    volt = 24.5
    raw = int(volt / 0.05) & 0xFFFF
    return bytes([0xFF,0xFF,0xFF,0xFF, raw & 0xFF, (raw>>8) & 0xFF, 0xFF,0xFF])

def build_payload_lfe():
    # PGN 65266, SPN 183 Fuel rate байты 0-1 LE, res=0.05
    rate = 5.2
    raw = int(rate / 0.05) & 0xFFFF
    return bytes([raw & 0xFF, (raw>>8) & 0xFF, 0xFF,0xFF,0xFF,0xFF,0xFF,0xFF])

def build_payload_eec2():
    # PGN 61443, SPN 92 Engine load байт 2, res=1
    load = 15
    return bytes([0xFF,0xFF, load & 0xFF, 0xFF,0xFF,0xFF,0xFF,0xFF])

def build_payload_vd():
    # PGN 65248, SPN 245 Total distance байты 0-3 LE, res=0.125
    km = 123456
    raw = int(km / 0.125) & 0xFFFFFFFF
    return bytes([raw & 0xFF, (raw>>8) & 0xFF, (raw>>16) & 0xFF, (raw>>24) & 0xFF, 0xFF,0xFF,0xFF,0xFF])

def build_payload_hours():
    # PGN 65253, SPN 247 Engine hours байты 0-3 LE, res=0.05
    hours = 1500.5
    raw = int(hours / 0.05) & 0xFFFFFFFF
    return bytes([raw & 0xFF, (raw>>8) & 0xFF, (raw>>16) & 0xFF, (raw>>24) & 0xFF, 0xFF,0xFF,0xFF,0xFF])

FRAMES = [
    (61444, 6, build_payload_eec1,  "EEC1  RPM=800"),
    (65265, 6, build_payload_ccvs,  "CCVS  Speed=0"),
    (65262, 6, build_payload_et1,   "ET1   Coolant=85"),
    (65263, 6, build_payload_eflp1, "EFLP1 Oil=300 Fuel=65"),
    (65271, 6, build_payload_ep1,   "EP1   V=24.5"),
    (65266, 6, build_payload_lfe,   "LFE   FuelRate=5.2"),
    (61443, 6, build_payload_eec2,  "EEC2  Load=15"),
    (65248, 6, build_payload_vd,    "VD    Dist=123456"),
    (65253, 6, build_payload_hours, "HOURS Hrs=1500.5"),
]

def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    sa = 0x00  # Engine source address

    assert dll.VCI_OpenDevice(VCI_USBCAN2, 0, 0) == STATUS_OK, "open failed"

    cfg = VCI_INIT_CONFIG(0,0xFFFFFFFF,0,0,BTR0,BTR1,0)  # Mode=0 NORMAL
    # Оба канала запускаем, они ACK друг друга
    for ch in (0, 1):
        assert dll.VCI_InitCAN(VCI_USBCAN2,0,ch,C.byref(cfg)) == STATUS_OK, f"init ch{ch}"
        assert dll.VCI_StartCAN(VCI_USBCAN2,0,ch) == STATUS_OK, f"start ch{ch}"

    print(f"[j1939] CH0+CH1 up @ 250 kbit/s, sending {len(FRAMES)} PGN for {duration}s")
    t0 = time.time()
    total = 0
    while time.time() - t0 < duration:
        for pgn, prio, payload_fn, label in FRAMES:
            can_id = build_j1939_id(prio, pgn, sa)
            data = payload_fn()
            obj = VCI_CAN_OBJ()
            obj.ID = can_id
            obj.SendType = 0
            obj.RemoteFlag = 0
            obj.ExternFlag = 1  # 29-bit
            obj.DataLen = 8
            for i,b in enumerate(data): obj.Data[i] = b
            r = dll.VCI_Transmit(VCI_USBCAN2, 0, 0, C.byref(obj), 1)
            total += 1
            print(f"  TX PGN {pgn:5d} ID=0x{can_id:08X}  {label:32s} {'OK' if r==STATUS_OK else 'FAIL'}")
            time.sleep(0.05)
        time.sleep(0.5)

    for ch in (0, 1):
        dll.VCI_ResetCAN(VCI_USBCAN2, 0, ch)
    dll.VCI_CloseDevice(VCI_USBCAN2, 0)
    print(f"\n[j1939] done. total TX={total}")

main()
