````md
# SD Card Quick Test (SAFE) — ECB10-135A5M5M-I

Этот тест предназначен для **быстрой и безопасной** проверки SD-карты (MicroSD/TF) на плате.
Он **не форматирует**, **не меняет разметку** и **не пишет в /dev/mmcblkX напрямую** — только создаёт маленький временный файл в файловой системе.

Тест рассчитан на минимальный Linux / BusyBox (где может не быть `findmnt`, `lsblk`).

---

## Что проверяет тест в GUI

### 0) Проверка подключения (обязательно)
Перед выполнением любых команд тест проверяет, что устройство **подключено**:
- если `Not connected` → тест **останавливается** и показывает `FAIL`.

Это сделано специально, чтобы тест **не выдавал ложный PASS**.

---

### 1) Видит ли ядро SD-устройство
Команда:
```sh
ls /sys/block | grep -E '^mmcblk[0-9]+$'
````

Ожидаемый результат:

* в выводе есть `mmcblk0` (или другое `mmcblkX`).

Если пусто:

* SD не определилась (контакты/питание/DT/драйвер/режим).

---

### 2) Откуда смонтирован rootfs

Команда (BusyBox-совместимо):

```sh
mount | grep ' on / '
```

Ожидаемый результат для загрузки с SD:

* что-то вроде:

  ```text
  /dev/mmcblk0p9 on / type ext4 (rw,relatime)
  ```

Это подтверждает:

* система реально работает с SD-раздела,
* rootfs доступен на запись (rw).

---

### 3) Свободное место на корневом разделе

Команда:

```sh
df -h / | tail -1
```

Ожидаемый результат:

* показывает доступное место (`Avail`), например `209M`.

---

### 4) Тест записи (1 MB) — безопасно

Создаётся временный файл:

* путь: `/tmp/sd_test.bin`
* размер: **1 MB**
* запись идёт в файловую систему, НЕ в устройство блочно.

Команда:

```sh
dd if=/dev/zero of=/tmp/sd_test.bin bs=512 count=2048
```

Если запись прошла — будет `Write test: OK (1MB)`.

---

### 5) Тест чтения (1 MB)

Команда:

```sh
dd if=/tmp/sd_test.bin of=/dev/null bs=512 count=2048
```

Если чтение прошло — будет `Read test: OK (1MB)`.

---

### 6) Очистка

Команды:

```sh
rm -f /tmp/sd_test.bin
sync
```

---

## Почему этот тест “SAFE”

Тест НЕ делает:

* `mkfs.*`
* `fdisk`
* `dd if=/dev/zero of=/dev/mmcblk0 ...`

Тест делает:

* только маленький файл (1MB),
* только в ФС,
* удаляет его после проверки.

---

## Типичный вывод (пример)

Подключено:

```text
== SD card quick test (SAFE) ==
Kernel block device(s): mmcblk0
Root filesystem: /dev/mmcblk0p9 on / type ext4 (rw,relatime)
Free space: 209M
Write test: OK (1MB)
Read test: OK (1MB)
Cleanup: OK
SD test PASSED
```

Отключено:

```text
== SD card quick test (SAFE) ==
Not connected
FAIL
```

---

## Linux команды для работы с SD (шпаргалка)

### Понять, откуда загружен rootfs

```sh
mount | grep ' on / '
df -h /
```

### Проверить, видит ли ядро SD и разделы

```sh
ls /sys/block | grep mmc
cat /proc/partitions | grep mmc
dmesg | grep -i mmc
```

### Посмотреть, что смонтировано с SD

```sh
mount | grep mmc
df -h | grep mmc
```

### Смонтировать раздел SD вручную (если нужно)

(пример для раздела p9)

```sh
mkdir -p /mnt/sd
mount /dev/mmcblk0p9 /mnt/sd
df -h /mnt/sd
```

Отмонтировать:

```sh
umount /mnt/sd
sync
```

### Безопасный тест записи/чтения (1 MB)

Вариант для rootfs:

```sh
TEST=/tmp/sd_test.bin
dd if=/dev/zero of=$TEST bs=512 count=2048
sync
dd if=$TEST of=/dev/null bs=512 count=2048
rm -f $TEST
sync
```

Вариант для примонтированной SD:

```sh
TEST=/mnt/sd/sd_test.bin
dd if=/dev/zero of=$TEST bs=512 count=2048
sync
dd if=$TEST of=/dev/null bs=512 count=2048
rm -f $TEST
sync
```

### (Опционально) Быстрый тест скорости (аккуратно, 5–10 MB)

```sh
TEST=/tmp/sd_speed.bin
time dd if=/dev/zero of=$TEST bs=1M count=5
sync
time dd if=$TEST of=/dev/null bs=1M count=5
rm -f $TEST
sync
```

---

## Примечания для BusyBox

В минимальных образах могут отсутствовать:

* `findmnt`
* `lsblk`

Это нормально — для диагностики используем:

* `mount`
* `df`
* `/proc/partitions`
* `dmesg`

```

