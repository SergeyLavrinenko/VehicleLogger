"""
Передатчик USBCAN-2A. Шлёт тестовый кадр 0x456 с шины и параллельно слушает.
Usage: python can_send.py [baud_kbit] [duration_sec]  (defaults: 50 15)
"""
import sys, time
from ctypes import c_uint, c_ubyte, c_uint16, windll, byref, Structure, POINTER, cast

VCI_USBCAN2 = 4
STATUS_OK = 1
BAUD_BTR = {
    1000:(0x00,0x14), 500:(0x00,0x1C),
    250:(0x01,0x1C),  125:(0x03,0x1C), 100:(0x04,0x1C),
    50:(0x09,0x1C),   20:(0x18,0x1C),  10:(0x31,0x1C),
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
    def __init__(self,n):
        self.STRUCT_ARRAY = cast((VCI_CAN_OBJ*n)(), POINTER(VCI_CAN_OBJ))
        self.SIZE = n
class VCI_ERR_INFO(Structure):
    _fields_ = [("ErrCode",c_uint),("Passive_ErrData",c_ubyte*3),("ArLost_ErrData",c_ubyte)]

def main():
    baud = int(sys.argv[1]) if len(sys.argv)>1 else 50
    duration = int(sys.argv[2]) if len(sys.argv)>2 else 15
    t0,t1 = BAUD_BTR[baud]

    dll = windll.LoadLibrary('./ControlCAN.dll')
    assert dll.VCI_OpenDevice(VCI_USBCAN2,0,0) == STATUS_OK, "open failed"

    cfg = VCI_INIT_CONFIG(0, 0xFFFFFFFF, 0, 0, t0, t1, 0)  # NORMAL mode
    assert dll.VCI_InitCAN(VCI_USBCAN2,0,0,byref(cfg)) == STATUS_OK
    assert dll.VCI_StartCAN(VCI_USBCAN2,0,0) == STATUS_OK
    print(f"[send] CH0 up @ {baud} kbit/s, sending 0x456 every 1s for {duration}s")

    # одна структура для TX
    data = (c_ubyte*8)(0xAA,0xBB,0xCC,0xDD,0x11,0x22,0x33,0x44)
    reserved = (c_ubyte*3)(0,0,0)
    # SendType=0 — normal; RemoteFlag=0; ExternFlag=0 (std id); DataLen=8
    tx = VCI_CAN_OBJ(0x456, 0, 0, 0, 0, 0, 8, data, reserved)

    rx = VCI_CAN_OBJ_ARRAY(100)
    err = VCI_ERR_INFO()

    t_end = time.time()+duration
    last_send = 0
    sent = 0; recv = 0
    while time.time()<t_end:
        now = time.time()
        if now - last_send >= 1.0:
            r = dll.VCI_Transmit(VCI_USBCAN2,0,0,byref(tx),1)
            status = "OK" if r == 1 else f"FAIL({r})"
            sent += 1 if r == 1 else 0
            print(f"  [TX] 0x456 {status}  (sent_total={sent})")
            last_send = now

        n = dll.VCI_Receive(VCI_USBCAN2,0,0,byref(rx.STRUCT_ARRAY[0]),100,20)
        if n>0:
            for i in range(n):
                o = rx.STRUCT_ARRAY[i]
                hd = " ".join(f"{b:02X}" for b in bytes(o.Data[:o.DataLen]))
                print(f"  [RX] ID=0x{o.ID:X} DLC={o.DataLen} {hd}")
                recv += 1
        if dll.VCI_ReadErrInfo(VCI_USBCAN2,0,0,byref(err)) == STATUS_OK and err.ErrCode:
            print(f"  [ERR] code=0x{err.ErrCode:04X}")

    print(f"\n[send] done. sent={sent} received={recv}")
    dll.VCI_CloseDevice(VCI_USBCAN2,0)

if __name__ == "__main__":
    main()
