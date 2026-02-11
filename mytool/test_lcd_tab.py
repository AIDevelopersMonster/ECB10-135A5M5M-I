# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


class TestLcdTab(ttk.Frame):
    """
    Lcd — empty test tab template.
    """

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Lcd").pack(anchor="w", pady=(0, 8))

        ttk.Button(
            left,
            text="Run (stub)",
            width=22,
            command=self.run_stub
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

    def run_stub(self):
        self._append(f"== Lcd ==")
        self._append("No tests implemented.")
        self._append("OK")
        self._append("")
