# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple


class TestWifiapTab(ttk.Frame):
    """Wi‑Fi AP (NO Internet) — stable AP + DHCP for phone.

    Uses:
      - hostapd -B /etc/hostapd.conf
      - dnsmasq with config in /tmp/wifiap/dnsmasq.conf

    Design rules (same as our working tabs):
      - No threads
      - Executor compatibility: callable OR object with run/exec/execute/shell
      - Executor may return str OR (ok: bool, out: str)

    Quick checklist:
      1) Press "Start AP".
      2) Connect phone to SSID: EBYTE, PASS: 12345678.
      3) Press "Check clients".

    Note: Internet/NAT will be implemented in a separate button/tab later.
    """

    DEFAULT_IFACE = "wlan0"
    DEFAULT_IP = "192.168.10.1/24"
    DEFAULT_SSID = "EBYTE"
    DEFAULT_PASS = "12345678"

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    # ------------------------------------------------------------------
    # Executor adapter
    # ------------------------------------------------------------------
    def _exec_cmd(self, cmd: str) -> Tuple[bool, str]:
        """Unified executor adapter.

        Returns:
            (ok: bool, out: str)
        """
        try:
            if callable(self.exec):
                res = self.exec(cmd)
            else:
                res = None
                for attr in ("run", "exec", "execute", "shell"):
                    if hasattr(self.exec, attr):
                        res = getattr(self.exec, attr)(cmd)
                        break
                else:
                    raise TypeError("Executor does not support command execution")
        except Exception as e:
            return False, f"ERROR: {e}"

        if isinstance(res, tuple) and len(res) == 2:
            ok, out = res
            return bool(ok), "" if out is None else str(out)

        return True, "" if res is None else str(res)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Wi‑Fi AP").pack(anchor="w", pady=(0, 8))

        ttk.Button(left, text="Start AP", width=22, command=self.start_ap).pack(anchor="w", pady=3)
        ttk.Button(left, text="Stop AP", width=22, command=self.stop_ap).pack(anchor="w", pady=3)
        ttk.Button(left, text="Check clients", width=22, command=self.check_clients).pack(anchor="w", pady=3)
        ttk.Button(left, text="Status", width=22, command=self.status).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="Clear", width=22, command=self.clear).pack(anchor="w", pady=3)

        hint = ttk.LabelFrame(left, text="Phone")
        hint.pack(fill="x", pady=(10, 0))
        ttk.Label(
            hint,
            text=(
                f"SSID: {self.DEFAULT_SSID}\n"
                f"PASS: {self.DEFAULT_PASS}\n\n"
                "After Start AP:\n"
                "connect phone to AP\n"
                "then press Check clients"
            ),
            justify="left",
        ).pack(anchor="w", padx=6, pady=6)

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        self._append("Ready. Press Start AP.\n")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ts(self) -> str:
        return time.strftime("%H:%M:%S")

    def _append(self, msg: str) -> None:
        for line in str(msg).splitlines():
            self.text.insert("end", f"[{self._ts()}] {line}\n")
        self.text.see("end")

    def clear(self) -> None:
        self.text.delete("1.0", "end")

    def _run(self, cmd: str) -> Tuple[bool, str]:
        self._append(f"$ {cmd}")
        ok, out = self._exec_cmd(cmd)
        out = (out or "").rstrip("\n")
        if out:
            for line in out.splitlines():
                self._append(line)
        else:
            self._append("(no output)")

        if (not ok) and (not out):
            self._append("(command failed)")

        self._append("")
        return ok, out

    def _run_many(self, title: str, commands: List[str]) -> None:
        self._append(f"== {title} ==")
        for c in commands:
            self._run(c)
        self._append("OK")
        self._append("")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def start_ap(self) -> None:
        """Start AP and DHCP (dnsmasq). No internet/NAT."""
        if not messagebox.askyesno(
            "Start AP",
            "This will configure wlan0, stop connman, start hostapd and dnsmasq (NO Internet). Continue?",
        ):
            return

        # Create dnsmasq.conf via printf (avoid heredocs for compatibility with some shells/executors)
        dnsmasq_conf = (
            "mkdir -p /tmp/wifiap && "
            "printf '%s\\n' "
            "'interface=wlan0' "
            "'bind-interfaces' "
            "'except-interface=lo' "
            "'listen-address=192.168.10.1' "
            "'dhcp-range=192.168.10.50,192.168.10.150,255.255.255.0,12h' "
            "'dhcp-option=3,192.168.10.1' "
            "'dhcp-option=6,192.168.10.1' "
            "'no-resolv' "
            "> /tmp/wifiap/dnsmasq.conf"
        )

        cmds = [
            # stop anything that can interfere with AP mode
            "killall connmand 2>/dev/null || true",
            "killall wpa_supplicant 2>/dev/null || true",
            "killall udhcpc 2>/dev/null || true",
            "killall hostapd 2>/dev/null || true",
            "killall dnsmasq 2>/dev/null || true",
            # bring interface up and set static IP (required for AP routing/DHCP)
            "rfkill unblock wifi || true",
            f"ip link set {self.DEFAULT_IFACE} up",
            f"ip addr flush dev {self.DEFAULT_IFACE} || true",
            f"ip addr add {self.DEFAULT_IP} dev {self.DEFAULT_IFACE} || true",
            # start hostapd
            "hostapd -B /etc/hostapd.conf",
            # dnsmasq config + start (DHCP/DNS only for AP clients)
            dnsmasq_conf,
            "dnsmasq -C /tmp/wifiap/dnsmasq.conf",
            # quick status
            "ps | grep hostapd | grep -v grep || true",
            "ss -lunp | grep ':67\\b' || true",
        ]

        self._run_many("Start AP (NO Internet)", cmds)

        self._append("Phone: connect to AP now")
        self._append(f"SSID: {self.DEFAULT_SSID}")
        self._append(f"PASS: {self.DEFAULT_PASS}")
        self._append("")

        try:
            self.log_fn("WiFiAP: Start AP")
        except Exception:
            pass

    def stop_ap(self) -> None:
        if not messagebox.askyesno("Stop AP", "Stop hostapd/dnsmasq and clear wlan0 IP?"):
            return

        cmds = [
            "killall hostapd 2>/dev/null || true",
            "killall dnsmasq 2>/dev/null || true",
            f"ip addr flush dev {self.DEFAULT_IFACE} || true",
        ]
        self._run_many("Stop AP", cmds)
        try:
            self.log_fn("WiFiAP: Stop AP")
        except Exception:
            pass

    def check_clients(self) -> None:
        cmds = [
            f"iw dev {self.DEFAULT_IFACE} station dump 2>/dev/null || true",
        ]
        self._run_many("Clients (iw station dump)", cmds)
        try:
            self.log_fn("WiFiAP: Check clients")
        except Exception:
            pass

    def status(self) -> None:
        cmds = [
            f"ip -brief link show dev {self.DEFAULT_IFACE} 2>/dev/null || true",
            f"ip -brief addr show dev {self.DEFAULT_IFACE} 2>/dev/null || true",
            "ps | grep -E 'hostapd|dnsmasq|connmand' | grep -v grep || true",
            "ss -ltnup | grep ':53\\b' || true",
            "ss -lunp | grep ':67\\b' || true",
        ]
        self._run_many("Status", cmds)
