# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk, messagebox


class TestWifiapTab(ttk.Frame):
    """Wi‑Fi AP tab (Access Point) for ECB10-135A5M5M-I.

    What it does:
      - Start AP on wlan0 using /etc/hostapd.conf
      - Provide DHCP to clients via dnsmasq (DHCP-only: port=0)
      - Optionally enable Internet sharing (NAT) from wlan0 to eth0

    Design rules (same as our working tabs):
      - No threads
      - Executor compatibility: callable OR object with run/exec/execute/shell
      - Executor may return str OR (ok: bool, out: str)

    Phone defaults:
      - SSID: EBYTE
      - PASS: 12345678
      - AP IP: 192.168.10.1/24
    """

    DEFAULT_IFACE = "wlan0"
    DEFAULT_IP_CIDR = "192.168.10.1/24"
    DEFAULT_IP = "192.168.10.1"
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
    def _exec_cmd(self, cmd: str):
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
    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Wi‑Fi AP").pack(anchor="w", pady=(0, 8))

        ttk.Button(left, text="Start AP (NO Internet)", width=24, command=self.start_ap).pack(anchor="w", pady=3)
        ttk.Button(left, text="Stop AP", width=24, command=self.stop_ap).pack(anchor="w", pady=3)
        ttk.Button(left, text="Check clients", width=24, command=self.check_clients).pack(anchor="w", pady=3)
        ttk.Button(left, text="Status", width=24, command=self.status).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="Enable Internet (NAT)", width=24, command=self.enable_internet).pack(anchor="w", pady=3)
        ttk.Button(left, text="Disable Internet", width=24, command=self.disable_internet).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="Clear", width=24, command=self.clear).pack(anchor="w", pady=3)

        hint = ttk.LabelFrame(left, text="Phone")
        hint.pack(fill="x", pady=(10, 0))
        ttk.Label(
            hint,
            text=(
                f"SSID: {self.DEFAULT_SSID}\n"
                f"PASS: {self.DEFAULT_PASS}\n\n"
                "1) Start AP\n"
                "2) Connect phone\n"
                "3) Check clients\n\n"
                "Optional: Enable Internet (NAT)\n"
                "Tip: if websites don't open, reconnect Wi‑Fi"
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

        self._append("Ready.\n")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ts(self):
        return time.strftime("%H:%M:%S")

    def _append(self, msg: str):
        for line in str(msg).splitlines():
            self.text.insert("end", f"[{self._ts()}] {line}\n")
        self.text.see("end")

    def clear(self):
        self.text.delete("1.0", "end")

    def _run(self, cmd: str):
        self._append(f"$ {cmd}")
        ok, out = self._exec_cmd(cmd)

        out = (out or "").rstrip("\n")
        if out:
            for line in out.splitlines():
                self._append(line)
        else:
            self._append("(no output)")

        if not ok and not out:
            self._append("(command failed)")

        self._append("")
        return ok, out

    def _run_many(self, title: str, commands):
        self._append(f"== {title} ==")
        for c in commands:
            self._run(c)
        self._append("OK")
        self._append("")

    # ------------------------------------------------------------------
    # AP start/stop
    # ------------------------------------------------------------------
    def _dnsmasq_conf_dhcp_only(self) -> str:
        """Create dnsmasq.conf for DHCP only (no DNS service => avoids port 53 conflicts)."""
        # NOTE: We intentionally avoid heredocs; use printf for compatibility.
        return (
            "mkdir -p /tmp/wifiap && "
            "printf '%s\\n' "
            f"'interface={self.DEFAULT_IFACE}' "
            "'bind-interfaces' "
            "'except-interface=lo' "
            f"'listen-address={self.DEFAULT_IP}' "
            "'dhcp-range=192.168.10.50,192.168.10.150,255.255.255.0,12h' "
            f"'dhcp-option=3,{self.DEFAULT_IP}' "
            "'dhcp-option=6,1.1.1.1,8.8.8.8' "
            "'port=0' "
            "> /tmp/wifiap/dnsmasq.conf"
        )

    def start_ap(self):
        if not messagebox.askyesno(
            "Start AP",
            "This will stop Wi‑Fi client services, configure wlan0 and start hostapd + dnsmasq (NO Internet). Continue?",
        ):
            return

        cmds = [
            # stop anything that can interfere with AP mode
            "killall connmand 2>/dev/null || true",
            "killall wpa_supplicant 2>/dev/null || true",
            "killall udhcpc 2>/dev/null || true",
            "killall hostapd 2>/dev/null || true",
            "killall dnsmasq 2>/dev/null || true",
            "killall avahi-autoipd 2>/dev/null || true",
            "rfkill unblock wifi || true",
            f"ip link set {self.DEFAULT_IFACE} up",
            # clear addresses/routes that can break later NAT
            f"ip addr flush dev {self.DEFAULT_IFACE} || true",
            f"ip route del default dev {self.DEFAULT_IFACE} 2>/dev/null || true",
            f"ip addr add {self.DEFAULT_IP_CIDR} dev {self.DEFAULT_IFACE} || true",
            "ip addr del 169.254.0.0/16 dev wlan0 2>/dev/null || true",
            # start hostapd
            "hostapd -B /etc/hostapd.conf",
            # start DHCP
            self._dnsmasq_conf_dhcp_only(),
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

    def stop_ap(self):
        if not messagebox.askyesno("Stop AP", "Stop hostapd/dnsmasq and clear wlan0 IP?"):
            return

        cmds = [
            "killall hostapd 2>/dev/null || true",
            "killall dnsmasq 2>/dev/null || true",
            f"ip addr flush dev {self.DEFAULT_IFACE} || true",
            f"ip route del default dev {self.DEFAULT_IFACE} 2>/dev/null || true",
        ]
        self._run_many("Stop AP", cmds)

        try:
            self.log_fn("WiFiAP: Stop AP")
        except Exception:
            pass

    def check_clients(self):
        cmds = [
            f"iw dev {self.DEFAULT_IFACE} station dump 2>/dev/null || true",
        ]
        self._run_many("Clients (iw station dump)", cmds)

        try:
            self.log_fn("WiFiAP: Check clients")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internet sharing
    # ------------------------------------------------------------------
    def enable_internet(self):
        if not messagebox.askyesno(
            "Enable Internet (NAT)",
            "This will enable IPv4 forwarding and NAT from wlan0 -> eth0. Continue?",
        ):
            return

        cmds = [
            # bring ethernet up and get IP (if already up, it's harmless)
            "ip link set eth0 up 2>/dev/null || true",
            "udhcpc -i eth0 2>/dev/null || true",
            # make sure default route is not accidentally on wlan0 (169.254)
            "ip route del default dev wlan0 2>/dev/null || true",
            # kernel forwarding
            "sysctl -w net.ipv4.ip_forward=1",
            # some systems drop forwarded traffic due to rp_filter
            "sysctl -w net.ipv4.conf.all.rp_filter=0",
            "sysctl -w net.ipv4.conf.default.rp_filter=0",
            "sysctl -w net.ipv4.conf.wlan0.rp_filter=0",
            "sysctl -w net.ipv4.conf.eth0.rp_filter=0",
            # NAT rules
            "iptables -F",
            "iptables -t nat -F",
            "iptables -X 2>/dev/null || true",
            "iptables -P FORWARD ACCEPT",
            "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
            "iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT",
            "iptables -A FORWARD -i eth0 -o wlan0 -m state --state ESTABLISHED,RELATED -j ACCEPT",
            # show status
            "ip route",
            "iptables -t nat -L -v -n",
            "iptables -L FORWARD -v -n",
        ]

        self._run_many("Enable Internet (NAT wlan0 -> eth0)", cmds)
        self._append("Phone: if websites don't open, reconnect Wi‑Fi once.")
        self._append("")

        try:
            self.log_fn("WiFiAP: Enable Internet")
        except Exception:
            pass

    def disable_internet(self):
        if not messagebox.askyesno(
            "Disable Internet",
            "This will flush iptables NAT/FORWARD rules (AP stays ON). Continue?",
        ):
            return

        cmds = [
            "iptables -F",
            "iptables -t nat -F",
            "iptables -X 2>/dev/null || true",
            "sysctl -w net.ipv4.ip_forward=0",
            "iptables -t nat -L -v -n",
            "iptables -L FORWARD -v -n",
        ]
        self._run_many("Disable Internet", cmds)

        try:
            self.log_fn("WiFiAP: Disable Internet")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def status(self):
        cmds = [
            f"ip -brief link show dev {self.DEFAULT_IFACE} 2>/dev/null || true",
            f"ip -brief addr show dev {self.DEFAULT_IFACE} 2>/dev/null || true",
            "ip route 2>/dev/null || true",
            "ps | grep -E 'hostapd|dnsmasq|connmand|avahi-autoipd' | grep -v grep || true",
            "ss -lunp | grep ':67\\b' || true",
            "iptables -t nat -L -v -n 2>/dev/null || true",
        ]
        self._run_many("Status", cmds)
