# terminal_tab.py
# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk


class TerminalTab(ttk.Frame):
    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(side="top", fill="x")

        ttk.Label(top, text="Command:").pack(side="left")
        self.cmd_var = tk.StringVar(value="")
        self.cmd_entry = ttk.Entry(top, textvariable=self.cmd_var)
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.cmd_entry.bind("<Return>", lambda e: self.send())

        self.btn_send = ttk.Button(top, text="Send", command=self.send)
        self.btn_send.pack(side="left", padx=(0, 8))

        ttk.Button(top, text="Clear", command=self.clear).pack(side="left")

        # output
        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.pack(side="top", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    def clear(self):
        self.text.delete("1.0", "end")

    def _append(self, s: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {s}\n")
        self.text.see("end")

    def send(self):
        cmd = (self.cmd_var.get() or "").strip()
        if not cmd:
            return

        self.cmd_var.set("")
        self._append(f"$ {cmd}")

        if not self.exec.is_connected():
            self._append("Not connected")
            return

        self.btn_send.config(state="disabled")

        def worker():
            ok, out = self.exec.run(cmd, timeout_s=6.0)
            def ui():
                if out:
                    self._append(out)
                else:
                    self._append("(no output)")
                self._append("OK" if ok else "FAIL")
                self.btn_send.config(state="normal")
            self.after(0, ui)

        threading.Thread(target=worker, daemon=True).start()
