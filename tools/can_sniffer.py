"""
Сниффер USBCAN-2A через ControlCAN.dll.
Инициализирует оба канала, опрашивает входящие кадры и ошибки на обоих.

Usage: python can_sniffer.py [baud_kbit] [duration_sec]  (defaults: 50 15)
"""
import sys, time
from ctypes import c_uint, c_ubyte, c_uint16, windll, byref, Structure, POINTER, cast

VCI_USBCAN2 = 4
STATUS_OK = 1
BAUD_BTR = {
    1000:(0x00,0x14), 800:(0x00,0x16), 500:(0x00,0x1C),
    250:(0x01,0x1C),  125:(0x03,0x1C), 100:(0x04,0x1C),
    50: (0x09,0x1C),  20:(0x18,0x1C),  10:(0x31,0x1C),
}

class VCI_INIT_CONFIG(Structure):
    _fields_ = [("AccCode",c_uint),("AccMask",c_uint),("Reserved",c_uint),
                ("Filter",c_ubyte),("Timing0",c_ubyte),("Timing1",c_ubyte),("Mode",c_ubyte)]

class VCI_CAN_OBJ(Structure):
    _fields_ = [("ID",c_uint),("TimeStamp",c_uint),("TimeFlag",c_ubyte),
                ("SendType",c_ubyte),("RemoteFlag",c_ubyte),("ExternFlag",c_ubyte),
                ("DataLen",c_ubyte),("Data",c_ubyte*8),("Reserved",c_ubyte*3)]

class VCI_CAN_OBJ_ARRAY(Structure):
    _fields_ = [('SIZE',c_uint16),('STRUCT_ARRAY',POINTER(VCI_CAN_OBJ))]
    def __init__(self, num):
        self.STRUCT_ARRAY = cast((VCI_CAN_OBJ*num)(), POINTER(VCI_CAN_OBJ))
        self.SIZE = num

class VCI_ERR_INFO(Structure):
    _fields_ = [("ErrCode",c_uint),("Passive_ErrData",c_ubyte*3),("ArLost_ErrData",c_ubyte)]

def err_text(code):
    bits = {0x0001:"CAN_OVERFLOW",0x0002:"CAN_ERRALARM",0x0004:"CAN_PASSIVE",
            0x0008:"CAN_LOSE",0x0010:"CAN_BUSERR",0x0020:"CAN_BUS_OFF",
            0x0040:"CAN_BUFFER_OVF",0x0100:"DEV_BUFFER_OVF",
            0x0200:"DEV_ARBITRATION_LOST",0x0400:"DEV_PASSIVE_ERROR",0x0800:"DEV_BUS_ERROR"}
    return ",".join(n for b,n in bits.items() if code & b) or f"unknown(0x{code:x})"

def main():
    baud = int(sys.argv[1]) if len(sys.argv)>1 else 50
    duration = int(sys.argv[2]) if len(sys.argv)>2 else 15
    if baud not in BAUD_BTR:
        print(f"unknown baud {baud}, choose from {list(BAUD_BTR)}"); sys.exit(1)
    t0,t1 = BAUD_BTR[baud]

    dll = windll.LoadLibrary('./ControlCAN.dll')
    print("[sniff] open USBCAN-2A...")
    if dll.VCI_OpenDevice(VCI_USBCAN2,0,0) != STATUS_OK:
        print("VCI_OpenDevice failed"); sys.exit(1)

    cfg = VCI_INIT_CONFIG(0x00000000, 0xFFFFFFFF, 0, 0, t0, t1, 0)  # mode=NORMAL
    for ch in (0,1):
        r1 = dll.VCI_InitCAN(VCI_USBCAN2,0,ch,byref(cfg))
        r2 = dll.VCI_StartCAN(VCI_USBCAN2,0,ch)
        print(f"[sniff] CH{ch}: InitCAN={r1} StartCAN={r2}")

    print(f"[sniff] @ {baud} kbit/s, NORMAL, accept-all. Listening CH0+CH1 for {duration}s\n")

    rx = VCI_CAN_OBJ_ARRAY(500)
    err = VCI_ERR_INFO()
    t_end = time.time()+duration
    total = 0; err_polls = 0
    last_err = {0:0,1:0}

    while time.time()<t_end:
        for ch in (0,1):
            n = dll.VCI_Receive(VCI_USBCAN2,0,ch,byref(rx.STRUCT_ARRAY[0]),500,10)
            if n>0:
                for i in range(n):
                    o = rx.STRUCT_ARRAY[i]
                    data = bytes(o.Data[:o.DataLen])
                    hexd = " ".join(f"{b:02X}" for b in data)
                    flags = []
                    if o.ExternFlag: flags.append("EXT")
                    if o.RemoteFlag: flags.append("RTR")
                    fs = "["+",".join(flags)+"]" if flags else ""
                    print(f"  CH{ch} ts={o.TimeStamp:>8} ID=0x{o.ID:08X} {fs:6} DLC={o.DataLen}  {hexd}")
                    total += 1
            if dll.VCI_ReadErrInfo(VCI_USBCAN2,0,ch,byref(err)) == STATUS_OK:
                c = err.ErrCode
                if c and c != last_err[ch]:
                    print(f"  CH{ch} [ERR] 0x{c:04X} {err_text(c)} passive={bytes(err.Passive_ErrData).hex()} arb=0x{err.ArLost_ErrData:02X}")
                    last_err[ch] = c
                    err_polls += 1

    print(f"\n[sniff] done. frames={total} err_events={err_polls}")
    dll.VCI_CloseDevice(VCI_USBCAN2,0)

if __name__ == "__main__":
    main()
