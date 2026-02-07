# -*- coding: utf-8 -*-

import time
import tkinter as tk
from tkinter import ttk


class TestTouchTab(ttk.Frame):
    """Touch — HDMI + USB touchscreen checks (HID).

    IMPORTANT (project logic):
    - We do NOT try to stream live coordinates inside MyTools pseudo-terminal.
      Tools like `evtest` are interactive and work best in a real terminal
      (MobaXterm / SSH / serial).
    - In MyTools we only:
        1) confirm the device is detected
        2) show where it appears (/dev/input/eventX)
        3) show how to run a proper live test in a real terminal

    ShellExecutor contract (same as SD/CPU/USB tabs):
      - exec.is_connected() -> bool
      - ok, out = exec.run(cmd, timeout_s=<float>)
    """  # noqa: D400

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)

        self._build_ui()

    # ----------------
    # UI
    # ----------------
    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Touch", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Button(left, text="Run (quick detect)", width=22, command=self.run_quick).pack(anchor="w", pady=3)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        ttk.Button(left, text="Input events", width=22, command=self.cmd_input_events).pack(anchor="w", pady=3)
        ttk.Button(left, text="Detect touchscreen", width=22, command=self.cmd_detect_touch).pack(anchor="w", pady=3)
        ttk.Button(left, text="dmesg (USB/HID)", width=22, command=self.cmd_dmesg_usb).pack(anchor="w", pady=3)
        ttk.Button(left, text="How to test (evtest)", width=22, command=self.cmd_evtest_howto).pack(anchor="w", pady=3)

        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        # Output area
        out_frame = ttk.Frame(body)
        out_frame.pack(side="top", fill="both", expand=True)

        self.text = tk.Text(out_frame, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(out_frame, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

        # Command line (non-interactive commands only)
        cli = ttk.Frame(body)
        cli.pack(side="bottom", fill="x", pady=(8, 0))

        ttk.Label(cli, text="Command:").pack(side="left")

        self.cmd_var = tk.StringVar()
        self.cmd_entry = ttk.Entry(cli, textvariable=self.cmd_var)
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.cmd_entry.bind("<Return>", lambda _e: self.run_cli())

        ttk.Button(cli, text="Run", command=self.run_cli).pack(side="right")

        self._append("Touch tab ready. Use 'Run (quick detect)' first.")

    # ----------------
    # Helpers
    # ----------------
    def _append(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {msg}\n")
        self.text.see("end")

    def _section(self, title: str):
        self._append(f"== {title} ==")

    def _run(self, cmd: str, timeout_s: float = 6.0):
        """Run command via ShellExecutor contract."""
        if not self.exec.is_connected():
            return False, "Not connected"
        ok, out = self.exec.run(cmd, timeout_s=timeout_s)
        return bool(ok), (out or "")

    def _print_cmd_output(self, cmd: str, out: str):
        self._append(f"$ {cmd}")
        if out.strip():
            for line in out.splitlines():
                self._append(line)
        else:
            self._append("(no output)")
        self._append("")

    # ----------------
    # Main quick test
    # ----------------
    def run_quick(self):
        self._section("Touch quick detect (HDMI + USB)")
        if not self.exec.is_connected():
            self._append("Not connected")
            self._append("FAIL")
            self._append("")
            return

        # 1) /dev/input/event*
        ok1, out1 = self._run("ls -l /dev/input/event* 2>/dev/null", timeout_s=3.0)
        self._print_cmd_output("ls -l /dev/input/event*", out1)

        # 2) Find touchscreen blocks (stronger than a single grep line)
        ok2, out2 = self._run("cat /proc/bus/input/devices 2>/dev/null", timeout_s=6.0)
        if out2.strip():
            blocks = out2.split("\n\n")
            hits = []
            for b in blocks:
                lb = b.lower()
                if ("touchscreen" in lb) or ("wch.cn" in lb) or ("usb2iic" in lb) or ("1a86" in lb) or ("e2e3" in lb):
                    hits.append(b)
            self._append("$ cat /proc/bus/input/devices | (filter)")
            if hits:
                for i, b in enumerate(hits, 1):
                    self._append(f"--- match {i} ---")
                    for line in b.splitlines():
                        self._append(line)
            else:
                self._append("(no obvious touch device blocks found)")
            self._append("")
        else:
            self._print_cmd_output("cat /proc/bus/input/devices", out2)

        # 3) dmesg hints
        ok3, out3 = self._run("dmesg | grep -iE 'wch\\.cn|usb2iic|touchscreen|hid|1a86:e2e3' | tail -n 60", timeout_s=6.0)
        self._print_cmd_output("dmesg | grep -iE wch.cn|usb2iic|touchscreen|hid|1a86:e2e3 | tail -n 60", out3)

        detected = bool(out1.strip()) and ("/dev/input/event" in out1)
        detected = detected or ("touchscreen" in out2.lower()) or ("wch.cn" in out2.lower())
        detected = detected or ("hid" in out3.lower()) or ("touchscreen" in out3.lower())

        if detected:
            self._append("Result: PASSED (touch device detected)")
            self._append("Next: use 'How to test (evtest)' and run it in a real terminal for live coordinates.")
        else:
            self._append("Result: INCONCLUSIVE")
            self._append("Tip: connect the touchscreen USB cable to a USB-A HOST port (not USB-C OTG).")

        self._append("")

    # ----------------
    # Individual actions
    # ----------------
    def cmd_input_events(self):
        self._section("Input devices (/dev/input)")
        ok, out = self._run("ls -l /dev/input 2>/dev/null", timeout_s=3.0)
        self._print_cmd_output("ls -l /dev/input", out)

    def cmd_detect_touch(self):
        self._section("Detect touchscreen (filtered blocks)")
        ok, out = self._run("cat /proc/bus/input/devices 2>/dev/null", timeout_s=6.0)
        if not out.strip():
            self._append("$ cat /proc/bus/input/devices")
            self._append("(no output)")
            self._append("")
            return

        blocks = out.split("\n\n")
        hits = []
        for b in blocks:
            lb = b.lower()
            if ("touchscreen" in lb) or ("wch.cn" in lb) or ("usb2iic" in lb) or ("1a86" in lb) or ("e2e3" in lb):
                hits.append(b)

        self._append("$ cat /proc/bus/input/devices | (filter)")
        if not hits:
            self._append("(no obvious touch device blocks found)")
        else:
            for i, b in enumerate(hits, 1):
                self._append(f"--- match {i} ---")
                for line in b.splitlines():
                    self._append(line)
        self._append("")

    def cmd_dmesg_usb(self):
        self._section("USB/HID log (filtered)")
        ok, out = self._run("dmesg | tail -n 200", timeout_s=6.0)
        self._append("$ dmesg | (filter usb/hid/touch)")
        if not out.strip():
            self._append("(no output)")
            self._append("")
            return

        lines = []
        for line in out.splitlines():
            ll = line.lower()
            if ("usb" in ll) or ("hid" in ll) or ("touch" in ll) or ("wch.cn" in ll) or ("1a86" in ll) or ("e2e3" in ll):
                lines.append(line)

        if lines:
            for line in lines[-120:]:
                self._append(line)
        else:
            self._append("(no matching lines)")
        self._append("")

    def cmd_evtest_howto(self):
        self._section("How to test live coordinates (real terminal)")
        ok, out = self._run("command -v evtest 2>/dev/null || echo NO", timeout_s=3.0)
        if out.strip() == "NO":
            self._append("evtest: NOT found on target")
            self._append("You can still identify devices via:")
            self._append("  cat /proc/bus/input/devices")
            self._append("")
            return

        self._append("evtest: found")
        self._append("")
        self._append("Why not in MyTools window?")
        self._append("- evtest is interactive and prints a continuous stream.")
        self._append("- Our pseudo-terminal collects output with timeouts, so coordinates may be lost.")
        self._append("")
        self._append("Run in a REAL terminal (MobaXterm / SSH / serial):")
        self._append("  1) Find eventX for the touchscreen:")
        self._append("     grep -n 'USB2IIC_CTP_CONTROL' /proc/bus/input/devices -A6")
        self._append("  2) Start live test (replace X):")
        self._append("     evtest /dev/input/eventX")
        self._append("  Or run evtest and select by number:")
        self._append("     evtest")
        self._append("")
        self._append("Expected: ABS_X / ABS_Y events + BTN_TOUCH when you touch the screen.")
        self._append("")

    # ----------------
    # CLI runner (non-interactive)
    # ----------------
    def run_cli(self):
        cmd = (self.cmd_var.get() or "").strip()
        if not cmd:
            return

        # Guard: interactive tools won't work reliably here
        interactive_keywords = ("evtest", "top", "htop", "less", "more", "vi", "vim")
        if any(cmd.startswith(k) for k in interactive_keywords):
            self._append(f"$ {cmd}")
            self._append("Interactive command detected. Run it in a real terminal (MobaXterm / SSH / serial).") 
            self._append("Use 'How to test (evtest)' for exact commands.")
            self._append("")
            return

        self._section("CLI")
        ok, out = self._run(cmd, timeout_s=8.0)
        self._print_cmd_output(cmd, out)
