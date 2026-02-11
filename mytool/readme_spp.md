````md
# SPP.md — Bluetooth SPP (Serial Port Profile) на Linux (ECB10-135A5M5M-I / STM32MP135)

Этот документ — теория + практическая “карта системы”: **как SPP должен быть реализован в Linux**, какие слои участвуют, **где что хранится**, что должно быть включено/установлено, и почему на текущем образе SPP не работает (RFCOMM “Protocol not supported”).

---

## 1) Что такое SPP и из чего он состоит

**SPP (Serial Port Profile)** — это “виртуальный COM-порт поверх Bluetooth Classic”, который позволяет передавать байты как по UART (терминал/протокол), но по радиоканалу.

Стек (снизу вверх):

1. **Bluetooth controller (чип)**  
   Управляет радио, принимает команды HCI, поднимает соединения.

2. **HCI transport** (как контроллер подключён к CPU)  
   Например:
   - UART (H4) — как у нас на плате
   - USB (BT-dongle) — другое

3. **Kernel Bluetooth core**  
   Базовая поддержка Bluetooth в ядре: устройства `hciX`, менеджмент, сокеты.

4. **L2CAP**  
   Базовый транспортный уровень Bluetooth Classic.

5. **RFCOMM**  ✅ ключевой слой для SPP  
   Эмулирует “serial line” поверх L2CAP.  
   Если **RFCOMM не включён в ядре**, SPP невозможен.

6. **SDP (Service Discovery Protocol)**  
   Чтобы телефон “увидел” на плате сервис SPP, плата должна публиковать **SDP-запись**.

7. **Приложение / TTY**  
   На Linux обычно появится:
   - `/dev/rfcomm0` (TTY-устройство)
   - дальше вы читаете/пишете в него как в обычный serial.

---

## 2) Почему SPP сейчас не работает на вашем образе

Ваш диагностический факт:
- `rfcomm listen /dev/rfcomm0 1` → `Protocol not supported`

Это означает:
- ядро собрано **без RFCOMM** (или без его части TTY)
- userspace-утилита `rfcomm` может быть установлена, но **ядро не умеет RFCOMM сокет**

Минимум, что должно быть включено в kernel:

- `CONFIG_BT=y`
- `CONFIG_BT_BREDR=y` (Classic)
- `CONFIG_BT_RFCOMM=y` или `m`
- `CONFIG_BT_RFCOMM_TTY=y` или `m`

Дополнительно часто полезно:
- `CONFIG_BT_HCIUART=y/m` (для UART HCI)
- `CONFIG_BT_HCIUART_H4=y/m`
- `CONFIG_BT_BNEP=y/m` (если нужен PAN)
- `CONFIG_BT_SCO=y/m` (аудио/телефония)
- `CONFIG_BT_DEBUGFS` (для отладки)

---

## 3) Какие элементы должны быть в системе и где они находятся

### 3.1 Kernel / модули

Где лежат модули (если ядро модульное):
- `/lib/modules/$(uname -r)/kernel/net/bluetooth/`
  - `bluetooth.ko`
  - `rfcomm.ko`
  - `bnep.ko` (PAN)
  - и т.д.

Проверка:
```sh
zcat /proc/config.gz | grep RFCOMM
lsmod | grep rfcomm
modprobe rfcomm
````

### 3.2 HCI устройство (контроллер)

Появление:

* `/sys/class/bluetooth/hci0`

Состояние:

```sh
hciconfig -a hci0
bluetoothctl show
```

### 3.3 Firmware для Broadcom (combo AP6212)

Обычно firmware/patch для BT лежит в:

* `/lib/firmware/brcm/`

  * пример: `BCM43430A1.hcd`

Загрузка видна в:

```sh
dmesg | grep -i bluetooth
```

### 3.4 BlueZ userspace (демоны и конфиги)

Ключевой демон:

* `bluetoothd` (BlueZ)

Типичные конфиги:

* `/etc/bluetooth/main.conf`
* `/etc/bluetooth/input.conf`
* `/etc/bluetooth/network.conf` (если PAN)

Состояние pairing/trust и база устройств:

* `/var/lib/bluetooth/<ADAPTER_MAC>/`

  * `<DEVICE_MAC>/info` (Paired/Trusted/Key)
  * `cache/` и др.

Это важно: даже если телефон “Trusted”, без профиля SPP телефон не обязан “держать соединение”.

### 3.5 SPP сервис и SDP запись

Чтобы телефон “подключился” к SPP, на стороне платы должен быть **SPP server** + **SDP record**.

Инструменты (в зависимости от дистрибутива):

* `sdptool` (иногда в пакете `bluez` или `bluez-tools`)
* `rfcomm`

Пример публикации SPP через SDP (варианты зависят от образа):

* `sdptool add SP` (Serial Port)
  или с каналом:
* `sdptool add --channel=1 SP`

Важно: **без SDP записи** телефон может не показать “Serial” и не сможет подключиться как к COM-порту.

---

## 4) Как должен работать SPP (ожидаемый сценарий)

### 4.1 Подготовка (на плате)

1. Запустить Bluetooth стек:

```sh
bluetoothctl
power on
agent on
default-agent
discoverable-timeout 0
pairable-timeout 0
discoverable on
pairable on
```

2. Спарить телефон (на запрос passkey вводить **yes**).

3. Опубликовать SPP сервис (если нужно):

```sh
sdptool add --channel=1 SP
```

4. Поднять RFCOMM TTY (сервер на плате):

```sh
rfcomm listen /dev/rfcomm0 1
```

После этого:

* телефон должен увидеть сервис (зависит от приложения)
* при подключении появится связь, и `/dev/rfcomm0` станет “живым”

### 4.2 Передача данных

На плате:

```sh
echo "Hello from board" > /dev/rfcomm0
cat /dev/rfcomm0
```

На телефоне:

* приложение “Serial Bluetooth Terminal” / “Bluetooth Terminal” подключается к SPP и показывает обмен.

---

## 5) Что должно быть в папках проекта (зачем)

Рекомендуемая структура тестов:

```
test_bluetooth/
  README.md                 # общий итог: что работает/не работает на текущем образе
  bt_quick_info.sh          # smoke/info (hci0/firmware/dmesg)
  bt_pairing_notes.md       # pairing чеклист
  bt_spp_check.sh           # RFCOMM capability check (expected FAIL сейчас)
  SPP.md                    # этот документ (теория и “как должно быть”)
