# -*- coding: utf-8 -*-

import re
import time
import tkinter as tk
from tkinter import ttk


class TestEthernetTab(ttk.Frame):
    """
    Ethernet / Internet quick check (DHCP + internet reachability).

    This tab intentionally keeps things simple:
      - Uses real CLI commands (same as you tested manually).
      - Focuses on eth0 (wired) by default.
      - Optional PASS/FAIL where it is easy & reliable.

    Expected executor behavior:
      - may return a string
      - may return (ok: bool, output: str)
    """

    IFACE_DEFAULT = "eth0"

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)

        self.iface_var = tk.StringVar(value=self.IFACE_DEFAULT)

        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Internet (Ethernet)").pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="Interface (wired):").pack(anchor="w")
        ttk.Entry(left, textvariable=self.iface_var, width=18).pack(anchor="w", pady=(0, 8))

        ttk.Separator(left).pack(fill="x", pady=8)

        ttk.Button(left, text="Run ALL (SAFE)", width=22, command=self.run_all).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=8)

        ttk.Button(left, text="List interfaces", width=22, command=self.cmd_list_ifaces).pack(anchor="w", pady=3)
        ttk.Button(left, text="Link state", width=22, command=self.cmd_link_state).pack(anchor="w", pady=3)
        ttk.Button(left, text="IP (brief)", width=22, command=self.cmd_ip_brief).pack(anchor="w", pady=3)
        ttk.Button(left, text="IP (full)", width=22, command=self.cmd_ip_full).pack(anchor="w", pady=3)
        ttk.Button(left, text="Default route", width=22, command=self.cmd_default_route).pack(anchor="w", pady=3)
        ttk.Button(left, text="Ping 1.1.1.1", width=22, command=self.cmd_ping_ip).pack(anchor="w", pady=3)
        ttk.Button(left, text="DNS + ping google.com", width=22, command=self.cmd_dns_ping).pack(anchor="w", pady=3)

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    # ---------------- executor adapter ----------------
    def _exec_cmd(self, cmd: str):
        """
        Returns (ok: bool, out: str)
        - If executor returns (ok, out), use it.
        - If executor returns plain string, assume ok=True.
        - If executor raises exception, ok=False.
        """
        try:
            res = self.exec(cmd) if callable(self.exec) else self._exec_obj(cmd)
        except Exception as e:
            return False, f"ERROR: {e}"

        # Normalize
        if isinstance(res, tuple) and len(res) == 2:
            ok, out = res
            return bool(ok), "" if out is None else str(out)
        return True, "" if res is None else str(res)

    def _exec_obj(self, cmd: str):
        for attr in ("run", "exec", "execute", "shell"):
            if hasattr(self.exec, attr):
                return getattr(self.exec, attr)(cmd)
        raise TypeError("Executor does not support command execution")

    # ---------------- helpers ----------------
    def _ts(self):
        return time.strftime("%H:%M:%S")

    def _append(self, msg: str):
        self.text.insert("end", f"[{self._ts()}] {msg}\n")
        self.text.see("end")

    def _run(self, cmd: str):
        self._append(f"$ {cmd}")
        ok, out = self._exec_cmd(cmd)
        out = (out or "").rstrip("\n")
        if out:
            for line in out.splitlines():
                self._append(line)
        if not ok and not out:
            self._append("(command failed)")
        return ok, out

    def _iface(self) -> str:
        v = (self.iface_var.get() or "").strip()
        return v or self.IFACE_DEFAULT

    # ---------------- PASS/FAIL helpers ----------------
    def _passfail(self, passed: bool, label: str, details: str = ""):
        if passed:
            self._append(f"PASS: {label}")
        else:
            self._append(f"FAIL: {label}")
        if details:
            self._append(f"  {details}")

    def _parse_packet_loss_zero(self, ping_out: str) -> bool:
        # matches "0% packet loss"
        return bool(re.search(r"\b0%\s+packet\s+loss\b", ping_out))

    def _parse_has_ipv4(self, ip_out: str) -> bool:
        # simple: look for "inet X.X.X.X/"
        return bool(re.search(r"\binet\s+\d+\.\d+\.\d+\.\d+/\d+", ip_out))

    def _parse_default_via(self, route_out: str):
        # returns (gw, dev) or ("","")
        for line in route_out.splitlines():
            line = line.strip()
            if line.startswith("default "):
                parts = line.split()
                gw = ""
                dev = ""
                if "via" in parts:
                    i = parts.index("via")
                    if i + 1 < len(parts):
                        gw = parts[i + 1]
                if "dev" in parts:
                    i = parts.index("dev")
                    if i + 1 < len(parts):
                        dev = parts[i + 1]
                return gw, dev
        return "", ""

    # ---------------- buttons (commands) ----------------
    def cmd_list_ifaces(self):
        self._append("== Interfaces ==")
        self._run("ls -1 /sys/class/net")
        self._append("")

    def cmd_link_state(self):
        iface = self._iface()
        self._append(f"== Link state ({iface}) ==")
        ok1, carrier = self._run(f"cat /sys/class/net/{iface}/carrier")
        ok2, oper = self._run(f"cat /sys/class/net/{iface}/operstate")

        carrier_val = (carrier or "").strip()
        oper_val = (oper or "").strip()

        # PASS/FAIL (easy & reliable)
        self._passfail(ok1 and carrier_val == "1", "carrier == 1 (link up)", f"carrier={carrier_val or 'n/a'}")
        self._passfail(ok2 and oper_val == "up", "operstate == up", f"operstate={oper_val or 'n/a'}")
        self._append("")

    def cmd_ip_brief(self):
        iface = self._iface()
        self._append(f"== IP (brief) ({iface}) ==")
        self._run(f"ip -brief addr show dev {iface}")
        # без PASS/FAIL — формат не для парсинга
        self._append("")

    def cmd_ip_full(self):
        iface = self._iface()
        self._append(f"== IP (full) ({iface}) ==")
        ok, out = self._run(f"ip addr show dev {iface}")
        self._passfail(ok and self._parse_has_ipv4(out), "IPv4 address present (DHCP expected)")
        self._append("")

    def cmd_default_route(self):
        self._append("== Default route ==")
        ok, out = self._run("ip route show default")
        gw, dev = self._parse_default_via(out if ok else "")
        self._passfail(bool(gw), "default gateway present", f"gw={gw or 'n/a'} dev={dev or 'n/a'}")
        self._append("")

    def cmd_ping_ip(self):
        self._append("== Ping public IP (no DNS) ==")
        ok, out = self._run("ping -c 3 1.1.1.1")
        self._passfail(ok and self._parse_packet_loss_zero(out), "ping 1.1.1.1 (0% loss)")
        self._append("")

    def cmd_dns_ping(self):
        self._append("== DNS config ==")
        self._run("cat /etc/resolv.conf")
        self._append("== Ping hostname (DNS test) ==")
        ok, out = self._run("ping -c 1 google.com")
        self._passfail(ok and self._parse_packet_loss_zero(out), "ping google.com (DNS works)")
        self._append("")

    # ---------------- run all ----------------
    def run_all(self):
        iface = self._iface()
        self._append(f"== Internet check ALL (SAFE) [{iface}] ==")
        self.cmd_list_ifaces()
        self.cmd_link_state()
        self.cmd_ip_brief()
        self.cmd_default_route()
        self.cmd_ping_ip()
        self.cmd_dns_ping()
        self._append("DONE\n")
