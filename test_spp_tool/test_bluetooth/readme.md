```markdown
# Bluetooth test pack (ECB10-135A5M5M-I) — smoke + pairing + SPP check

Этот набор тестов предназначен для проекта с вкладками/Notebook и проверки Bluetooth на плате **ECB10-135A5M5M-I (STM32MP135)** в текущем Linux-образе.

Цели:
- быстро подтвердить, что **Bluetooth-стек жив** (hci0, firmware, драйверы);
- дать воспроизводимую **пошаговую проверку pairing** с телефоном;
- честно зафиксировать ограничение текущего образа: **SPP (RFCOMM) в ядре не поддержан** (ожидаемый FAIL).

---

## Структура

```

test_bluetooth/
README.md
bt_quick_info.sh       # smoke/info: hci0, dmesg bluetooth, firmware
bt_pairing_notes.md    # pairing подсказки + команды
bt_spp_check.sh        # SPP/RFCOMM check: ожидаемо FAIL на текущей сборке

````

---

## Требования на плате

Минимум:
- `bluetoothctl` (BlueZ)
- `hciconfig` (обычно пакет bluez-tools)
- `rfcomm` (userspace утилита; даже если ядро без RFCOMM — утилита может быть)

Проверка:
```bash
which bluetoothctl hciconfig rfcomm
````

---

## Установка на плату через Serial (ручной, самый надёжный способ)

Этот способ работает, даже если нет сети. Вы просто **копируете команды в терминал по UART/serial**
(либо в реальном терминале, либо через вашу вкладку Result в Notebook, если она умеет отправлять многострочные блоки).

### 1) Создать папку

```bash
mkdir -p /root/test_spp_tool/test_bluetooth
cd /root/test_spp_tool/test_bluetooth
```

### 2) Создать файлы скриптов (вставкой через heredoc)

#### bt_quick_info.sh

```bash
cat > bt_quick_info.sh <<'EOF'
#!/bin/sh
set -eu
TS(){ date +"%Y-%m-%d %H:%M:%S"; }
LOG(){ echo "[$(TS)] $*"; }
DIE(){ echo "[$(TS)] ERROR: $*" >&2; exit 1; }

LOG "== Bluetooth info =="
[ -d /sys/class/bluetooth/hci0 ] || DIE "hci0 not found in /sys/class/bluetooth"
LOG "hci0 present: YES"

if command -v hciconfig >/dev/null 2>&1; then
  LOG "hciconfig: $(command -v hciconfig)"
  LOG "hciconfig -a:"
  hciconfig -a hci0 || true
else
  LOG "hciconfig not found."
fi

if [ -f /lib/firmware/brcm/BCM43430A1.hcd ]; then
  LOG "Firmware: /lib/firmware/brcm/BCM43430A1.hcd (FOUND)"
else
  LOG "Firmware: /lib/firmware/brcm/BCM43430A1.hcd (NOT FOUND)"
fi

LOG "dmesg (bluetooth) tail:"
dmesg | grep -i bluetooth | tail -n 30 || true
LOG "OK"
EOF
```

#### bt_spp_check.sh

```bash
cat > bt_spp_check.sh <<'EOF'
#!/bin/sh
# SPP/RFCOMM availability check (expected FAIL on current image)
set -eu
TS(){ date +"%Y-%m-%d %H:%M:%S"; }
LOG(){ echo "[$(TS)] $*"; }
ERR(){ echo "[$(TS)] ERROR: $*" >&2; }
have(){ command -v "$1" >/dev/null 2>&1; }

LOG "== Bluetooth SPP (RFCOMM) kernel capability check =="

if ! have rfcomm; then
  ERR "rfcomm tool not found."
  exit 3
fi

LOG "rfcomm: $(command -v rfcomm)"

if have modprobe; then
  if modprobe rfcomm >/dev/null 2>&1; then
    LOG "modprobe rfcomm: OK"
  else
    LOG "modprobe rfcomm: failed (module may be absent / modules disabled)"
  fi
else
  LOG "modprobe not available; skip."
fi

if [ -r /proc/config.gz ] && have zcat; then
  cfg="$(zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_BT_RFCOMM(=| )|^CONFIG_BT_RFCOMM_TTY(=| )|^# CONFIG_BT_RFCOMM' || true)"
  [ -n "$cfg" ] && { LOG "Kernel config (RFCOMM):"; echo "$cfg" | sed 's/^/[CFG] /'; } || true
fi

tmp="$(mktemp -t rfcomm_err.XXXXXX)"
if rfcomm release 0 >/dev/null 2>"$tmp"; then
  LOG "RFCOMM control socket доступен (SPP вероятно поддерживается)."
  rm -f "$tmp"
  exit 0
fi

msg="$(cat "$tmp" 2>/dev/null || true)"
rm -f "$tmp"

