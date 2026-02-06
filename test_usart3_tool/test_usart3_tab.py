# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


EXPECTED_TTY = "ttySTM3"
EXPECTED_DEV = f"/dev/{EXPECTED_TTY}"
EXPECTED_SYSFS = f"/sys/class/tty/{EXPECTED_TTY}"


class TestUsart3Tab(ttk.Frame):
    """
    USART3 minimal check:
    - only reports whether ttySTM3 is initialized (sysfs/dev node exists)
    """

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="USART3").pack(anchor="w", pady=(0, 8))

        ttk.Button(
            left,
            text="Check init status",
            width=24,
            command=self.check_init
        ).pack(anchor="w", pady=3)

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    def _append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {msg}\n")
        self.text.see("end")

    def _exec_cmd(self, cmd: str) -> str:
        # Try common executor method names
        fn = None
        for name in ("run", "exec", "execute", "send_command", "cmd"):
            if hasattr(self.exec, name) and callable(getattr(self.exec, name)):
                fn = getattr(self.exec, name)
                break
        if fn is None:
            return "Executor has no run/exec method"

        res = fn(cmd)
        if isinstance(res, tuple) and len(res) >= 2:
            return (res[1] or "").strip()
        return (res or "").strip()

    def check_init(self):
        self._append("== USART3 init status ==")
        self._append(f"Expected TTY: {EXPECTED_TTY} (serial3 @ 0x40019000)")

        sysfs_ok = self._exec_cmd(f"test -e {EXPECTED_SYSFS} && echo OK || echo NO")
        dev_ok = self._exec_cmd(f"test -c {EXPECTED_DEV} && echo OK || echo NO")

        self._append(f"sysfs: {EXPECTED_SYSFS}: {sysfs_ok}")
        self._append(f"dev:   {EXPECTED_DEV}: {dev_ok}")

        if "OK" in sysfs_ok and "OK" in dev_ok:
            self._append("USART3 port initialized")
            self._append("OK")
        else:
            self._append("USART3 port NOT initialized in this firmware")
            self._append("SKIPPED")

        self._append("")
