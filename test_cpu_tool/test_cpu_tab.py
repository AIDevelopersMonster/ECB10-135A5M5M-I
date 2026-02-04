# test_cpu_tab.py
# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk


CPU_COMMANDS = [
    ("Model",              "cat /proc/device-tree/model 2>/dev/null || echo '(no model)'"),
    ("Kernel",             "uname -a"),
    ("CPU info (short)",   "cat /proc/cpuinfo | egrep -i 'model name|Hardware|processor|BogoMIPS' | head -n 50"),
    ("Meminfo",            "cat /proc/meminfo | head -n 30"),
    ("Uptime",             "uptime; cat /proc/loadavg"),
    ("Top (5 lines)",      "top -b -n 1 | head -n 15"),
    ("Dmesg (last 50)",    "dmesg | tail -n 50"),
]


class TestCPUTab(ttk.Frame):
    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Test CPU").pack(anchor="w", pady=(0, 8))

        for title, cmd in CPU_COMMANDS:
            ttk.Button(left, text=title, width=22, command=lambda c=cmd, t=title: self.run_test(t, c)).pack(
                anchor="w", pady=3
            )

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="Run ALL", width=22, command=self.run_all).pack(anchor="w", pady=3)

        # output
        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    def _append(self, s: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {s}\n")
        self.text.see("end")

    def run_test(self, title: str, cmd: str):
        if not self.exec.is_connected():
            self._append("Not connected")
            return

        self._append(f"== {title} ==")
        self._append(f"$ {cmd}")

        def worker():
            ok, out = self.exec.run(cmd, timeout_s=8.0)
            def ui():
                self._append(out if out else "(no output)")
                self._append("OK" if ok else "FAIL")
                self._append("")
            self.after(0, ui)

        threading.Thread(target=worker, daemon=True).start()

    def run_all(self):
        # Run sequentially in one worker to avoid mixing outputs
        if not self.exec.is_connected():
            self._append("Not connected")
            return

        def worker():
            for title, cmd in CPU_COMMANDS:
                ok, out = self.exec.run(cmd, timeout_s=10.0)
                def ui_one(t=title, c=cmd, o=out, k=ok):
                    self._append(f"== {t} ==")
                    self._append(f"$ {c}")
                    self._append(o if o else "(no output)")
                    self._append("OK" if k else "FAIL")
                    self._append("")
                self.after(0, ui_one)

        threading.Thread(target=worker, daemon=True).start()
