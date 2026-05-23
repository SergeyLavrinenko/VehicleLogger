# Mosquitto broker для VehicleLogger

В этой папке — конфиги для подключения брокера к нашему стеку.

## Развёртывание на сервере (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y mosquitto mosquitto-clients
sudo cp mosquitto.conf /etc/mosquitto/conf.d/vehiclelogger.conf
sudo cp acl              /etc/mosquitto/acl
sudo touch /etc/mosquitto/passwd
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd
sudo chmod 640                  /etc/mosquitto/passwd

# Группа для backend (чтобы он мог писать в passwd и перезагружать сервис)
sudo usermod -aG mosquitto $(whoami)         # для админа
# Для systemd-юнита backend — добавить SupplementaryGroups=mosquitto и
# разрешить через sudoers команду "systemctl reload mosquitto".

sudo systemctl restart mosquitto
sudo systemctl enable mosquitto
```

## Первый пользователь — backend

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd vl-backend
# (введите пароль; этот же пароль кладёте в appsettings.json: Mqtt:Password)
sudo systemctl reload mosquitto
```

Учётки устройств добавляются автоматически: при enroll backend пишет
`<serial>:<bcrypt(api_key)>` в passwd и шлёт reload.

## DNS

Поддомен `mqtt.nonconf.ru` должен резолвиться в IP сервера. Сертификат
wildcard `*.nonconf.ru` (Let's Encrypt) уже покрывает.

## Проверка вживую

```bash
mosquitto_sub -h mqtt.nonconf.ru -p 8883 --cafile /etc/ssl/certs/ca-certificates.crt \
              -u vl-backend -P "<password>" -t 'vl/#' -v
# Или через python-скрипт:
python tools/mqtt_listen.py
```

## Безопасность

- `allow_anonymous false` — без логина не пустят.
- ACL: устройство пишет только в свои топики.
- TLS на 8883 — обязательно. Plain 1883 не открываем.
- При компрометации api_key админ компании в ЛК нажимает rotate-key —
  backend заменяет пароль устройства в passwd и устройство получает
  отказ при следующем подключении со старым ключом, после чего
  перезаявляется через enroll.