if echo "$msg" | grep -qi "Protocol not supported"; then
  ERR "SPP/RFCOMM НЕ поддерживается текущим ядром (Protocol not supported)."
  ERR "Это ограничение сборки Linux, не проблема BT железа."
  ERR "Нужно пересобрать ядро с CONFIG_BT_RFCOMM и CONFIG_BT_RFCOMM_TTY."
  exit 2
fi

ERR "Unexpected rfcomm error:"
echo "$msg" | sed 's/^/  /' >&2
exit 4
EOF
```

#### bt_pairing_notes.md

```bash
cat > bt_pairing_notes.md <<'EOF'
# Pairing notes (Android)

Короткая памятка по pairing через bluetoothctl.

## Подготовка на плате
bluetoothctl
power on
system-alias EBYTE-13x
discoverable-timeout 0
pairable-timeout 0
discoverable on
pairable on
agent on
default-agent
show

## Важно
Когда появится:
  Confirm passkey XXXXX (yes/no):
нужно вводить строго:
  yes
(НЕ цифры)

## После успешного pairing
trust <MAC_телефона>
paired-devices
trusted-devices
EOF
```

### 3) Сделать скрипты исполняемыми

```bash
chmod +x bt_quick_info.sh bt_spp_check.sh
```

---

## Установка “автоматом” из вашей папки `test_spp_tool` (сценарий для Notebook)

Если ваш Notebook умеет отправлять команды по Serial, можно сделать кнопки/шаги:

1. **Install Bluetooth test pack**
   Отправляет команды:

   * `mkdir -p /root/test_spp_tool/test_bluetooth`
   * затем 3 heredoc блока (как выше)
   * затем `chmod +x ...`

2. **Run: BT Info**

   * `/root/test_spp_tool/test_bluetooth/bt_quick_info.sh`

3. **Run: SPP Check**

   * `/root/test_spp_tool/test_bluetooth/bt_spp_check.sh`

4. **Open notes**

   * выводит `cat bt_pairing_notes.md` в поле лога/Help.

> Примечание: если ваша вкладка не поддерживает многострочную вставку (heredoc),
> то “авто-установка” лучше делается через реальный терминал (minicom/screen/moba)
> или через будущую функцию “передать файл на плату”.

---

## Запуск тестов (CLI)

### 1) Smoke/Info

```bash
cd /root/test_spp_tool/test_bluetooth
./bt_quick_info.sh
```

Ожидаемо:

* `/sys/class/bluetooth/hci0` существует
* в `dmesg` есть строки про Broadcom BCM/AP6212 и загрузку firmware

### 2) Pairing (вручную по памятке)

Открыть:

```bash
cat /root/test_spp_tool/test_bluetooth/bt_pairing_notes.md
```

И выполнить шаги из файла.

### 3) Проверка SPP/RFCOMM (ожидаемый FAIL в текущей сборке)

```bash
cd /root/test_spp_tool/test_bluetooth
./bt_spp_check.sh
echo $?
```

Ожидаемо в текущем образе:

* вывод с `Protocol not supported`
* код возврата: `2`

Это **нормально** и означает:

* Bluetooth работает,
* но в ядре нет RFCOMM, поэтому SPP невозможен без пересборки ядра.

---

## Что именно проверяем и зачем

* `bt_quick_info.sh` — быстрый ответ на вопрос “Bluetooth вообще жив?”
  Проверяет:

  * наличие `hci0`
  * ключевые строки `dmesg` (инициализация, firmware)
  * наличие firmware-файла

* `bt_pairing_notes.md` — фиксируем правильный сценарий pairing
  (важно: отвечать `yes`, а не вводить цифры)

* `bt_spp_check.sh` — проверяем возможность SPP/RFCOMM
  Сейчас тест нужен, чтобы:

  * документировать ограничение образа
  * позже, после пересборки ядра, получить **PASS** без изменений в тесте

---

## Cleanup (вернуть состояние “как было”)

Если включали видимость:

```bash
bluetoothctl discoverable off
bluetoothctl pairable off
bluetoothctl power off
```

---

## Troubleshooting

### rfcomm: Protocol not supported

Это ожидаемо для текущего образа: ядро без RFCOMM.
Вернёмся к этому в разделе/видео “пересборка ядра”:
нужно включить `CONFIG_BT_RFCOMM` и `CONFIG_BT_RFCOMM_TTY`.

### Телефон не видит плату

Проверь:

```bash
bluetoothctl show
```

Должно быть:

* Powered: yes
* Discoverable: yes
* DiscoverableTimeout: 0x00000000
* Pairable: yes
* Alias: EBYTE-13x

```

---

## Статус

- Bluetooth HCI/firmware: ✅ OK
- Pairing: ✅ OK
- SPP/RFCOMM: ❌ не поддержан в текущем ядре (ожидаемо)
- OBEX/file transfer: ❌ отсутствует в rootfs (обсудим отдельно)
```