```

Зачем:

* `bt_quick_info.sh` — быстро доказать “железо + стек поднялись”
* `bt_pairing_notes.md` — воспроизводимый pairing без ошибок
* `bt_spp_check.sh` — диагностировать **ядро**, не споря “почему не подключается”
* `SPP.md` — объяснить, что именно не хватает и что будет после пересборки ядра

---

## 6) Может ли SPP работать одновременно с Wi-Fi (AP6212)

**Да, в большинстве случаев может.** AP6212 — это Wi-Fi + BT combo, обычно:

* Wi-Fi идёт по **SDIO**
* Bluetooth идёт по **UART (HCI UART)**

Они делят:

* питание
* антенну/радиочасть (через coex)
* иногда общие линии управления

Чтобы Wi-Fi и BT работали стабильно вместе, важны:

1. **Правильные драйверы**

* Wi-Fi: обычно `brcmfmac` (для Broadcom SDIO)
* BT: `hci_uart` + broadcom протокол/патч (`btbcm` / serdev)

2. **Coexistence (совместная работа радио)**

* параметры coex часто зашиты в firmware/NVRAM (особенно для Wi-Fi)
* при плохой настройке возможны:

  * просадки скорости Wi-Fi при активном BT
  * лаги BT при высокой нагрузке Wi-Fi

3. **Питание и RF окружение**

* при слабом питании/плохой антенне одновременная работа заметно хуже

Итог: **SPP и Wi-Fi совместимы**, но качество зависит от coex/firmware/антенны и общей конфигурации.

---

## 7) Что будет после пересборки ядра (Roadmap)

Когда вы дойдёте до стадии kernel rebuild, цель такая:

1. Включить RFCOMM в kernel (`CONFIG_BT_RFCOMM`, `CONFIG_BT_RFCOMM_TTY`)
2. Убедиться, что `rfcomm` перестал выдавать `Protocol not supported`
3. Поднять SPP server:

   * SDP record + rfcomm listen
4. Показать стабильный тест:

   * телефон подключился к SPP
   * обмен данными через `/dev/rfcomm0`
   * (дополнительно) параллельно включить Wi-Fi и показать, что всё живёт

---

## 8) Короткий “симптом → причина” (для README/видео)

* Телефон **Paired/Trusted**, но “не подключается” или подключается и сразу отключается
  → на плате **нет сервиса**, который телефон хочет открыть (SPP/OBEX и т.д.)

* `rfcomm` пишет `Protocol not supported`
  → в ядре **нет RFCOMM**, SPP невозможен до пересборки ядра

---

## Статус для текущего этапа проекта

* ✅ Bluetooth hardware + HCI работают
* ✅ Pairing работает
* ❌ SPP (RFCOMM) не работает из-за kernel config
* ➡ вернёмся при разборе пересборки ядра

```


## Hardware notes: UART HCI signals (AP6212 / Broadcom)

On this board the Bluetooth part of the combo module is connected via classic UART HCI:
- UART_TX/RX/CTS/RTS — HCI transport + hardware flow control
- BT_nRST — Bluetooth reset line
- BT_WAKE / BT_HOST_WAKE — sleep/wakeup handshake between host and controller

In our current stage we do not toggle these pins manually — Linux drivers and board configuration
(device tree / platform init) handle them. We verify functionality at OS level (hci0, firmware, BlueZ).

Note: Missing RFCOMM/SPP support (rfcomm: "Protocol not supported") is a kernel configuration issue
(CONFIG_BT_RFCOMM / CONFIG_BT_RFCOMM_TTY), not a WAKE/RESET wiring issue.
