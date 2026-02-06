# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


UART5_DEV = "/dev/ttySTM2"   # можно будет вынести в конфиг/настройки UI


class TestUart5Tab(ttk.Frame):
    """
    UART5 test tab:
    - device-level test (no wiring)
    - optional hardware loopback test (TX<->RX jumper)
    """

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="UART5").pack(anchor="w", pady=(0, 8))

        ttk.Button(
            left,
            text="Run device test",
            width=24,
            command=self.run_device_test
        ).pack(anchor="w", pady=3)

        ttk.Button(
            left,
            text="Run loopback test",
            width=24,
            command=self.run_loopback_test
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
        """
        Execute command on TARGET (board) via ShellExecutor.
        Supports different executor method names.
        Returns combined output as string.
        """
        # Not connected handling (if available)
        if hasattr(self.exec, "is_connected") and callable(self.exec.is_connected):
            if not self.exec.is_connected():
                return "Not connected"

        # Try common method names
        fn = None
        for name in ("run", "exec", "execute", "send_command", "cmd"):
            if hasattr(self.exec, name) and callable(getattr(self.exec, name)):
                fn = getattr(self.exec, name)
                break
        if fn is None:
            return "Executor has no run/exec method"

        res = fn(cmd)

        # Normalize possible return formats:
        # - string output
        # - (ok, output) tuple
        if isinstance(res, tuple) and len(res) >= 2:
            return (res[1] or "").strip()
        return (res or "").strip()

    # -------------------------
    # Tests
    # -------------------------

    def run_device_test(self):
        dev = UART5_DEV

        self._append("== UART5 device-level test ==")

        out = self._exec_cmd(f"ls -l {dev} || echo '__NO_DEV__'")
        if "__NO_DEV__" in out or "No such file" in out:
            self._append(f"Device not found: {dev}")
            self._append("FAIL")
            self._append("")
            return

        self._append(f"Device found: {dev}")

        out = self._exec_cmd(f"stty -F {dev} 115200 raw -echo -crtscts 2>&1 || echo '__STTY_FAIL__'")
        if "__STTY_FAIL__" in out:
            self._append("stty failed")
            self._append(out.replace("__STTY_FAIL__", "").strip())
            self._append("FAIL")
            self._append("")
            return

        if out:
            self._append(out)
        self._append("stty configured")

        out = self._exec_cmd(f"echo UART5_DEVICE_TEST > {dev} 2>&1 || echo '__WRITE_FAIL__'")
        if "__WRITE_FAIL__" in out:
            self._append("TX write failed")
            self._append(out.replace("__WRITE_FAIL__", "").strip())
            self._append("FAIL")
            self._append("")
            return

        if out:
            self._append(out)

        self._append("TX write OK")
        self._append("RX not verified (no loopback)")
        self._append("OK")
        self._append("")

    def run_loopback_test(self):
        dev = UART5_DEV

        self._append("== UART5 loopback test ==")
        self._append("NOTE: requires physical jumper TX<->RX on UART5 pins")
        self._append("If no jumper yet: result should be treated as SKIPPED")

        # shell loopback without `timeout` dependency
        cmd = (
            f"stty -F {dev} 115200 raw -echo -crtscts || exit 1; "
            f"rm -f /tmp/uart5_rx.txt /tmp/uart5_cat.pid; "
            f"(cat {dev} > /tmp/uart5_rx.txt & echo $! > /tmp/uart5_cat.pid); "
            f"sleep 0.2; "
            f"echo UART5_LOOPBACK_TEST > {dev}; "
            f"sleep 0.6; "
            f"kill $(cat /tmp/uart5_cat.pid) 2>/dev/null; "
            f"cat /tmp/uart5_rx.txt 2>/dev/null | tail -n 5"
        )

        out = self._exec_cmd(cmd)

        if "UART5_LOOPBACK_TEST" in out:
            self._append("Loopback OK")
            self._append("PASS")
        else:
            self._append("No loopback data received")
            self._append("SKIPPED (no jumper) or FAIL (wiring/port)")

        if out:
            self._append("--- rx dump ---")
            self._append(out)

        self._append("")
