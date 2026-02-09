# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


class TestBleTab(ttk.Frame):
    """
    BLE interactive control tab (STABLE)

    Buttons send commands into interactive bluetoothctl session,
    exactly like manual typing in terminal.

    Includes:
      - bluetoothctl enter
      - power on / off
      - menu advertise
      - name EBYTE_BLE
      - back
      - advertise on / off
      - exit
      - clear output
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

        ttk.Button(left, text="bluetoothctl (enter)", width=28,
                   command=self.btctl_enter).pack(anchor="w", pady=3)

        ttk.Button(left, text="power on", width=28,
                   command=self.bt_power_on).pack(anchor="w", pady=3)

        ttk.Button(left, text="power off", width=28,
                   command=self.bt_power_off).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=6)

        ttk.Button(left, text="menu advertise", width=28,
                   command=self.bt_menu_advertise).pack(anchor="w", pady=3)

        ttk.Button(left, text="name EBYTE_BLE", width=28,
                   command=self.bt_name).pack(anchor="w", pady=3)

        ttk.Button(left, text="back", width=28,
                   command=self.bt_back).pack(anchor="w", pady=3)

        ttk.Button(left, text="advertise on", width=28,
                   command=self.bt_adv_on).pack(anchor="w", pady=3)

        ttk.Button(left, text="advertise off", width=28,
                   command=self.bt_adv_off).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=6)

        ttk.Button(left, text="exit bluetoothctl", width=28,
                   command=self.bt_exit).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=8)

        ttk.Button(left, text="Clear output", width=28,
                   command=self.clear_output).pack(anchor="w", pady=3)

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
        """
        Same executor pattern as stable tabs.
        """
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

    def bt_power_off(self):
        self._run("power off")

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

    def bt_exit(self):
        self._run("exit")

    # ---------------- UI service ----------------

    def clear_output(self):
        self.text.delete("1.0", "end")
