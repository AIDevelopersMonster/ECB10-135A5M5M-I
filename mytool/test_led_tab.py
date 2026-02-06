# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk
from typing import Any, List, Tuple
import re


class TestLedTab(ttk.Frame):
    """
    LED test tab for Linux sysfs (/sys/class/leds)

    What this tab can do:
      - Scan available LEDs
      - ON/OFF via brightness
      - Read current trigger and list available triggers
      - Set trigger (heartbeat/timer/cpu/mmc0/...)
      - Timer blink setup (delay_on/delay_off) when trigger=timer

    Sysfs paths used:
      /sys/class/leds/<led>/{brightness,trigger,delay_on,delay_off}
    """

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)

        self.led_var = tk.StringVar(value="")
        self.trigger_var = tk.StringVar(value="")
        self.delay_on_var = tk.StringVar(value="200")
        self.delay_off_var = tk.StringVar(value="200")

        self._build_ui()

    # -----------------------------
    # Executor adapter (robust)
    # -----------------------------
    def _run(self, cmd: str, timeout_s: int = 10) -> Tuple[bool, str]:
        """
        Execute `cmd` using whatever interface `executor` provides.

        Supported executor patterns:
          - executor(cmd) -> str OR (ok, out) OR dict
          - executor.run(cmd) / executor.exec(cmd) / executor.send_command(cmd) / executor.send(cmd) / executor.execute(cmd)
        """
        ex = self.exec

        def _normalize(res: Any) -> Tuple[bool, str]:
            if res is None:
                return False, ""
            if isinstance(res, tuple) and len(res) == 2:
                ok, out = res
                return bool(ok), str(out)
            if isinstance(res, dict):
                ok = bool(res.get("ok", True))
                out = res.get("out") or res.get("stdout") or res.get("result") or ""
                return ok, str(out)
            return True, str(res)

        try:
            if callable(ex):
                return _normalize(ex(cmd))
            for attr in ("run", "exec", "send_command", "send", "execute"):
                if hasattr(ex, attr):
                    fn = getattr(ex, attr)
                    if callable(fn):
                        try:
                            return _normalize(fn(cmd, timeout=timeout_s))
                        except TypeError:
                            return _normalize(fn(cmd))
            return False, f"Executor interface not recognized (cmd={cmd})"
        except Exception as e:
            return False, f"Executor error: {e}"

    # -----------------------------
    # UI helpers
    # -----------------------------
    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="LED (sysfs)", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="LED device:").pack(anchor="w")
        self.led_combo = ttk.Combobox(left, textvariable=self.led_var, state="readonly", width=26, values=[])
        self.led_combo.pack(anchor="w", pady=(0, 8))
        self.led_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_led_state())

        ttk.Button(left, text="Scan LEDs", width=22, command=self.scan_leds).pack(anchor="w", pady=3)
        ttk.Button(left, text="LED ON (brightness=1)", width=22, command=lambda: self.set_brightness(1)).pack(anchor="w", pady=3)
        ttk.Button(left, text="LED OFF (brightness=0)", width=22, command=lambda: self.set_brightness(0)).pack(anchor="w", pady=3)
        ttk.Button(left, text="Read state", width=22, command=self.refresh_led_state).pack(anchor="w", pady=3)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(left, text="Trigger:").pack(anchor="w")
        self.trig_combo = ttk.Combobox(left, textvariable=self.trigger_var, state="readonly", width=26, values=[])
        self.trig_combo.pack(anchor="w", pady=(0, 8))

        ttk.Button(left, text="Load triggers", width=22, command=self.load_triggers).pack(anchor="w", pady=3)
        ttk.Button(left, text="Set trigger", width=22, command=self.set_trigger_from_ui).pack(anchor="w", pady=3)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(left, text="Timer blink (ms):").pack(anchor="w")
        row = ttk.Frame(left)
        row.pack(anchor="w", pady=(0, 6))
        ttk.Label(row, text="on").pack(side="left")
        ttk.Entry(row, textvariable=self.delay_on_var, width=6).pack(side="left", padx=(4, 10))
        ttk.Label(row, text="off").pack(side="left")
        ttk.Entry(row, textvariable=self.delay_off_var, width=6).pack(side="left", padx=(4, 0))

        ttk.Button(left, text="Enable timer blink", width=22, command=self.enable_timer_blink).pack(anchor="w", pady=3)
        ttk.Button(left, text="Stop blinking (none)", width=22, command=lambda: self.set_trigger("none")).pack(anchor="w", pady=3)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(left, text="Quick attach:").pack(anchor="w")
        quick = ttk.Frame(left)
        quick.pack(anchor="w")
        ttk.Button(quick, text="heartbeat", width=10, command=lambda: self.set_trigger("heartbeat")).grid(row=0, column=0, padx=2, pady=2, sticky="w")
        ttk.Button(quick, text="cpu0", width=10, command=lambda: self.set_trigger("cpu0")).grid(row=0, column=1, padx=2, pady=2, sticky="w")
        ttk.Button(quick, text="default-on", width=10, command=lambda: self.set_trigger("default-on")).grid(row=1, column=0, padx=2, pady=2, sticky="w")
        ttk.Button(quick, text="mmc0", width=10, command=lambda: self.set_trigger("mmc0")).grid(row=1, column=1, padx=2, pady=2, sticky="w")

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        self.scan_leds()

    def _append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {msg}\n")
        self.text.see("end")
        try:
            self.log_fn(msg)
        except Exception:
            pass

    def _led_path(self) -> str:
        led = self.led_var.get().strip()
        return f"/sys/class/leds/{led}" if led else ""

    # -----------------------------
    # LED operations
    # -----------------------------
    def scan_leds(self):
        self._append("== LED scan ==")
        ok, out = self._run("ls -1 /sys/class/leds 2>/dev/null || true")
        if not ok:
            self._append(f"ERR: {out}")
            return
        leds = [line.strip() for line in out.splitlines() if line.strip()]
        self.led_combo["values"] = leds
        if leds and (self.led_var.get() not in leds):
            self.led_var.set(leds[0])
        self._append(f"Found LEDs: {', '.join(leds) if leds else '(none)'}")
        if leds:
            self.refresh_led_state()
        self._append("OK\n")

    def set_brightness(self, value: int):
        lp = self._led_path()
        if not lp:
            self._append("ERR: Select LED first.")
            return
        v = 1 if int(value) else 0
        self._append(f"== brightness -> {v} ==")
        ok, out = self._run(f"echo {v} > {lp}/brightness 2>/dev/null && echo OK || echo FAIL")
        self._append(out.strip() if out else ("OK" if ok else "FAIL"))
        self._append("")

    def refresh_led_state(self):
        lp = self._led_path()
        if not lp:
            return
        self._append(f"== LED state ({lp}) ==")
        _, b = self._run(f"cat {lp}/brightness 2>/dev/null || echo ?")
        _, t = self._run(f"cat {lp}/trigger 2>/dev/null || echo ?")
        brightness = (b.strip().splitlines()[-1] if b else "?").strip()
        trigger_raw = t.strip()
        current = self._parse_current_trigger(trigger_raw)
        self._append(f"brightness: {brightness}")
        self._append(f"trigger: {current if current else '(unknown)'}")
        self._populate_triggers_from_raw(trigger_raw)
        self._append("OK\n")

    def load_triggers(self):
        lp = self._led_path()
        if not lp:
            self._append("ERR: Select LED first.")
            return
        self._append("== Load triggers ==")
        ok, out = self._run(f"cat {lp}/trigger 2>/dev/null || true")
        if not ok:
            self._append(f"ERR: {out}")
            return
        self._populate_triggers_from_raw(out)
        cur = self._parse_current_trigger(out)
        if cur:
            self.trigger_var.set(cur)
        self._append(f"Current: {cur if cur else '(unknown)'}")
        self._append("OK\n")

    def set_trigger_from_ui(self):
        trig = self.trigger_var.get().strip()
        if not trig:
            self._append("ERR: Select trigger first.")
            return
        self.set_trigger(trig)

    def set_trigger(self, trigger: str):
        lp = self._led_path()
        if not lp:
            self._append("ERR: Select LED first.")
            return
        trigger = trigger.strip()
        self._append(f"== set trigger -> {trigger} ==")
        ok, out = self._run(f"echo {trigger} > {lp}/trigger 2>/dev/null && echo OK || echo FAIL")
        self._append(out.strip() if out else ("OK" if ok else "FAIL"))
        self.refresh_led_state()

    def enable_timer_blink(self):
        lp = self._led_path()
        if not lp:
            self._append("ERR: Select LED first.")
            return
        try:
            on_ms = max(1, int(self.delay_on_var.get().strip()))
            off_ms = max(1, int(self.delay_off_var.get().strip()))
        except Exception:
            self._append("ERR: delay_on/off must be integers (ms).")
            return

        self._append(f"== timer blink ({on_ms} / {off_ms}) ==")
        self._run(f"echo timer > {lp}/trigger 2>/dev/null || true")
        ok1, out1 = self._run(f"echo {on_ms} > {lp}/delay_on 2>/dev/null && echo OK || echo FAIL")
        ok2, out2 = self._run(f"echo {off_ms} > {lp}/delay_off 2>/dev/null && echo OK || echo FAIL")
        self._append(f"delay_on: {out1.strip() if out1 else ('OK' if ok1 else 'FAIL')}")
        self._append(f"delay_off: {out2.strip() if out2 else ('OK' if ok2 else 'FAIL')}")
        self.refresh_led_state()

    # -----------------------------
    # Parsing helpers
    # -----------------------------
    @staticmethod
    def _parse_current_trigger(raw: str) -> str:
        m = re.search(r"\[([^\]]+)\]", raw)
        return (m.group(1).strip() if m else "")

    def _populate_triggers_from_raw(self, raw: str):
        tokens = [t.strip() for t in raw.replace("\n", " ").split() if t.strip()]
        triggers: List[str] = []
        current = ""
        for tok in tokens:
            if tok.startswith("[") and tok.endswith("]"):
                current = tok[1:-1]
                triggers.append(current)
            else:
                triggers.append(tok)

        seen = set()
        uniq: List[str] = []
        for t in triggers:
            if t not in seen:
                uniq.append(t)
                seen.add(t)

        if uniq:
            self.trig_combo["values"] = uniq
            if current:
                self.trigger_var.set(current)
