# -*- coding: utf-8 -*-

import re
import time
import tkinter as tk
from tkinter import ttk, messagebox


class TestWifiTab(ttk.Frame):
    """Wi‑Fi (Client/Radio) — diagnostics tab.

    Goal (no connect):
      - Confirm Wi‑Fi hardware/driver is alive.
      - Show rfkill status, wlan interface state, driver presence, scan results (SSID list).

    Safety levels:
      - SAFE: read-only commands (iw dev/link/scan, rfkill list, ip show).
      - Semi-risky: unblock rfkill, ip link set up (does NOT connect).

    Executor compatibility:
      - executor may return string OR (ok: bool, output: str)
      - executor may be callable OR object with run/exec/execute/shell
    """

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()
        self._refresh_if_list()

    # ------------------------------------------------------------------
    # Executor adapter
    # ------------------------------------------------------------------
    def _exec_cmd(self, cmd: str):
        """Unified executor adapter.

        Returns:
            (ok: bool, out: str)
        """
        try:
            # callable executor
            if callable(self.exec):
                res = self.exec(cmd)
            else:
                # object executor
                res = None
                for attr in ("run", "exec", "execute", "shell"):
                    if hasattr(self.exec, attr):
                        res = getattr(self.exec, attr)(cmd)
                        break
                else:
                    raise TypeError("Executor does not support command execution")
        except Exception as e:
            return False, f"ERROR: {e}"

        # Normalize result
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

        ttk.Label(left, text="Wi‑Fi (C/R)").pack(anchor="w", pady=(0, 8))

        # Interface selector
        ttk.Label(left, text="Interface:").pack(anchor="w")
        self.if_var = tk.StringVar(value="wlan0")
        self.if_combo = ttk.Combobox(left, textvariable=self.if_var, width=20, state="readonly")
        self.if_combo.pack(anchor="w", pady=(0, 8))
        ttk.Button(left, text="Refresh list", width=22, command=self._refresh_if_list).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=8)

        # SAFE buttons
        ttk.Button(left, text="Quick (SAFE)", width=22, command=self.run_safe).pack(anchor="w", pady=3)
        ttk.Button(left, text="rfkill status", width=22, command=self.run_rfkill).pack(anchor="w", pady=3)
        ttk.Button(left, text="iw dev", width=22, command=self.run_iw_dev).pack(anchor="w", pady=3)
        ttk.Button(left, text="Scan SSIDs (SAFE)", width=22, command=self.run_scan).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=8)

        # Semi-risky buttons (no connect)
        ttk.Button(left, text="Unblock Wi‑Fi (confirm)", width=22, command=self.unblock_wifi).pack(anchor="w", pady=3)
        ttk.Button(left, text="Bring UP (confirm)", width=22, command=self.bring_up).pack(anchor="w", pady=3)

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ts(self):
        return time.strftime("%H:%M:%S")

    def _append(self, msg: str):
        self.text.insert("end", f"[{self._ts()}] {msg}\n")
        self.text.see("end")

    def _run(self, cmd: str):
        """Execute command and print output to text widget."""
        self._append(f"$ {cmd}")
        ok, out = self._exec_cmd(cmd)

        out = (out or "").rstrip("\n")
        if out:
            for line in out.splitlines():
                self._append(line)

        if not ok and not out:
            self._append("(command failed)")

        return ok, out

    def _get_if(self) -> str:
        v = (self.if_var.get() or "").strip()
        return v if v else "wlan0"

    def _refresh_if_list(self):
        ok, out = self._run("ls -1 /sys/class/net 2>/dev/null")
        ifs = [x.strip() for x in (out or "").splitlines() if x.strip() and x.strip() != "lo"]
        # prefer wlan*
        wlan_ifs = [x for x in ifs if x.startswith("wlan")]
        if not wlan_ifs:
            wlan_ifs = ["wlan0"]
        self.if_combo["values"] = wlan_ifs
        cur = self._get_if()
        if cur not in wlan_ifs:
            self.if_var.set(wlan_ifs[0])

    # ------------------------------------------------------------------
    # SAFE tests
    # ------------------------------------------------------------------
    def run_safe(self):
        iface = self._get_if()
        self._append(f"== Wi‑Fi quick (SAFE) ({iface}) ==")

        self._append("== Interface status ==")
        self._run(f"ip -brief link show dev {iface} 2>/dev/null || true")
        self._run(f"ip -brief addr show dev {iface} 2>/dev/null || true")

        self._append("== rfkill ==")
        self._run("rfkill list 2>/dev/null || true")

        self._append("== iw link ==")
        self._run(f"iw dev {iface} link 2>/dev/null || true")

        self._append("OK")
        self._append("")

    def run_rfkill(self):
        self._append("== rfkill status ==")
        self._run("rfkill list 2>/dev/null || true")
        self._append("OK")
        self._append("")

    def run_iw_dev(self):
        self._append("== iw dev ==")
        self._run("iw dev 2>/dev/null || true")
        self._append("OK")
        self._append("")

    def run_scan(self):
        """Scan for nearby SSIDs (does not connect)."""
        iface = self._get_if()
        self._append(f"== Scan SSIDs (SAFE) ({iface}) ==")

        ok, out = self._run(f"iw dev {iface} scan 2>/dev/null || true")

        ssids = []
        if out:
            # SSID lines may be empty (hidden SSID) => keep as "<hidden>"
            for m in re.finditer(r"^\s*SSID:\s*(.*)$", out, flags=re.MULTILINE):
                s = (m.group(1) or "").strip()
                ssids.append(s if s else "<hidden>")

        uniq = []
        seen = set()
        for s in ssids:
            if s not in seen:
                uniq.append(s)
                seen.add(s)

        # PASS/FAIL rule: at least one BSS/SSID found
        if uniq:
            self._append(f"PASS: networks found: {len(uniq)}")
            self._append("SSIDs:")
            for s in uniq[:50]:
                self._append(f"- {s}")
            if len(uniq) > 50:
                self._append(f"... ({len(uniq) - 50} more)")
        else:
            # If command succeeded but no SSIDs => could still be blocked/regdom/antenna/etc.
            # Keep it simple per request.
            self._append("FAIL: no SSIDs found")
            self._append("Hint: check rfkill (soft blocked) and make sure interface is UP.")

        self._append("OK")
        self._append("")

    # ------------------------------------------------------------------
    # Semi-risky (no connect)
    # ------------------------------------------------------------------
    def unblock_wifi(self):
        if not messagebox.askyesno(
            "Unblock Wi‑Fi",
            "This will run: rfkill unblock wifi\n\n"
            "It does NOT connect to any network.\n\nProceed?",
        ):
            return
        self._append("== Unblock Wi‑Fi ==")
        self._run("rfkill unblock wifi 2>/dev/null || true")
        self._run("rfkill list 2>/dev/null || true")
        self._append("DONE")
        self._append("")

    def bring_up(self):
        iface = self._get_if()
        if not messagebox.askyesno(
            "Bring interface UP",
            f"This will run: ip link set {iface} up\n\n"
            "It does NOT connect to any network.\n\nProceed?",
        ):
            return
        self._append(f"== Bring UP ({iface}) ==")
        self._run(f"ip link set {iface} up 2>/dev/null || true")
        self._run(f"ip -brief link show dev {iface} 2>/dev/null || true")
        self._append("DONE")
        self._append("")
