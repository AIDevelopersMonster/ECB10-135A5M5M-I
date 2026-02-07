# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

class TestHdmiTab(ttk.Frame):
    """
    HDMI test tab:
      - show DRM/FB info
      - paint fb0 (black/white/noise)
      - paint RGB565 solid colors
      - draw color bars
      - show EDID head
      - notes: splash preview & install commands (copy/paste)
    """

    def __init__(self, parent, executor, log_fn):
        super().__init__(parent)
        self.exec = executor
        self.log = log_fn

        self._build_ui()

    # ----------------------------
    # Executor wrapper (compat)
    # ----------------------------
    def _run(self, cmd: str):
        """
        Try to run a shell command through ShellExecutor with best-effort compatibility.
        Expected to return (ok: bool, out: str).
        """
        # Common method names we might have in your project:
        for name in ("run", "exec", "execute", "run_cmd", "exec_cmd"):
            fn = getattr(self.exec, name, None)
            if callable(fn):
                try:
                    res = fn(cmd)
                    # Normalize results:
                    if isinstance(res, tuple) and len(res) >= 2:
                        ok = bool(res[0])
                        out = str(res[1])
                        return ok, out
                    # If it returns only string:
                    return True, str(res)
                except Exception as e:
                    return False, f"{type(e).__name__}: {e}"
        return False, "ShellExecutor has no known run/exec method"

    def _append(self, text: str):
        self.out_text.insert("end", text)
        if not text.endswith("\n"):
            self.out_text.insert("end", "\n")
        self.out_text.see("end")

    def _exec_and_show(self, title: str, cmd: str):
        self.log(f"HDMI: {title}")
        self._append(f"\n$ {cmd}\n")
        ok, out = self._run(cmd)
        self._append(out.strip() if out else "")
        self._append("OK\n" if ok else "FAIL\n")
        return ok

    # ----------------------------
    # UI
    # ----------------------------
    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side="top", fill="x")

        # Left buttons (tests)
        btns = ttk.Labelframe(top, text="HDMI / DRM quick actions", padding=10)
        btns.pack(side="left", fill="y")

        ttk.Button(btns, text="Status (DRM+FB)", command=self.action_status).pack(fill="x", pady=3)
        ttk.Button(btns, text="EDID head", command=self.action_edid).pack(fill="x", pady=3)
        ttk.Separator(btns).pack(fill="x", pady=8)

        ttk.Button(btns, text="Black", command=lambda: self.action_fill_basic("black")).pack(fill="x", pady=3)
        ttk.Button(btns, text="White", command=lambda: self.action_fill_basic("white")).pack(fill="x", pady=3)
        ttk.Button(btns, text="Noise", command=lambda: self.action_fill_basic("noise")).pack(fill="x", pady=3)
        ttk.Separator(btns).pack(fill="x", pady=8)

        ttk.Button(btns, text="Red (RGB565)", command=lambda: self.action_fill_rgb565("red")).pack(fill="x", pady=3)
        ttk.Button(btns, text="Green (RGB565)", command=lambda: self.action_fill_rgb565("green")).pack(fill="x", pady=3)
        ttk.Button(btns, text="Blue (RGB565)", command=lambda: self.action_fill_rgb565("blue")).pack(fill="x", pady=3)
        ttk.Separator(btns).pack(fill="x", pady=8)

        ttk.Button(btns, text="Color bars", command=self.action_color_bars).pack(fill="x", pady=3)
        ttk.Button(btns, text="Gradient", command=self.action_gradient).pack(fill="x", pady=3)

        # Right notes / recipes (copy-paste)
        notes = ttk.Labelframe(top, text="How to save & show splash (copy/paste)", padding=10)
        notes.pack(side="left", fill="both", expand=True, padx=(10, 0))

        self.notes_text = tk.Text(notes, height=16, wrap="word")
        self.notes_text.pack(fill="both", expand=True)

        self.notes_text.insert(
            "end",
            """1) Find USB drive (it mounts as /media/sda1 or /media/usb0):
   ls /media/sda1
   ls /media/usb0

2) Preview BMP on HDMI via fb0 (requires ffmpeg):
   ffmpeg -y -i /media/sda1/splash_landscape.bmp -f rawvideo -pix_fmt rgb565le -s 1024x600 /tmp/kontakts.raw
   cat /tmp/kontakts.raw > /dev/fb0

3) Install splash BMP into bootfs (backup first):
   cd /media/mmcblk0p8
   cp splash_landscape.bmp splash_landscape.bmp.bak
   cp /media/sda1/splash_landscape.bmp /media/mmcblk0p8/splash_landscape.bmp
   sync

4) Reboot:
   reboot

Tip: If old logo still shows at boot, it may be a kernel logo (not a BMP file).
"""
        )
        self.notes_text.configure(state="disabled")

        # Output console
        out = ttk.Labelframe(self, text="HDMI test output", padding=10)
        out.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

        self.out_text = tk.Text(out, height=18, wrap="word")
        self.out_text.pack(fill="both", expand=True)

    # ----------------------------
    # Actions
    # ----------------------------
    def action_status(self):
        cmd = r"""
echo "=== DRM HDMI status ==="
[ -f /sys/class/drm/card0-HDMI-A-1/status ] && cat /sys/class/drm/card0-HDMI-A-1/status || echo "no /sys/class/drm/card0-HDMI-A-1/status"
echo
echo "=== Modes (EDID) ==="
[ -f /sys/class/drm/card0-HDMI-A-1/modes ] && cat /sys/class/drm/card0-HDMI-A-1/modes || echo "no modes"
echo
echo "=== fb0 ==="
cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || true
cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null || true
cat /sys/class/graphics/fb0/stride 2>/dev/null || true
echo
echo "=== dmesg drm (tail) ==="
dmesg | grep -i drm | tail -n 30
""".strip()
        self._exec_and_show("Status", cmd)

    def action_edid(self):
        cmd = r"""
echo "=== EDID head (hex) ==="
if [ -f /sys/class/drm/card0-HDMI-A-1/edid ]; then
  cat /sys/class/drm/card0-HDMI-A-1/edid | hexdump -C | head -n 20
else
  echo "no EDID file"
fi
""".strip()
        self._exec_and_show("EDID", cmd)

    def action_fill_basic(self, mode: str):
        # Uses fb0 geometry dynamically (stride * height)
        if mode == "black":
            cmd = r"""
STRIDE=$(cat /sys/class/graphics/fb0/stride)
H=$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size)
dd if=/dev/zero of=/dev/fb0 bs=$STRIDE count=$H
""".strip()
            self._exec_and_show("Fill black", cmd)
        elif mode == "white":
            cmd = r"""
STRIDE=$(cat /sys/class/graphics/fb0/stride)
H=$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size)
tr '\000' '\377' < /dev/zero | dd of=/dev/fb0 bs=$STRIDE count=$H
""".strip()
            self._exec_and_show("Fill white", cmd)
        elif mode == "noise":
            cmd = r"""
STRIDE=$(cat /sys/class/graphics/fb0/stride)
H=$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size)
head -c $((STRIDE*H)) /dev/urandom > /dev/fb0
""".strip()
            self._exec_and_show("Fill noise", cmd)

    def action_fill_rgb565(self, color: str):
        # Solid fills via python3 -> raw writes to /dev/fb0.
        # RGB565 constants:
        # red=0xF800, green=0x07E0, blue=0x001F
        color_map = {"red": "0xF800", "green": "0x07E0", "blue": "0x001F"}
        c = color_map.get(color, "0x0000")

        cmd = rf"""
python3 - << 'PY'
import struct
stride = int(open("/sys/class/graphics/fb0/stride").read().strip())
w,h = open("/sys/class/graphics/fb0/virtual_size").read().strip().split(",")
h = int(h)
color = int("{c}", 16)
# one row = stride bytes = stride//2 pixels (RGB565)
row = struct.pack("<" + "H"*(stride//2), *([color]*(stride//2)))
with open("/dev/fb0", "wb") as f:
    for _ in range(h):
        f.write(row)
print("filled RGB565 color:", hex(color), "rows:", h, "stride:", stride)
PY
""".strip()
        self._exec_and_show(f"Fill {color} (RGB565)", cmd)

    def action_color_bars(self):
        # 8 vertical bars (RGB565)
        cmd = r"""
python3 - << 'PY'
import struct
stride = int(open("/sys/class/graphics/fb0/stride").read().strip())
w,h = open("/sys/class/graphics/fb0/virtual_size").read().strip().split(",")
w = int(w); h = int(h)
# RGB565 bars: white, yellow, cyan, green, magenta, red, blue, black
colors = [0xFFFF, 0xFFE0, 0x07FF, 0x07E0, 0xF81F, 0xF800, 0x001F, 0x0000]
bar_w = max(1, w // len(colors))
# build one scanline in pixels (w), then pack into stride
pixels = []
for i in range(w):
    idx = min(len(colors)-1, i // bar_w)
    pixels.append(colors[idx])
# pad to stride (in pixels)
line_px = stride // 2
if len(pixels) < line_px:
    pixels += [pixels[-1]] * (line_px - len(pixels))
else:
    pixels = pixels[:line_px]
row = struct.pack("<" + "H"*line_px, *pixels)
with open("/dev/fb0","wb") as f:
    for _ in range(h):
        f.write(row)
print("color bars:", w, "x", h, "stride:", stride)
PY
""".strip()
        self._exec_and_show("Color bars", cmd)

    def action_gradient(self):
        # Horizontal gradient (RGB565 gray)
        cmd = r"""
python3 - << 'PY'
import struct
stride = int(open("/sys/class/graphics/fb0/stride").read().strip())
w,h = open("/sys/class/graphics/fb0/virtual_size").read().strip().split(",")
w = int(w); h = int(h)
line_px = stride // 2

def rgb565(r,g,b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

pixels = []
for i in range(w):
    v = int(i * 255 / max(1, w-1))
    pixels.append(rgb565(v, v, v))
# pad/crop to stride
if len(pixels) < line_px:
    pixels += [pixels[-1]] * (line_px - len(pixels))
else:
    pixels = pixels[:line_px]

row = struct.pack("<" + "H"*line_px, *pixels)
with open("/dev/fb0","wb") as f:
    for _ in range(h):
        f.write(row)
print("gradient:", w, "x", h, "stride:", stride)
PY
""".strip()
        self._exec_and_show("Gradient", cmd)
