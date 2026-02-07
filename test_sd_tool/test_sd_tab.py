# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


class TestSDTab(ttk.Frame):
    """
    SD — safe quick test tab (uses same executor contract as TerminalTab).
    """

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="SD").pack(anchor="w", pady=(0, 8))

        ttk.Button(
            left,
            text="Run (safe test)",
            width=22,
            command=self.run_safe
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

    def _run(self, cmd: str, timeout_s: float = 6.0):
        """
        Run command via ShellExecutor contract: ok, out = exec.run(cmd, timeout_s=?)
        """
        if not self.exec.is_connected():
            return False, "Not connected"
        ok, out = self.exec.run(cmd, timeout_s=timeout_s)
        return bool(ok), (out or "")

    def run_safe(self):
        self._append("== SD card quick test (SAFE) ==")

        # 0) Must be connected
        if not self.exec.is_connected():
            self._append("Not connected")
            self._append("FAIL\n")
            return

        # 1) Kernel sees SD
        ok, out = self._run("ls /sys/block | grep -E '^mmcblk[0-9]+$'", timeout_s=3.0)
        if not ok or not out.strip():
            self._append(out.strip() if out else "(no output)")
            self._append("SD device not found in /sys/block")
            self._append("FAIL\n")
            return
        self._append(f"Kernel block device(s): {out.strip()}")

        # 2) Root filesystem (BusyBox)
        ok, out = self._run("mount | grep ' on / '", timeout_s=3.0)
        if not ok or not out.strip():
            self._append(out.strip() if out else "(no output)")
            self._append("Cannot determine root filesystem")
            self._append("FAIL\n")
            return
        self._append(f"Root filesystem: {out.strip()}")

        # 3) Free space
        ok, out = self._run("df -h / | tail -1", timeout_s=3.0)
        if ok and out.strip():
            parts = out.split()
            if len(parts) >= 4:
                self._append(f"Free space: {parts[3]}")

        # 4) Safe write/read (1MB)
        test_file = "/tmp/sd_test.bin"

        ok, wout = self._run(f"dd if=/dev/zero of={test_file} bs=512 count=2048 2>&1", timeout_s=10.0)
        if not ok:
            self._append(wout.strip() if wout else "(no output)")
            self._append("Write test FAILED")
            self._append("FAIL\n")
            return
        self._append("Write test: OK (1MB)")

        ok, rout = self._run(f"dd if={test_file} of=/dev/null bs=512 count=2048 2>&1", timeout_s=10.0)
        if not ok:
            self._append(rout.strip() if rout else "(no output)")
            self._append("Read test FAILED")
            self._append("FAIL\n")
            return
        self._append("Read test: OK (1MB)")

        # 5) Cleanup
        self._run(f"rm -f {test_file}", timeout_s=3.0)
        self._run("sync", timeout_s=6.0)

        self._append("Cleanup: OK")
        self._append("SD test PASSED\n")
