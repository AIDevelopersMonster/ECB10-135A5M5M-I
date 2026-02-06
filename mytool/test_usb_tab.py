# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk


class TestUsbTab(ttk.Frame):
    """
    USB HOST test tab (auto port detect + manual override).

    Workflow:
    - Insert device into any USB port.
    - Press Detect: last USB connect path is read from dmesg and mapped to USB1..USB4.
    - Radiobutton is switched automatically if mapping is known.
    - If /dev/sdX1 exists and FS is FAT32 (SD via USB reader), Run test becomes enabled.
    - Run test: mount -> write -> read/compare -> umount.
    - Port dots: gray (untested) / green (PASS) / red (FAIL).
    """

    # Linux USB topology path → logical USB port
    PORT_MAP = {
        "2-1.1": 1,  # USB1
        "2-1.2": 2,  # USB2
        "2-1.3": 3,  # USB3 (UIO1)
        "2-1.4": 4,  # USB4 (UIO2)
    }

    # Human-readable labels (no hard binding to documentation)
    PORT_LABEL = {
        1: "USB1 (Bottom)",
        2: "USB2 (Top)",
        3: "USB3 (UIO1)",
        4: "USB4 (UIO2)",
    }

    DOT_GRAY = "#9e9e9e"
    DOT_GREEN = "#2e7d32"
    DOT_RED = "#c62828"

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)

        self._busy = False

        self.port_var = tk.IntVar(value=1)
        self.port_status = {1: "unknown", 2: "unknown", 3: "unknown", 4: "unknown"}

        self.detected_dev = None
        self.detected_fs_ok = False

        self.mount_point = "/mnt/usb"
        self.test_file = "usb_test.txt"
        self.test_payload = "test 123456789"

        self._build_ui()
        self._refresh_dots()
        self._update_buttons()

    # ---------------- UI ----------------

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="USB HOST", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(left, text="Insert device → Detect → Run test.").pack(anchor="w", pady=(0, 10))

        ports_box = ttk.Labelframe(left, text="Ports")
        ports_box.pack(fill="x", pady=(0, 10))

        self._dot_canvas = {}
        for p in (1, 2, 3, 4):
            row = ttk.Frame(ports_box)
            row.pack(fill="x", pady=2)

            rb = ttk.Radiobutton(
                row,
                text=self.PORT_LABEL.get(p, f"USB{p}"),
                variable=self.port_var,
                value=p,
                command=self._on_port_change,
            )
            rb.pack(side="left")

            c = tk.Canvas(row, width=16, height=16, highlightthickness=0)
            c.pack(side="left", padx=8)
            dot = c.create_oval(2, 2, 14, 14, fill=self.DOT_GRAY, outline="")
            self._dot_canvas[p] = (c, dot)

        actions = ttk.Labelframe(left, text="Actions")
        actions.pack(fill="x", pady=(0, 10))

        self.btn_detect = ttk.Button(actions, text="Detect device", command=self.detect_device, width=22)
        self.btn_detect.pack(anchor="w", pady=4)

        self.btn_test = ttk.Button(actions, text="Run test", command=self.run_test, width=22)
        self.btn_test.pack(anchor="w", pady=4)

        self.btn_reset = ttk.Button(actions, text="Reset statuses", command=self.reset_statuses, width=22)
        self.btn_reset.pack(anchor="w", pady=4)

        self.info_var = tk.StringVar(value="Ready.")
        ttk.Label(left, textvariable=self.info_var, wraplength=260, justify="left").pack(anchor="w", pady=(8, 0))

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        self._append("== USB ==")
        self._append("Workflow: Insert device → Detect (auto) → Run test.")
        self._append("")

    def _append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {msg}\n")
        self.text.see("end")

    # ---------------- helpers ----------------

    def _set_busy(self, busy: bool):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.btn_detect.config(state=state)
        self.btn_reset.config(state=state)
        self._update_buttons()

    def _update_buttons(self):
        if self._busy:
            self.btn_test.config(state="disabled")
        else:
            self.btn_test.config(
                state="normal" if (self.detected_dev and self.detected_fs_ok) else "disabled"
            )

    def _refresh_dots(self):
        for p in (1, 2, 3, 4):
            status = self.port_status[p]
            color = self.DOT_GRAY
            if status == "pass":
                color = self.DOT_GREEN
            elif status == "fail":
                color = self.DOT_RED
            c, dot = self._dot_canvas[p]
            c.itemconfig(dot, fill=color)

    def _on_port_change(self):
        self.detected_dev = None
        self.detected_fs_ok = False
        self._update_buttons()
        self.info_var.set(f"Selected {self.PORT_LABEL[self.port_var.get()]}. Press Detect.")

    def _require_connected(self):
        if not self.exec.is_connected():
            self._append("Not connected")
            self.info_var.set("Not connected.")
            return False
        return True

    def _cmd(self, cmd: str, timeout: float = 8.0):
        ok, out = self.exec.run(cmd, timeout_s=timeout)
        return ok, (out or "").strip()

    def _detect_usb_path_from_dmesg(self):
        _, out = self._cmd("dmesg | tail -n 160", timeout=10.0)
        for ln in reversed(out.splitlines()):
            if " usb " in ln and ": new " in ln and " USB device" in ln:
                try:
                    return ln.split(" usb ", 1)[1].split(":", 1)[0].strip()
                except Exception:
                    pass
        return None

    # ---------------- actions ----------------

    def reset_statuses(self):
        self.port_status = {1: "unknown", 2: "unknown", 3: "unknown", 4: "unknown"}
        self.detected_dev = None
        self.detected_fs_ok = False
        self._refresh_dots()
        self._update_buttons()
        self.info_var.set("Statuses reset. Insert device and press Detect.")
        self._append("== Reset ==")
        self._append("All ports set to UNKNOWN.")
        self._append("")

    def _remaining_ports(self):
        return [p for p in (1, 2, 3, 4) if self.port_status[p] == "unknown"]

    def _print_remaining(self):
        rem = self._remaining_ports()
        if rem:
            labels = ", ".join(self.PORT_LABEL[p] for p in rem)
            self._append(f"Not tested yet: {labels}")
            self._append("Move device to another port and repeat Detect → Test.")
        else:
            self._append("All ports tested.")
        self._append("")

    def detect_device(self):
        if not self._require_connected():
            return

        self.detected_dev = None
        self.detected_fs_ok = False
        self._update_buttons()
        self._set_busy(True)
        self.info_var.set("Detecting device...")

        def worker():
            usb_path = self._detect_usb_path_from_dmesg()
            mapped = self.PORT_MAP.get(usb_path)

            _, out_usb = self._cmd("lsusb")
            _, out_sd = self._cmd("ls /dev/sd* 2>/dev/null || true")

            dev = next((x for x in out_sd.split() if x.endswith("1")), None)

            fs_ok = False
            fs_desc = ""
            if dev:
                _, fs_desc = self._cmd(f"file -s {dev} 2>/dev/null || true")
                if "fat (32 bit)" in fs_desc.lower() or "mswin" in fs_desc.lower():
                    fs_ok = True

            def ui():
                if mapped:
                    self.port_var.set(mapped)

                port = self.port_var.get()
                label = self.PORT_LABEL[port]

                self._append(f"== Detect ({label}) ==")
                if usb_path:
                    self._append(f"Detected USB path: {usb_path}")
                    self._append(f"Mapped to: {self.PORT_LABEL.get(mapped, 'Unknown')}")
                    self._append("")

                self._append("$ lsusb")
                self._append(out_usb or "(no output)")
                self._append("")

                if not dev:
                    self._append("No /dev/sdX1 found.")
                    self._append("RESULT: WAIT")
                    self.info_var.set(f"{label}: insert USB storage and press Detect.")
                    self._set_busy(False)
                    return

                self._append(f"Detected block device: {dev}")
                self._append(fs_desc)
                self._append("")

                if fs_ok:
                    self.detected_dev = dev
                    self.detected_fs_ok = True
                    self._append("Filesystem OK (FAT32). Press Run test.")
                    self.info_var.set(f"{label}: ready for test.")
                else:
                    self._append("Filesystem NOT supported (expected FAT32).")
                    self.info_var.set(f"{label}: unsupported filesystem.")

                self._append("")
                self._set_busy(False)

            self.after(0, ui)

        threading.Thread(target=worker, daemon=True).start()

    def run_test(self):
        if not self._require_connected():
            return

        port = self.port_var.get()
        label = self.PORT_LABEL[port]
        dev = self.detected_dev

        self._append(f"== Run test ({label}) ==")

        if not dev or not self.detected_fs_ok:
            self._append("Run Detect first.")
            self._append("")
            return

        self._set_busy(True)
        self.info_var.set(f"{label}: running test...")

        def worker():
            ok_all = True

            def cmd(title, c):
                nonlocal ok_all
                ok, out = self._cmd(c, timeout=12.0)
                self.after(0, lambda: (
                    self._append(f"-- {title} --"),
                    self._append(f"$ {c}"),
                    self._append(out or "(no output)"),
                    self._append("OK" if ok else "FAIL"),
                    self._append("")
                ))
                if not ok:
                    ok_all = False

            self._cmd(f"mount | grep -q ' {self.mount_point} ' && umount {self.mount_point} || true")
            cmd("Prepare mountpoint", f"mkdir -p {self.mount_point}")
            cmd("Mount", f"mount -t vfat {dev} {self.mount_point}")
            cmd("Write", f"echo '{self.test_payload}' > {self.mount_point}/{self.test_file}")
            cmd("Sync", "sync")
            _, read_back = self._cmd(f"cat {self.mount_point}/{self.test_file}")
            if read_back.strip() != self.test_payload:
                ok_all = False
            cmd("Umount", f"umount {self.mount_point}")

            def ui():
                self.port_status[port] = "pass" if ok_all else "fail"
                self._refresh_dots()
                self._append(f"RESULT: {'PASS' if ok_all else 'FAIL'} ({label})")
                self._append("")
                self._print_remaining()
                self.detected_dev = None
                self.detected_fs_ok = False
                self._update_buttons()
                self._set_busy(False)

            self.after(0, ui)

        threading.Thread(target=worker, daemon=True).start()
