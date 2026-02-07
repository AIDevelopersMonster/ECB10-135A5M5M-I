

---


# HDMI Test (Linux) — STM32MP135 / EBYTE

Данный документ описывает проверку работы **HDMI внутри Linux**  
на платах EBYTE со **STM32MP135**, без изменения U-Boot и ядра.

Тесты выполняются через **DRM + framebuffer (`/dev/fb0`)**  
и являются **безопасными и обратимыми**.

---

## 1. Аппаратная схема

- **CPU:** STM32MP135  
- **HDMI:** отсутствует нативно  
- **Вывод видео:** LTDC (RGB)  
- **Преобразователь:** RGB → HDMI (SII9022A)  
- **Linux:** DRM (`stm32-display`) + framebuffer

⚠️ HDMI и LCD используют одни и те же RGB-линии  
и **не могут работать одновременно**.

---

## 2. Проверка подключения HDMI (DRM)

### Статус HDMI-коннектора
```sh
cat /sys/class/drm/card0-HDMI-A-1/status
````

Ожидаемо:

```
connected
```

### Поддерживаемые режимы (EDID)

```sh
cat /sys/class/drm/card0-HDMI-A-1/modes
```

Пример:

```
1024x600
1024x768
800x600
```

---

## 3. Параметры framebuffer

```sh
cat /sys/class/graphics/fb0/virtual_size
cat /sys/class/graphics/fb0/bits_per_pixel
cat /sys/class/graphics/fb0/stride
```

Типичный вывод:

```
1024,600
16
2048
```

Расшифровка:

* Разрешение: **1024×600**
* Формат: **RGB565 (16 bpp)**
* Stride: **2048 байт на строку**

Размер кадра:

```
2048 × 600 = 1 228 800 байт
```

---

## 4. Базовые тесты framebuffer (безопасно)

Все команды ниже **только пишут в `/dev/fb0`**.

### 4.1 Чёрный экран

```sh
STRIDE=$(cat /sys/class/graphics/fb0/stride)
H=$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size)
dd if=/dev/zero of=/dev/fb0 bs=$STRIDE count=$H
```

### 4.2 Белый экран

```sh
STRIDE=$(cat /sys/class/graphics/fb0/stride)
H=$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size)
tr '\000' '\377' < /dev/zero | dd of=/dev/fb0 bs=$STRIDE count=$H
```

### 4.3 Шум (рябь)

```sh
STRIDE=$(cat /sys/class/graphics/fb0/stride)
H=$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size)
head -c $((STRIDE*H)) /dev/urandom > /dev/fb0
```

Назначение:

* проверка записи в framebuffer
* стабильность вывода
* отсутствие артефактов

---

## 5. Тест цветов (RGB565)

Контроль порядка каналов и глубины цвета.

RGB565:

* Красный: `0xF800`
* Зелёный: `0x07E0`
* Синий: `0x001F`

Пример (красный):

```sh
python3 - << 'PY'
import struct
stride = int(open("/sys/class/graphics/fb0/stride").read())
h = int(open("/sys/class/graphics/fb0/virtual_size").read().split(",")[1])
color = 0xF800
row = struct.pack("<" + "H"*(stride//2), *([color]*(stride//2)))
with open("/dev/fb0","wb") as f:
    for _ in range(h):
        f.write(row)
PY
```

---

## 6. Цветовые полосы и градиент

Используются для:

* проверки линейности
* оценки синхронизации
* визуальной диагностики HDMI

Реализованы в **HDMI-вкладке тестовой программы**.

---

## 7. Просмотр BMP на HDMI (без перезагрузки)

Позволяет проверить изображение **перед установкой как splash**.

### Требования

* `ffmpeg`
* BMP с разрешением **1024×600**

### Конвертация BMP → raw RGB565

```sh
ffmpeg -y -i /media/sda1/splash_landscape.bmp \
  -f rawvideo -pix_fmt rgb565le \
  -s 1024x600 /tmp/preview.raw
```

### Вывод на HDMI

```sh
cat /tmp/preview.raw > /dev/fb0
```

Если изображение корректно отображается — формат подходит.

---

## 8. Установка splash-картинки в bootfs

⚠️ Не влияет на **kernel built-in logo**.

### Резервная копия

```sh
cd /media/mmcblk0p8
cp splash_landscape.bmp splash_landscape.bmp.bak
```

### Копирование новой картинки

```sh
cp /media/sda1/splash_landscape.bmp /media/mmcblk0p8/splash_landscape.bmp
sync
```

### Перезагрузка

```sh
reboot
```

---

## 9. Важно: ранний логотип Ebyte

Если при старте всё равно отображается логотип **Ebyte**:

* он **вшит в ядро Linux**
* не загружается из BMP-файлов
* управляется через `CONFIG_LOGO`

### Отключение (временно)

Добавить в `extlinux.conf`:

```
logo.nologo
```

Замена логотипа возможна **только пересборкой ядра**.

---

## 10. HDMI Test GUI

В проекте реализована вкладка **HDMI Test**, включающая:

* статус DRM
* чтение EDID
* кнопки Black / White / Noise
* RGB565 заливки
* цветовые полосы и градиенты
* инструкции по работе с splash

Позволяет тестировать HDMI **без консоли**.

---

## 11. Итог

Данный набор тестов подтверждает:

* работу HDMI-линии
* корректность EDID
* функционирование DRM и framebuffer
* правильность RGB565
* возможность безопасного вывода изображений

Подходит для **разработки, валидации и демонстрации**.

```

---


