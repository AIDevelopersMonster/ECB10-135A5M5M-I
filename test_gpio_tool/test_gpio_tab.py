# test_gpio_tab.py
# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox


SYSFS = "/sys/class/gpio"

DEFAULT_PINS = ["PA1", "PA8", "PA11", "PE6"]


class LedLamp(ttk.Frame):
    def __init__(self, parent, size=16, text=""):
        super().__init__(parent)
        self._c = tk.Canvas(self, width=size, height=size, highlightthickness=0)
        self._c.grid(row=0, column=0, padx=(0, 6))
        self._t = ttk.Label(self, text=text)
        self._t.grid(row=0, column=1, sticky="w")
        pad = 2
        self._oval = self._c.create_oval(pad, pad, size - pad, size - pad, outline="#444", fill="#777")

    def set(self, on: bool):
        self._c.itemconfig(self._oval, fill=("#1cff4a" if on else "#777"))


class TestGPIOTab(ttk.Frame):
    """
    Requires executor with:
      - is_connected() -> bool
      - run(cmd: str, timeout_s: float=...) -> (ok: bool, out: str)

    Works with named sysfs nodes:
      /sys/class/gpio/PA8/direction
      /sys/class/gpio/PA8/value
    """

    def __init__(self, parent, executor, log_fn=None, pins=None):
        super().__init__(parent)
        self.exec = executor
        self.log = log_fn or (lambda s: None)

        self.pins = pins[:] if pins else DEFAULT_PINS[:]

        # UI state
        self.selected_pin = tk.StringVar(value=self.pins[0] if self.pins else "")
        self.poll_ms = tk.IntVar(value=200)
        self.blink_count = tk.IntVar(value=10)
        self.blink_period_ms = tk.IntVar(value=250)
        self.stop_flag = threading.Event()

        # internal: prevent parallel COM commands
        self._busy_lock = threading.Lock()

        # output controls (enabled only when direction == out)
        self.btn_write0 = None
        self.btn_write1 = None
        self.btn_blink = None

        self._build_ui()

    # ---------------- shell helpers ----------------
    def _require_conn(self) -> bool:
        if not self.exec.is_connected():
            messagebox.showwarning("COM", "Not connected")
            return False
        return True

    def _sh(self, cmd: str, timeout=2.0):
        # serialize access to executor
        with self._busy_lock:
            return self.exec.run(cmd, timeout_s=timeout)

    def _path(self, pin: str, leaf: str) -> str:
        return f"{SYSFS}/{pin}/{leaf}"

    def _gpio_num(self, pin: str):
        """Convert 'PA1' -> 1, 'PE6' -> 70 (STM32 style: P<port><idx>, 16 GPIOs per port)."""
        try:
            p = (pin or "").strip().upper()
            if not (len(p) >= 3 and p[0] == "P"):
                return None
            port = p[1]
            idx = int(p[2:])
            if port < "A" or port > "K":
                return None
            if idx < 0 or idx > 15:
                return None
            port_idx = ord(port) - ord("A")
            return port_idx * 16 + idx
        except Exception:
            return None

    def _export_pin(self, pin: str) -> bool:
        """Create sysfs node for pin via /sys/class/gpio/export (safe if already exported)."""
        n = self._gpio_num(pin)
        if n is None:
            return False
        # If already present, treat as OK.
        if self._exists(pin):
            return True
        ok, _ = self._sh(f'echo {n} > "{SYSFS}/export" 2>/dev/null || true', timeout=2.0)
        # Even if echo returns non-zero (busy), re-check presence.
        return self._exists(pin)

    def _unexport_pin(self, pin: str) -> bool:
        """Remove sysfs node for pin via /sys/class/gpio/unexport (safe if already unexported)."""
        n = self._gpio_num(pin)
        if n is None:
            return False
        ok, _ = self._sh(f'echo {n} > "{SYSFS}/unexport" 2>/dev/null || true', timeout=2.0)
        # Return True when it's gone.
        return not self._exists(pin)

    def _exists(self, pin: str) -> bool:
        ok, out = self._sh(f'test -d "{SYSFS}/{pin}" && echo OK || echo NO', timeout=2.0)
        return "OK" in out

    def _get_dir(self, pin: str):
        # Be tolerant to noisy shells: read last line and match suffix.
        ok, out = self._sh(f'cat "{self._path(pin,"direction")}" 2>/dev/null | tail -n 1', timeout=2.0)
        if not ok:
            return None
        s = (out or "").strip().lower()
        if s.endswith("in"):
            return "in"
        if s.endswith("out"):
            return "out"
        return None

    def _set_dir(self, pin: str, direction: str) -> bool:
        ok, out = self._sh(f'echo {direction} > "{self._path(pin,"direction")}"', timeout=2.0)
        return ok

    def _get_val(self, pin: str):
        # Strong parsing: strip everything except 0/1, take last digit.
        ok, out = self._sh(
            f'cat "{self._path(pin,"value")}" 2>/dev/null | tr -dc "01" | tail -c 1 ; echo',
            timeout=2.0,
        )
        if not ok:
            return None
        s = (out or "").strip()
        if s.endswith("1"):
            return 1
        if s.endswith("0"):
            return 0
        return None

    def _set_val(self, pin: str, v: int) -> bool:
        v = 1 if int(v) else 0
        ok, out = self._sh(f'echo {v} > "{self._path(pin,"value")}"', timeout=2.0)
        return ok

    # ---------------- UI ----------------
    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        # Left control panel
        left = ttk.Frame(root)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="TestGPIO", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 8))

        # pin selector
        pin_box = ttk.Labelframe(left, text="Pin")
        pin_box.pack(fill="x", pady=6)

        self.pin_combo = ttk.Combobox(pin_box, state="readonly", values=self.pins, textvariable=self.selected_pin, width=10)
        self.pin_combo.pack(side="left", padx=8, pady=8)
        self.pin_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_selected())

       #ttk.Button(pin_box, text="Refresh state", command=self.refresh_selected).pack(side="left", padx=6, pady=8)

        # init / cleanup
        init_box = ttk.Labelframe(left, text="Init / Cleanup")
        init_box.pack(fill="x", pady=6)

        r0 = ttk.Frame(init_box); r0.pack(fill="x", padx=8, pady=8)
        ttk.Button(r0, text="Init pins", command=self.init_pins).pack(side="left")
        ttk.Button(r0, text="Cleanup pins", command=self.cleanup_pins).pack(side="left", padx=8)
       

        # basic ops
        ops = ttk.Labelframe(left, text="Manual control")
        ops.pack(fill="x", pady=6)

        row1 = ttk.Frame(ops); row1.pack(fill="x", padx=8, pady=6)
        ttk.Button(row1, text="Set IN", width=10, command=lambda: self.set_dir_selected("in")).pack(side="left", padx=(0, 6))
        ttk.Button(row1, text="Set OUT", width=10, command=lambda: self.set_dir_selected("out")).pack(side="left")

        row2 = ttk.Frame(ops); row2.pack(fill="x", padx=8, pady=(0, 8))
        self.btn_write0 = ttk.Button(row2, text="Write 0", width=10, command=lambda: self.write_selected(0))
        self.btn_write0.pack(side="left", padx=(0, 6))
        self.btn_write1 = ttk.Button(row2, text="Write 1", width=10, command=lambda: self.write_selected(1))
        self.btn_write1.pack(side="left")

        # blink test
        blink = ttk.Labelframe(left, text="Blink test (OUT)")
        blink.pack(fill="x", pady=6)

        r = ttk.Frame(blink); r.pack(fill="x", padx=8, pady=6)
        ttk.Label(r, text="Count").pack(side="left")
        ttk.Spinbox(r, from_=1, to=1000, width=6, textvariable=self.blink_count).pack(side="left", padx=6)

        r2 = ttk.Frame(blink); r2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(r2, text="Period ms").pack(side="left")
        ttk.Spinbox(r2, from_=50, to=5000, width=6, textvariable=self.blink_period_ms).pack(side="left", padx=6)

        r3 = ttk.Frame(blink); r3.pack(fill="x", padx=8, pady=(0, 8))
        self.btn_blink = ttk.Button(r3, text="Start blink", command=self.start_blink)
        self.btn_blink.pack(side="left")
        ttk.Button(r3, text="Stop", command=self.stop_actions).pack(side="left", padx=8)

        # input monitor
        mon = ttk.Labelframe(left, text="Monitor (read inputs)")
        mon.pack(fill="x", pady=6)

        rr = ttk.Frame(mon); rr.pack(fill="x", padx=8, pady=6)
        ttk.Label(rr, text="Poll ms").pack(side="left")
        ttk.Spinbox(rr, from_=50, to=2000, width=6, textvariable=self.poll_ms).pack(side="left", padx=6)

        rr2 = ttk.Frame(mon); rr2.pack(fill="x", padx=8, pady=(0, 8))
        self.monitor_var = tk.IntVar(value=0)
        ttk.Checkbutton(rr2, text="Enable monitor", variable=self.monitor_var, command=self._monitor_toggle).pack(side="left")

        # Right panel: table + log
        right = ttk.Frame(root)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        # table of pins
        tbl = ttk.Labelframe(right, text="Pins state")
        tbl.pack(fill="x")

        hdr = ttk.Frame(tbl); hdr.pack(fill="x", padx=8, pady=(8, 0))
        for i, t in enumerate(["Pin", "Exists", "Dir", "Val", "Lamp"]):
            ttk.Label(hdr, text=t).grid(row=0, column=i, padx=6, sticky="w")

        self.rows = {}
        body = ttk.Frame(tbl); body.pack(fill="x", padx=8, pady=(6, 8))

        for idx, p in enumerate(self.pins):
            pin_lbl = ttk.Label(body, text=p, width=6)
            pin_lbl.grid(row=idx, column=0, padx=6, sticky="w")

            ex = ttk.Label(body, text="—", width=8)
            ex.grid(row=idx, column=1, padx=6, sticky="w")

            dr = ttk.Label(body, text="—", width=6)
            dr.grid(row=idx, column=2, padx=6, sticky="w")

            vl = ttk.Label(body, text="—", width=4)
            vl.grid(row=idx, column=3, padx=6, sticky="w")

            lamp = LedLamp(body, size=16, text="")
            lamp.grid(row=idx, column=4, padx=6, sticky="w")

            self.rows[p] = (ex, dr, vl, lamp)

        # log view
        lf = ttk.Labelframe(right, text="Test log")
        lf.pack(fill="both", expand=True, pady=(10, 0))

        self.text = tk.Text(lf, wrap="word", height=12)
        self.text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lf, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        # initial refresh
       #ttk.Button(right, text="Refresh all", command=self.refresh_all).pack(anchor="e", pady=(8, 0))

        self._apply_output_controls_state(False, None)
        self.refresh_all()

    def _ui_log(self, s: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {s}\n")
        self.text.see("end")
        self.log(s)


    def _apply_output_controls_state(self, present: bool, direction=None):
        """Enable Write/Blink only when pin exists and direction == 'out'."""
        enable = bool(present and (direction == "out"))
        state = "normal" if enable else "disabled"
        for b in (self.btn_write0, self.btn_write1, self.btn_blink):
            if b is not None:
                b.configure(state=state)

    # ---------------- actions ----------------
    def refresh_selected(self):
        pin = self.selected_pin.get().strip().upper()
        self.refresh_pin(pin)

    def init_pins(self):
        """Export all pins into sysfs (no direction/value changes)."""
        if not self._require_conn():
            return

        def worker():
            self.stop_flag.clear()
            self.after(0, lambda: self._ui_log("Init pins: export via /sys/class/gpio/export"))
            for p in self.pins:
                ok = self._export_pin(p)
                n = self._gpio_num(p)
                self.after(0, lambda pp=p, nn=n, oo=ok: self._ui_log(
                    f"{pp} (gpio{nn if nn is not None else '?'}) export -> {'OK' if oo else 'FAIL'}"
                ))
            self.after(0, self.refresh_all)

        threading.Thread(target=worker, daemon=True).start()

    def cleanup_pins(self):
        """Soft cleanup: set IN when present, then unexport. (Full reset requires reboot.)"""
        if not self._require_conn():
            return

        def worker():
            self.stop_flag.set()  # stop any blinking
            self.after(0, lambda: self._ui_log("Cleanup pins: set IN (if exists), then unexport"))
            for p in self.pins:
                try:
                    if self._exists(p):
                        self._sh(f'echo in > "{self._path(p,"direction")}" 2>/dev/null || true', timeout=2.0)
                    ok = self._unexport_pin(p)
                    n = self._gpio_num(p)
                    self.after(0, lambda pp=p, nn=n, oo=ok: self._ui_log(
                        f"{pp} (gpio{nn if nn is not None else '?'}) unexport -> {'OK' if oo else 'FAIL'}"
                    ))
                except Exception as e:
                    self.after(0, lambda pp=p, ee=e: self._ui_log(f"{pp}: cleanup error: {ee}"))

            self.after(0, lambda: self._ui_log("Note: unexport removes sysfs node only; for full pinctrl reset use reboot."))
            self.after(0, self.refresh_all)

        threading.Thread(target=worker, daemon=True).start()

    def refresh_all(self):
        if not self._require_conn():
            return
        threading.Thread(target=self._refresh_all_worker, daemon=True).start()

    def _refresh_all_worker(self):
        for p in self.pins:
            self.refresh_pin(p)

    def refresh_pin(self, pin: str):
        if not self._require_conn():
            return

        def worker():
            try:
                exists = self._exists(pin)
                if not exists:
                    def ui():
                        ex, dr, vl, lamp = self.rows[pin]
                        ex.config(text="NO")
                        dr.config(text="—")
                        vl.config(text="—")
                        lamp.set(False)
                        if pin == self.selected_pin.get().strip().upper():
                            self._apply_output_controls_state(False, None)
                    self.after(0, ui)
                    return

                d = self._get_dir(pin) or "?"
                v = self._get_val(pin)
                vv = "?" if v is None else str(v)

                def ui():
                    ex, dr, vl, lamp = self.rows[pin]
                    ex.config(text="OK")
                    dr.config(text=d)
                    vl.config(text=vv)
                    lamp.set(v == 1)
                    if pin == self.selected_pin.get().strip().upper():
                        self._apply_output_controls_state(True, d)
                self.after(0, ui)
            except Exception as e:
                self.after(0, lambda: self._ui_log(f"refresh {pin} error: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def set_dir_selected(self, direction: str):
        pin = self.selected_pin.get().strip().upper()
        if not self._require_conn():
            return

        def worker():
            self.stop_flag.clear()
            if not self._exists(pin):
                self.after(0, lambda: self._ui_log(f"{pin}: sysfs node not found"))
                return
            ok = self._set_dir(pin, direction)
            self.after(0, lambda: self._ui_log(f"{pin}: set direction {direction} -> {'OK' if ok else 'FAIL'}"))
            self.refresh_pin(pin)

        threading.Thread(target=worker, daemon=True).start()

    def write_selected(self, v: int):
        pin = self.selected_pin.get().strip().upper()
        if not self._require_conn():
            return

        def worker():
            self.stop_flag.clear()
            if not self._exists(pin):
                self.after(0, lambda: self._ui_log(f"{pin}: sysfs node not found"))
                return
            d = self._get_dir(pin)
            if d != "out":
                self.after(0, lambda: self._ui_log(f"{pin}: write blocked (Dir is {d or '?'}). Use Set OUT first."))
                self.after(0, lambda: self._apply_output_controls_state(True, d))
                return

            ok = self._set_val(pin, v)
            self.after(0, lambda: self._ui_log(f"{pin}: write {v} -> {'OK' if ok else 'FAIL'}"))
            self.refresh_pin(pin)

        threading.Thread(target=worker, daemon=True).start()

    def start_blink(self):
        pin = self.selected_pin.get().strip().upper()
        if not self._require_conn():
            return

        count = int(self.blink_count.get())
        period = int(self.blink_period_ms.get())
        if period < 30:
            period = 30

        self.stop_flag.clear()
        self._ui_log(f"{pin}: blink start count={count} period_ms={period}")

        def worker():
            if not self._exists(pin):
                self.after(0, lambda: self._ui_log(f"{pin}: sysfs node not found"))
                return
            d = self._get_dir(pin)
            if d != "out":
                self.after(0, lambda: self._ui_log(f"{pin}: blink blocked (Dir is {d or '?'}). Use Set OUT first."))
                return

            for i in range(count):
                if self.stop_flag.is_set():
                    break
                self._set_val(pin, 1)
                self.after(0, lambda p=pin: self.refresh_pin(p))
                time.sleep(period / 1000.0)

                if self.stop_flag.is_set():
                    break
                self._set_val(pin, 0)
                self.after(0, lambda p=pin: self.refresh_pin(p))
                time.sleep(period / 1000.0)

            self.after(0, lambda: self._ui_log(f"{pin}: blink done{' (stopped)' if self.stop_flag.is_set() else ''}"))
            self.after(0, lambda p=pin: self.refresh_pin(p))

        threading.Thread(target=worker, daemon=True).start()

    def stop_actions(self):
        self.stop_flag.set()
        self._ui_log("Stop requested")

    def _monitor_toggle(self):
        if self.monitor_var.get():
            self._ui_log("Monitor enabled")
            self._monitor_tick()
        else:
            self._ui_log("Monitor disabled")

    def _monitor_tick(self):
        if not self.monitor_var.get():
            return
        if not self.exec.is_connected():
            self.after(300, self._monitor_tick)
            return

        # light monitor: read all values quickly in one worker
        def worker():
            for p in self.pins:
                try:
                    if not self._exists(p):
                        continue
                    v = self._get_val(p)
                    if v is None:
                        continue
                    def ui_one(pin=p, vv=v):
                        ex, dr, vl, lamp = self.rows[pin]
                        lamp.set(vv == 1)
                        vl.config(text=str(vv))
                    self.after(0, ui_one)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

        self.after(max(50, int(self.poll_ms.get())), self._monitor_tick)
