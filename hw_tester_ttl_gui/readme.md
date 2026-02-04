Как пользоваться (быстро)

Подключи USB-TTL к плате (TX↔RX, GND↔GND, питание платы отдельно).

Узнай COM-порт в Windows (Диспетчер устройств).

Запусти:

python hw_tester_ttl_gui.py


Нажми Run Tests → увидишь список тестов и детали.

Что этот скрипт реально проверяет

CPU (/proc/cpuinfo)

RAM (/proc/meminfo)

Температуру (через hwmon/thermal)

NAND/разделы (/proc/mtd)

USB (через lsusb, если есть)

Сеть (ip addr)

RTC (hwclock -r, если есть)

uname/uptime