"""Подписка на все MQTT-топики брокера для отладки.

  python tools/mqtt_listen.py --host mqtt.nonconf.ru --user vl-backend
  (пароль — из переменной окружения VL_MQTT_PASSWORD, либо --password)

Зависимость: paho-mqtt (pip install paho-mqtt).
"""
import argparse
import json
import os
import sys
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("paho-mqtt не установлен. pip install paho-mqtt")
    sys.exit(2)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[CONN] подключены, подписываемся на {userdata['topic']}")
        client.subscribe(userdata["topic"], qos=1)
    else:
        print(f"[CONN] не удалось подключиться, rc={rc}")

def on_message(client, userdata, msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    payload = msg.payload.decode("utf-8", errors="replace")
    try:
        obj = json.loads(payload)
        payload = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        pass
    print(f"[{ts}] {msg.topic}\n{payload}\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="mqtt.nonconf.ru")
    ap.add_argument("--port", type=int, default=8883)
    ap.add_argument("--user", default="vl-backend")
    ap.add_argument("--password", default=os.environ.get("VL_MQTT_PASSWORD"))
    ap.add_argument("--topic", default="vl/#")
    ap.add_argument("--no-tls", action="store_true", help="отключить TLS (для отладки plain-брокера)")
    args = ap.parse_args()

    if not args.password:
        print("Укажите --password или VL_MQTT_PASSWORD")
        sys.exit(2)

    client = mqtt.Client(
        client_id=f"vl-listen-{os.getpid()}",
        userdata={"topic": args.topic},
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(args.user, args.password)
    if not args.no_tls:
        client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()