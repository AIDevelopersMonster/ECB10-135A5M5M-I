# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk


class TestOtgTab(ttk.Frame):
    """
    USB OTG test tab (auto-detect current firmware state).

    What it can report:
    - OTG Host ACTIVE (mass storage via dwc2, /dev/sdX1 present)
    - OTG Peripheral/Gadget ready (UDC present)  [rare in your current image]
    - OTG present but no active role (info)

    NOTE:
    Your board does not support automatic OTG role switching. Role is set by device tree (dr_mode).
    """

    DOT_GRAY = "#9e9e9e"
    DOT_GREEN = "#2e7d32"
    DOT_YELLOW = "#f9a825"
    DOT_RED = "#c62828"

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)

        self._busy = False

        self.mount_point = "/mnt/otg"
        self.test_file = "otg_test.txt"
        self.test_payload = "OTG HOST OK"

        self.detected_dev = None
        self.detected_fs_ok = False
        self.otg_host_active = False

        self._build_ui()
        self._set_dot("unknown")
        self._update_buttons()

    # ---------------- UI ----------------

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="USB OTG", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            left,
            text="Detect current OTG state.\n"
                 "If OTG Host is active (dwc2 + /dev/sdX1),\n"
                 "you can run R/W test.",
            wraplength=260,
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        ports_box = ttk.Labelframe(left, text="Status")
        ports_box.pack(fill="x", pady=(0, 10))

        row = ttk.Frame(ports_box)
        row.pack(fill="x", pady=2)

        self.dot = tk.Canvas(row, width=16, height=16, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 8))
        self._dot_oval = self.dot.create_oval(2, 2, 14, 14, fill=self.DOT_GRAY, outline="")

        self.status_var = tk.StringVar(value="UNKNOWN")
        ttk.Label(row, textvariable=self.status_var).pack(side="left")

        actions = ttk.Labelframe(left, text="Actions")
        actions.pack(fill="x", pady=(0, 10))

        self.btn_detect = ttk.Button(actions, text="Detect OTG", command=self.detect_otg, width=22)
        self.btn_detect.pack(anchor="w", pady=4)

        self.btn_test = ttk.Button(actions, text="Run OTG R/W test", command=self.run_test, width=22)
        self.btn_test.pack(anchor="w", pady=4)

        self.btn_cleanup = ttk.Button(actions, text="Umount /mnt/otg", command=self.cleanup, width=22)
        self.btn_cleanup.pack(anchor="w", pady=4)

        self.info_var = tk.StringVar(value="Ready.")
        ttk.Label(left, textvariable=self.info_var, wraplength=260, justify="left").pack(anchor="w", pady=(8, 0))

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        self._append("== OTG ==")
        self._append("Insert device into Type-C OTG (host) → Detect → Run R/W test.")
        self._append("")

    def _append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {msg}\n")
        self.text.see("end")

    def _require_connected(self) -> bool:
        if not self.exec.is_connected():
            self._append("Not connected.")
            self.info_var.set("Not connected.")
            return False
        return True

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.btn_detect.config(state=state)
        self.btn_cleanup.config(state=state)
        self._update_buttons()

    def _update_buttons(self):
        if self._busy:
            self.btn_test.config(state="disabled")
            return
        self.btn_test.config(state=("normal" if (self.otg_host_active and self.detected_dev and self.detected_fs_ok) else "disabled"))

    def _set_dot(self, state: str):
        # state: unknown / pass / warn / fail
        if state == "pass":
            color = self.DOT_GREEN
            self.status_var.set("PASS")
        elif state == "warn":
            color = self.DOT_YELLOW
            self.status_var.set("WARN")
        elif state == "fail":
            color = self.DOT_RED
            self.status_var.set("FAIL")
        else:
            color = self.DOT_GRAY
            self.status_var.set("UNKNOWN")
        self.dot.itemconfig(self._dot_oval, fill=color)

    # ---------------- helpers ----------------

    @staticmethod
    def _looks_like_error(text: str) -> bool:
        t = (text or "").lower()
        bad = [
            "not found",
            "no such file",
            "can't open",
            "failed",
            "invalid argument",
            "permission denied",
            "unknown filesystem",
        ]
        return any(x in t for x in bad)

    def _cmd(self, cmd: str, timeout: float = 8.0):
        ok, out = self.exec.run(cmd, timeout_s=timeout)
        out = out or ""
        if self._looks_like_error(out):
            ok = False
        return ok, out.strip()

    # ---------------- actions ----------------

    def cleanup(self):
        if not self._require_connected():
            return
        self._append("== OTG: cleanup ==")
        self._cmd(f"sync; mount | grep -q ' {self.mount_point} ' && umount {self.mount_point}; sync", timeout=12.0)
        self._append(f"$ sync; umount {self.mount_point} (if mounted); sync")
        self._append("OK")
        self._append("")
        self.info_var.set("Cleanup done (if /mnt/otg was mounted).")

    def detect_otg(self):
        """
        Detect OTG status:
        - DWC2 controller is present (dmesg)
        - OTG Host ACTIVE if we see "usb 1-*: ... using dwc2"
        - Detect /dev/sdX1 and FAT32 (for R/W test)
        - Also report UDC/configfs if gadget mode exists
        """
        if not self._require_connected():
            return

        self.detected_dev = None
        self.detected_fs_ok = False
        self.otg_host_active = False
        self._update_buttons()

        self.info_var.set("Detecting OTG...")
        self._set_busy(True)

        def worker():
            # 1) dmesg: controller + host activity markers
            _, out_dwc2 = self._cmd("dmesg | grep -i -E 'dwc2|DWC OTG Controller' | tail -n 40", timeout=10.0)
            _, out_host = self._cmd("dmesg | grep -E 'usb 1-[0-9]+: new .* using dwc2' | tail -n 10", timeout=10.0)

            host_active = bool(out_host.strip())

            # 2) UDC (device/gadget readiness)
            _, out_udc = self._cmd("ls -1 /sys/class/udc 2>/dev/null || true", timeout=6.0)
            udc_list = [x for x in out_udc.splitlines() if x.strip()]

            # 3) configfs gadget
            _, out_cfg = self._cmd("ls -ld /sys/kernel/config/usb_gadget 2>/dev/null || echo 'no configfs gadget'", timeout=6.0)
            has_cfg = "no configfs gadget" not in out_cfg.lower()

            # 4) block device (mass storage)
            _, out_sd = self._cmd("ls /dev/sd* 2>/dev/null || true", timeout=6.0)

            dev = None
            for tok in out_sd.split():
                if tok.startswith("/dev/sd") and tok[-1].isdigit():
                    dev = tok
                    if tok.endswith("1"):
                        break

            fs_ok = False
            fs_desc = ""
            if dev:
                _, fs_desc = self._cmd(f"file -s {dev} 2>/dev/null || true", timeout=8.0)
                low = fs_desc.lower()
                if "fat (32 bit)" in low or "fat32" in low or "mswin" in low:
                    fs_ok = True

            def ui():
                self._append("== OTG: detect ==")

                self._append("-- Dmesg (dwc2/controller) --")
                self._append("$ dmesg | grep -i dwc2 | tail")
                self._append(out_dwc2 if out_dwc2 else "(no matches)")
                self._append("OK")
                self._append("")

                self._append("-- Dmesg (OTG host activity) --")
                self._append("$ dmesg | grep 'usb 1-* using dwc2' | tail")
                self._append(out_host if out_host else "(no OTG-host activity seen)")
                self._append("OK")
                self._append("")

                self._append("-- UDC (/sys/class/udc) --")
                self._append("$ ls -1 /sys/class/udc")
                self._append(out_udc if out_udc else "(empty)")
                self._append("OK")
                self._append("")

                self._append("-- ConfigFS gadget --")
                self._append("$ ls -ld /sys/kernel/config/usb_gadget")
                self._append(out_cfg if out_cfg else "(no output)")
                self._append("OK")
                self._append("")

                self._append("-- Block devices --")
                self._append("$ ls /dev/sd*")
                self._append(out_sd if out_sd else "(no /dev/sdX found)")
                self._append("OK")
                self._append("")

                if dev:
                    self._append(f"Detected block device: {dev}")
                    if fs_desc:
                        self._append(f"$ file -s {dev}")
                        self._append(fs_desc)
                    self._append("")

                # Decide status
                if host_active and dev and fs_ok:
                    self.otg_host_active = True
                    self.detected_dev = dev
                    self.detected_fs_ok = True
                    self._set_dot("pass")
                    self._append("RESULT: PASS (OTG HOST ACTIVE + Mass Storage detected)")
                    self.info_var.set(f"OTG HOST active. Device {dev} FAT32 OK. Press Run OTG R/W test.")
                elif host_active and dev and not fs_ok:
                    self.otg_host_active = True
                    self.detected_dev = dev
                    self.detected_fs_ok = False
                    self._set_dot("warn")
                    self._append("RESULT: WARN (OTG HOST ACTIVE, but FS not supported by this test)")
                    self._append("INFO: This R/W test expects FAT32 (vfat).")
                    self.info_var.set("OTG host active, but filesystem is not FAT32 for this test.")
                elif host_active and not dev:
                    self.otg_host_active = True
                    self._set_dot("warn")
                    self._append("RESULT: WARN (OTG HOST ACTIVE, but no /dev/sdX1 detected)")
                    self.info_var.set("OTG host active, but block device not found.")
                elif udc_list or has_cfg:
                    self._set_dot("warn")
                    self._append("RESULT: WARN (OTG gadget/peripheral seems possible)")
                    self._append("INFO: This tab currently focuses on OTG HOST mass-storage testing.")
                    self.info_var.set("OTG gadget signals detected. (Different test scenario.)")
                else:
                    self._set_dot("warn")
                    self._append("RESULT: WARN (No clear OTG role active)")
                    self._append("INFO: OTG role is fixed by DTS dr_mode=host/peripheral.")
                    self.info_var.set("No OTG activity. Check DTS dr_mode and Type-C OTG adapter.")

                self._append("")
                self._update_buttons()
                self._set_busy(False)

            self.after(0, ui)

        threading.Thread(target=worker, daemon=True).start()

    def run_test(self):
        """
        OTG Host Mass Storage R/W test:
        - cleanup existing mount
        - mount -t vfat
        - write test file
        - sync
        - read & compare
        - sync before umount
        - umount
        - sync after umount + small delay
        """
        if not self._require_connected():
            return

        if not (self.otg_host_active and self.detected_dev and self.detected_fs_ok):
            self._append("== OTG: R/W test ==")
            self._append("Test disabled: run Detect first and ensure OTG host + FAT32 device.")
            self._append("")
            return

        dev = self.detected_dev
        self._append("== OTG: R/W test ==")
        self.info_var.set("Running OTG R/W test...")
        self._set_busy(True)

        def worker():
            ok_all = True
            steps = []

            def cmd(title, c, to=10.0, must=True):
                nonlocal ok_all
                ok, out = self._cmd(c, timeout=to)
                steps.append((title, c, ok, out))
                if must and not ok:
                    ok_all = False
                return ok, out

            # Cleanup mount if needed
            cmd("Cleanup mount", f"sync; mount | grep -q ' {self.mount_point} ' && umount {self.mount_point} || true; sync", to=12.0, must=False)

            cmd("Prepare mountpoint", f"mkdir -p {self.mount_point}", to=6.0, must=True)
            cmd("Mount (vfat)", f"mount -t vfat {dev} {self.mount_point}", to=12.0, must=True)

            if ok_all:
                cmd("Write", f"echo '{self.test_payload}' > {self.mount_point}/{self.test_file}", to=8.0, must=True)
                cmd("Sync (after write)", "sync", to=12.0, must=True)
                ok_r, read_back = self._cmd(f"cat {self.mount_point}/{self.test_file}", timeout=8.0)
                steps.append(("Read", f"cat {self.mount_point}/{self.test_file}", ok_r, read_back))
                if not ok_r or (read_back.strip() != self.test_payload):
                    ok_all = False
                    steps.append(("Compare", f"(expect '{self.test_payload}')", False, f"got '{read_back.strip()}'"))
                else:
                    steps.append(("Compare", f"(expect '{self.test_payload}')", True, "match"))

                cmd("Sync (before umount)", "sync", to=12.0, must=True)

            cmd("Umount", f"umount {self.mount_point}", to=12.0, must=True)
            cmd("Sync (after umount)", "sync", to=12.0, must=True)

            def ui():
                for title, c, ok, out in steps:
                    self._append(f"-- {title} --")
                    self._append(f"$ {c}")
                    self._append(out if out else "(no output)")
                    self._append("OK" if ok else "FAIL")
                    self._append("")

                # tiny delay so user can safely unplug
                time.sleep(0.3)

                if ok_all:
                    self._set_dot("pass")
                    self._append("RESULT: PASS (OTG HOST R/W)")
                    self.info_var.set("PASS. Safe to unplug after this message.")
                else:
                    self._set_dot("fail")
                    self._append("RESULT: FAIL (OTG HOST R/W)")
                    self.info_var.set("FAIL. Check device/cable/power and retry.")

                self._append("")
                self._set_busy(False)
                # force re-detect after move/unplug
                self.detected_dev = None
                self.detected_fs_ok = False
                self.otg_host_active = False
                self._update_buttons()

            self.after(0, ui)

        threading.Thread(target=worker, daemon=True).start()
