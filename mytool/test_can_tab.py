# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


CAN_IFACE = "can0"
CAN_BITRATE = 1000000

# Default test frame
TEST_ID = "123"
TEST_DATA = "DE.AD.BE.EF"


class TestCanTab(ttk.Frame):
    """
    CAN tests:
    1) Soft check (Linux / driver / tools)
    2) Loopback test (no hardware)  -> PASS/FAIL
    3) Send test (external device)  -> OK + NO LINK note
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

        ttk.Label(left, text="CAN").pack(anchor="w", pady=(0, 8))

        ttk.Button(left, text="Soft check", width=22, command=self.run_soft_check).pack(anchor="w", pady=3)
        ttk.Button(left, text="Loopback test", width=22, command=self.run_loopback_test).pack(anchor="w", pady=3)
        ttk.Button(left, text="Send test", width=22, command=self.run_send_test).pack(anchor="w", pady=3)

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    # ---------------- helpers ----------------

    def _append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {msg}\n")
        self.text.see("end")

    def _exec_cmd(self, cmd: str) -> str:
        """
        Execute command on target (board) via provided executor.
        Normalizes possible executor API variants.
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

    def _iface_exists(self) -> bool:
        out = self._exec_cmd(f"ip link show {CAN_IFACE} 2>&1 || true")
        return (CAN_IFACE + ":") in out and "does not exist" not in out

    def _tools_present(self) -> bool:
        out = self._exec_cmd("which candump cansend 2>/dev/null || true")
        return "candump" in out and "cansend" in out

    def _setup_can(self, loopback: bool) -> str:
        """
        Configure CAN interface. Returns '' if OK or error string.
        """
        self._exec_cmd(f"ifconfig {CAN_IFACE} down 2>&1 || true")

        lb = " loopback on" if loopback else ""
        out = self._exec_cmd(
            f"ip link set {CAN_IFACE} type can bitrate {CAN_BITRATE}{lb} 2>&1 || echo __IP_FAIL__"
        )
        if "__IP_FAIL__" in out:
            return out.replace("__IP_FAIL__", "").strip() or "ip link set failed"

        out2 = self._exec_cmd(f"ifconfig {CAN_IFACE} up 2>&1 || echo __UP_FAIL__")
        if "__UP_FAIL__" in out2:
            return out2.replace("__UP_FAIL__", "").strip() or "ifconfig up failed"

        return ""

    def _show_details(self):
        out = self._exec_cmd(f"ip -details link show {CAN_IFACE} 2>&1 | head -n 40")
        if out:
            self._append("ip -details:")
            self._append(out)

    # ---------------- tests ----------------

    def run_soft_check(self):
        self._append("== CAN soft check ==")

        if not self._iface_exists():
            self._append(f"{CAN_IFACE} not found")
            self._append("SKIPPED")
            self._append("")
            return

        self._append(f"{CAN_IFACE} exists")

        if not self._tools_present():
            self._append("can-utils not installed (candump/cansend missing)")
            self._append("FAIL")
            self._append("")
            return

        self._append("can-utils present")

        out = self._exec_cmd("dmesg | grep -i -E 'm_can|can0|CAN device driver' | tail -n 8")
        if out:
            self._append("dmesg (tail):")
            self._append(out)

        self._show_details()
        self._append("OK")
        self._append("")

    def run_loopback_test(self):
        self._append("== CAN loopback test ==")
        self._append("No external hardware required")

        if not self._iface_exists():
            self._append(f"{CAN_IFACE} not found")
            self._append("SKIPPED")
            self._append("")
            return

        if not self._tools_present():
            self._append("can-utils not installed (candump/cansend missing)")
            self._append("SKIPPED")
            self._append("")
            return

        err = self._setup_can(loopback=True)
        if err:
            self._append("Failed to configure CAN (loopback on)")
            self._append(err)
            self._append("FAIL")
            self._append("")
            return

        self._append(f"Interface configured: {CAN_IFACE} bitrate={CAN_BITRATE} loopback=on")
        self._show_details()

        # Key improvement:
        # candump -n 1 exits after one frame => no background PID/kill => no hangs.
        cmd = (
            "rm -f /tmp/can_rx.txt; "
            f"(candump -L -n 1 {CAN_IFACE} > /tmp/can_rx.txt 2>/dev/null &); "
            "sleep 0.2; "
            f"cansend {CAN_IFACE} {TEST_ID}#{TEST_DATA} 2>&1 || echo __SEND_FAIL__; "
            "sleep 0.8; "
            f"grep -q ' {TEST_ID}#' /tmp/can_rx.txt && echo HIT || echo MISS; "
            "tail -n 5 /tmp/can_rx.txt 2>/dev/null"
        )

        out = self._exec_cmd(cmd)

        if "__SEND_FAIL__" in out:
            self._append("cansend failed")
            self._append(out.replace("__SEND_FAIL__", "").strip())
            self._append("FAIL")
            self._append("")
            return

        if "HIT" in out:
            self._append("Loopback OK")
            self._append("PASS")
        else:
            self._append("No loopback data received")
            self._append("FAIL")

        rx_dump = out.replace("HIT", "").replace("MISS", "").strip()
        if rx_dump:
            self._append("--- rx dump ---")
            self._append(rx_dump)

        self._append("")

    def run_send_test(self):
        self._append("== CAN send test ==")
        self._append("External USB-CAN required for RX validation")

        if not self._iface_exists():
            self._append(f"{CAN_IFACE} not found")
            self._append("SKIPPED")
            self._append("")
            return

        if not self._tools_present():
            self._append("can-utils not installed (candump/cansend missing)")
            self._append("SKIPPED")
            self._append("")
            return

        err = self._setup_can(loopback=False)
        if err:
            self._append("Failed to configure CAN (loopback off)")
            self._append(err)
            self._append("FAIL")
            self._append("")
            return

        self._append(f"Interface configured: {CAN_IFACE} bitrate={CAN_BITRATE} loopback=off")
        self._show_details()

        out = self._exec_cmd(f"cansend {CAN_IFACE} {TEST_ID}#{TEST_DATA} 2>&1 || echo __SEND_FAIL__")
        if "__SEND_FAIL__" in out:
            self._append("cansend failed")
            self._append(out.replace("__SEND_FAIL__", "").strip())
            self._append("FAIL")
            self._append("")
            return

        if out:
            self._append(out)

        self._append("Frame sent")
        self._append("NO LINK: RX not checked (expected without external USB-CAN or proper termination)")
        self._append("OK")
        self._append("")
