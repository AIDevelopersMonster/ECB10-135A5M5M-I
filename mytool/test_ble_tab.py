# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


class TestBleTab(ttk.Frame):
    """
    BLE interactive control tab (STABLE)

    Start BLE:
      bluetoothctl (enter) -> power on -> menu advertise -> name EBYTE_BLE -> back -> advertise on

    Stop BLE:
      advertise off -> power off -> exit

    Clear:
      Clear output
    """

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    # ---------------- UI ----------------

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="BLE (interactive)").pack(anchor="w", pady=(0, 8))

        # ---- Start BLE sequence ----
        ttk.Label(left, text="Start BLE:").pack(anchor="w", pady=(4, 2))

        ttk.Button(left, text="1) bluetoothctl (enter)", width=28,
                   command=self.btctl_enter).pack(anchor="w", pady=2)

        ttk.Button(left, text="2) power on", width=28,
                   command=self.bt_power_on).pack(anchor="w", pady=2)

        ttk.Button(left, text="3) menu advertise", width=28,
                   command=self.bt_menu_advertise).pack(anchor="w", pady=2)

        ttk.Button(left, text="4) name EBYTE_BLE", width=28,
                   command=self.bt_name).pack(anchor="w", pady=2)

        ttk.Button(left, text="5) back", width=28,
                   command=self.bt_back).pack(anchor="w", pady=2)

        ttk.Button(left, text="6) advertise on", width=28,
                   command=self.bt_adv_on).pack(anchor="w", pady=2)

        ttk.Separator(left).pack(fill="x", pady=8)

        # ---- Stop BLE sequence ----
        ttk.Label(left, text="Stop BLE:").pack(anchor="w", pady=(4, 2))

        ttk.Button(left, text="1) advertise off", width=28,
                   command=self.bt_adv_off).pack(anchor="w", pady=2)

        ttk.Button(left, text="2) power off", width=28,
                   command=self.bt_power_off).pack(anchor="w", pady=2)

        ttk.Button(left, text="3) exit", width=28,
                   command=self.bt_exit).pack(anchor="w", pady=2)

        ttk.Separator(left).pack(fill="x", pady=8)

        # ---- Clear output ----
        ttk.Label(left, text="Clear output:").pack(anchor="w", pady=(4, 2))
        ttk.Button(left, text="Clear output", width=28,
                   command=self.clear_output).pack(anchor="w", pady=2)

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    # ---------------- helpers ----------------

    def _ts(self):
        return time.strftime("%H:%M:%S")

    def _append(self, msg: str):
        self.text.insert("end", f"[{self._ts()}] {msg}\n")
        self.text.see("end")

    def _exec_cmd(self, cmd: str):
        fn = None
        for name in ("run", "exec", "execute", "send_command", "cmd"):
            if hasattr(self.exec, name) and callable(getattr(self.exec, name)):
                fn = getattr(self.exec, name)
                break

        if fn is None:
            return "Executor error: no run/exec method"

        res = fn(cmd)

        if isinstance(res, tuple) and len(res) >= 2:
            return (res[1] or "").strip()

        return (res or "").strip()

    def _run(self, cmd: str):
        self._append(f"$ {cmd}")
        out = self._exec_cmd(cmd)
        if out:
            for line in out.splitlines():
                self._append(line)
        self._append("OK")
        self._append("")

    # ---------------- bluetoothctl actions ----------------

    def btctl_enter(self):
        self._run("bluetoothctl")

    def bt_power_on(self):
        self._run("power on")

    def bt_menu_advertise(self):
        self._run("menu advertise")

    def bt_name(self):
        self._run("name EBYTE_BLE")

    def bt_back(self):
        self._run("back")

    def bt_adv_on(self):
        self._run("advertise on")

    def bt_adv_off(self):
        self._run("advertise off")

    def bt_power_off(self):
        self._run("power off")

    def bt_exit(self):
        self._run("exit")

    # ---------------- UI service ----------------

    def clear_output(self):
        self.text.delete("1.0", "end")
