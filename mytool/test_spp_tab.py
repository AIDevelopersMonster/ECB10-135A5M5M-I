# -*- coding: utf-8 -*-
import re
import time
import tkinter as tk
from tkinter import ttk


class TestSppTab(ttk.Frame):
    """
    Bluetooth / SPP (RFCOMM) test tab.

    Current-image goals:
      - Prove Bluetooth stack is alive (hci0, firmware, dmesg).
      - Provide pairing proof helpers (paired-devices, info, trust).
      - Check SPP/RFCOMM kernel support (EXPECTED FAIL on current image):
          rfcomm -> "Protocol not supported"

    Privacy:
      - The log output masks MAC addresses (AA:BB:CC:DD:EE:FF -> AA:BB:CC:XX:XX:XX).
      - Commands are executed with real MAC (if provided), only the UI log is masked.

    Executor contract (flexible):
      - executor may return:
          * str
          * (ok: bool, output: str)
      - executor may be:
          * callable(cmd) -> result
          * object with .run/.exec/.execute/.shell(cmd) -> result
    """

    MAC_RE = re.compile(r"\b([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    # -------------------- executor adapter --------------------
    def _exec_cmd(self, cmd: str):
        """
        Run a command through the provided executor.

        Returns:
            (ok: bool, out: str)
        """
        try:
            if callable(self.exec):
                res = self.exec(cmd)
            else:
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

    # -------------------- privacy helpers --------------------
    @classmethod
    def _mask_mac(cls, mac: str) -> str:
        parts = mac.split(":")
        if len(parts) != 6:
            return mac
        return ":".join(parts[:3] + ["XX", "XX", "XX"])

    @classmethod
    def _mask_macs_in_text(cls, s: str) -> str:
        def repl(m):
            return cls._mask_mac(m.group(0))
        return cls.MAC_RE.sub(repl, s)

    # -------------------- UI --------------------
    def _build_ui(self):
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        left = ttk.Frame(outer, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Bluetooth / SPP", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 8))

        # Stage 1 — Smoke
        ttk.Label(left, text="Stage 1: Smoke", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Button(left, text="BT Info (SAFE)", width=22, command=self.run_bt_info).pack(anchor="w", pady=2)
        ttk.Button(left, text="BT Status (show)", width=22, command=self.run_bt_show).pack(anchor="w", pady=2)

        row = ttk.Frame(left)
        row.pack(anchor="w", pady=(6, 2), fill="x")
        ttk.Button(row, text="Power ON", width=10, command=lambda: self._run("bluetoothctl power on")).pack(side="left")
        ttk.Button(row, text="Power OFF", width=10, command=lambda: self._run("bluetoothctl power off")).pack(
            side="left", padx=(6, 0)
        )

        ttk.Separator(left).pack(fill="x", pady=10)

        # Stage 2 — Pairing proof
        ttk.Label(left, text="Stage 2: Pairing proof", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Button(left, text="Paired devices", width=22, command=self.run_paired_devices).pack(anchor="w", pady=2)

        ttk.Label(left, text="Phone MAC (optional):").pack(anchor="w", pady=(8, 0))
        self.mac_var = tk.StringVar(value="")
        ttk.Entry(left, textvariable=self.mac_var, width=24).pack(anchor="w", pady=(2, 6))

        ttk.Button(left, text="Device info (MAC)", width=22, command=self.run_device_info).pack(anchor="w", pady=2)
        ttk.Button(left, text="Trust device (MAC)", width=22, command=self.run_trust_device).pack(anchor="w", pady=2)

        self.demo_try_connect = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Demo: try connect (safe)", variable=self.demo_try_connect).pack(anchor="w", pady=(6, 0))
        ttk.Button(left, text="Demo: pairing proof", width=22, command=self.run_demo_pairing_proof).pack(anchor="w", pady=2)

        ttk.Button(left, text="Pairing notes", width=22, command=self.print_pairing_notes).pack(anchor="w", pady=2)

        ttk.Separator(left).pack(fill="x", pady=10)

        # Stage 3 — SPP/RFCOMM
        ttk.Label(left, text="Stage 3: SPP / RFCOMM", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Button(left, text="SPP Check", width=22, command=self.run_spp_check).pack(anchor="w", pady=2)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="Run all (SAFE)", width=22, command=self.run_all_safe).pack(anchor="w", pady=2)
        ttk.Button(left, text="Clear log", width=22, command=self.clear_log).pack(anchor="w", pady=2)

        # Right: log
        body = ttk.Frame(outer, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    # -------------------- log helpers --------------------
    def _ts(self):
        return time.strftime("%H:%M:%S")

    def _append(self, msg: str):
        msg = self._mask_macs_in_text(msg)
        self.text.insert("end", f"[{self._ts()}] {msg}\n")
        self.text.see("end")

    def clear_log(self):
        self.text.delete("1.0", "end")

    def _run(self, cmd: str):
        # Mask MACs in displayed command only
        display_cmd = self._mask_macs_in_text(cmd)
        self._append(f"$ {display_cmd}")

        ok, out = self._exec_cmd(cmd)

        out = (out or "").rstrip("\n")
        if out:
            out = self._mask_macs_in_text(out)
            for line in out.splitlines():
                self._append(line)

        if not ok and not out:
            self._append("(command failed)")

        return ok, out

    def _headline(self, title: str):
        self._append(f"== {title} ==")

    # -------------------- Stage 1 --------------------
    def run_bt_info(self):
        self._headline("Bluetooth info (SAFE)")
        self._run("ls /sys/class/bluetooth")
        self._run("hciconfig -a hci0")
        self._run("ls -1 /lib/firmware/brcm | grep -i bcm4343 || true")
        self._run("dmesg | grep -i bluetooth | tail -n 25")
        self._append("")

    def run_bt_show(self):
        self._headline("bluetoothctl show")
        self._run("bluetoothctl show")
        self._append("")

    # -------------------- Stage 2 --------------------
    def run_paired_devices(self):
        self._headline("Paired devices")
        self._run("bluetoothctl paired-devices")
        self._append("")

    def _get_mac(self):
        mac = (self.mac_var.get() or "").strip()
        return mac or None

    def run_device_info(self):
        mac = self._get_mac()
        if not mac:
            self._append("NOTE: Phone MAC is empty. Paste MAC and retry (e.g. XX:XX:XX:XX:XX:XX).")
            self._append("")
            return
        self._headline("Device info (masked in log)")
        self._run(f"bluetoothctl info {mac}")
        self._append("")

    def run_trust_device(self):
        mac = self._get_mac()
        if not mac:
            self._append("NOTE: Phone MAC is empty. Paste MAC and retry (e.g. XX:XX:XX:XX:XX:XX).")
            self._append("")
            return
        self._headline("Trust device (masked in log)")
        self._run(f"bluetoothctl trust {mac}")
        self._append("")

    def run_demo_pairing_proof(self):
        """
        One-button demo for video:
          - show paired devices
          - show info for provided MAC
          - optionally try connect (may connect briefly then disconnect)
          - explain expected disconnect without SPP/OBEX servers
        """
        mac = self._get_mac()
        self._headline("Demo: pairing proof (SAFE)")

        self._append("Step 1: paired-devices")
        self._run("bluetoothctl paired-devices")

        if mac:
            self._append("Step 2: info <MAC> (shows Paired/Trusted)")
            self._run(f"bluetoothctl info {mac}")

            if self.demo_try_connect.get():
                self._append("Step 3: connect <MAC> (may briefly connect then disconnect)")
                self._run(f"bluetoothctl connect {mac} || true")
                self._append("Step 4: info <MAC> again (Connected may become 'no' afterwards)")
                self._run(f"bluetoothctl info {mac}")
        else:
            self._append("NOTE: Phone MAC is empty, skipping info/connect steps.")

        self._append("")
        self._append("Interpretation:")
        self._append("- Paired/Trusted can be YES even if Connected becomes NO.")
        self._append("- Phone often disconnects if board has no active profile/server (SPP/RFCOMM or OBEX).")
        self._append("- We continue after kernel rebuild, because SPP requires RFCOMM support in kernel.")
        self._append("")

    def print_pairing_notes(self):
        self._headline("Pairing notes (manual, proven)")
        self._append("On board (bluetoothctl):")
        self._append("  power on")
        self._append("  system-alias EBYTE-13x")
        self._append("  discoverable-timeout 0")
        self._append("  pairable-timeout 0")
        self._append("  discoverable on")
        self._append("  pairable on")
        self._append("  agent on")
        self._append("  default-agent")
        self._append("On phone: start pairing with 'EBYTE-13x'")
        self._append("IMPORTANT: when prompted: Confirm passkey XXXXX (yes/no): type ONLY 'yes' (NOT digits)")
        self._append("After pairing: trust <PHONE_MAC> ; paired-devices")
        self._append("NOTE: Phone may connect briefly then disconnect if no profile is available (SPP/OBEX missing).")
        self._append("")

    # -------------------- Stage 3 --------------------
    def run_spp_check(self):
        self._headline("SPP / RFCOMM check")
        ok, out = self._run("rfcomm release 0")
        out = out or ""
        if "Protocol not supported" in out:
            self._append("EXPECTED FAIL: SPP/RFCOMM not supported by current kernel (Protocol not supported).")
            self._append("Next: return after kernel rebuild (enable CONFIG_BT_RFCOMM + CONFIG_BT_RFCOMM_TTY).")
        elif ok:
            self._append("PASS: RFCOMM control socket available (SPP likely supported).")
        else:
            self._append("FAIL: Unexpected rfcomm error (see output above).")
        self._append("")

    # -------------------- run all --------------------
    def run_all_safe(self):
        self._headline("Run all (SAFE)")
        self.run_bt_info()
        self.run_bt_show()
        self.run_paired_devices()
        self.run_spp_check()
        self._append("Summary:")
        self._append("- Bluetooth stack OK if hci0 exists and dmesg shows BCM/AP6212 + firmware.")
        self._append("- Pairing proof: paired-devices list (and optional info/connect demo).")
        self._append("- SPP is EXPECTED FAIL on current image (Protocol not supported).")
        self._append("")
