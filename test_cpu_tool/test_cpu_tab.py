# test_cpu_tab.py
# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk
import re


CPU_COMMANDS = [
    ("CPU info (full)",    "cat /proc/cpuinfo | head -n 200"),
    ("Model",              "cat /proc/device-tree/model 2>/dev/null || echo '(no model)'"),
    ("Kernel",             "uname -a"),
    ("CPU info (short)",   "cat /proc/cpuinfo | egrep -i 'model name|Hardware|processor|BogoMIPS' | head -n 50"),
    ("Meminfo",            "cat /proc/meminfo | head -n 30"),
    ("Check Nand",            "cat /proc/mtd | head -n 30"),
    ("Uptime",             "uptime; cat /proc/loadavg"),
    ("Top (5 lines)",      "top -b -n 1 | head -n 15"),
    ("Dmesg (last 50)",    "dmesg | tail -n 50"),
]


class TestCPUTab(ttk.Frame):
    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Test CPU").pack(anchor="w", pady=(0, 8))

        for title, cmd in CPU_COMMANDS:
            ttk.Button(left, text=title, width=22, command=lambda c=cmd, t=title: self.run_test(t, c)).pack(
                anchor="w", pady=3
            )

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Button(left, text="RTC quick (info)", width=22, command=self.run_rtc_quick).pack(anchor="w", pady=3)
        ttk.Button(left, text="Run ALL", width=22, command=self.run_all).pack(anchor="w", pady=3)

        # output
        body = ttk.Frame(self, padding=(0, 10, 10, 10))
        body.pack(side="left", fill="both", expand=True)

        self.text = tk.Text(body, wrap="word")
        self.text.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(body, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=sb.set)

    def _append(self, s: str):
        ts = time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {s}\n")
        self.text.see("end")
    def _parse_hwclock(self, s: str):
        """
        Parses typical hwclock -r output, e.g.:
        "Thu Feb  5 08:09:22 2026  0.000000 seconds"
        Returns dict or None.
        """
        if not s:
            return None
        s = s.strip()
        m = re.search(r"\b([A-Za-z]{3})\s+([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+(\d{4})\b", s)
        if not m:
            return None
        return {
            "wday": m.group(1),
            "mon": m.group(2),
            "day": int(m.group(3)),
            "time": m.group(4),
            "year": int(m.group(5)),
            "raw": s,
        }

    def run_rtc_quick(self):
        """
        RTC quick info-test (no policy decisions, only facts).
        """
        if not self.exec.is_connected():
            self._append("Not connected")
            return

        self._append("== RTC quick (info) ==")

        def worker():
            def ui_line(line: str):
                self.after(0, lambda: self._append(line))

            # 1) Presence
            ok_dev, out_dev = self.exec.run("ls -l /dev/rtc* 2>/dev/null", timeout_s=5.0)
            ui_line("$ ls -l /dev/rtc*")
            ui_line(out_dev.strip() if out_dev.strip() else "(no output)")
            ui_line("OK" if ok_dev else "FAIL")
            ui_line("")

            # 2) RTC read #1
            ok_r1, out_r1 = self.exec.run("hwclock -r 2>&1", timeout_s=5.0)
            rtc1 = self._parse_hwclock(out_r1)
            ui_line("$ hwclock -r")
            ui_line(out_r1.strip() if out_r1.strip() else "(no output)")
            ui_line("OK" if ok_r1 else "FAIL")
            if rtc1 and rtc1["year"] == 2000:
                ui_line("NOTE: RTC calendar appears reset (year = 2000)")
            ui_line("")

            # 3) RTC ticking check
            ok_sleep, _ = self.exec.run("sleep 5", timeout_s=7.0)
            ok_r2, out_r2 = self.exec.run("hwclock -r 2>&1", timeout_s=5.0)
            rtc2 = self._parse_hwclock(out_r2)
            ui_line("$ sleep 5; hwclock -r")
            ui_line(out_r2.strip() if out_r2.strip() else "(no output)")
            ui_line("OK" if (ok_sleep and ok_r2) else "FAIL")

            ticking = None
            if rtc1 and rtc2 and rtc1["raw"] != rtc2["raw"]:
                ticking = True
            elif rtc1 and rtc2 and rtc1["raw"] == rtc2["raw"]:
                ticking = False
            ui_line(f"RTC ticking: {ticking if ticking is not None else 'unknown'}")
            ui_line("")

            # 4) Write test value (BusyBox-friendly)
            # BusyBox hwclock often supports only -s/-w/-r/-u/-l and cannot set an arbitrary RTC date.
            # Fallback approach:
            #   - save current system time
            #   - set system to a test time
            #   - write system -> RTC (hwclock -u -w)
            #   - readback RTC
            #   - restore original system time
            #   - write system -> RTC again (restore RTC "as was")
            ui_line("RTC write test:")

            # Detect if hwclock supports --set
            ok_help, out_help = self.exec.run("hwclock --help 2>&1", timeout_s=5.0)
            supports_set = ("--set" in out_help) or ("--date" in out_help)

            if supports_set:
                ok_w, out_w = self.exec.run('hwclock -u --set --date "2022-01-01 12:00:00" 2>&1', timeout_s=6.0)
                ok_rb, out_rb = self.exec.run("hwclock -r 2>&1", timeout_s=5.0)
                ui_line('$ hwclock -u --set --date "2022-01-01 12:00:00"')
                ui_line(out_w.strip() if out_w.strip() else "(no output)")
                ui_line("OK" if ok_w and ("unrecognized option" not in out_w.lower()) else "FAIL")
                ui_line("$ hwclock -r  (readback)")
                ui_line(out_rb.strip() if out_rb.strip() else "(no output)")
                ui_line("OK" if ok_rb else "FAIL")
                ui_line("")
                write_set_ok = ok_w and ("unrecognized option" not in out_w.lower())
                readback_ok = ok_rb
            else:
                # BusyBox fallback
                ui_line(
                    "INFO: BusyBox hwclock has no --set/--date; using fallback via 'date -s' + 'hwclock -w' (will restore time afterwards).")

                # Save current system time (UTC) for restore
                ok_save, out_save = self.exec.run("date -u '+%Y-%m-%d %H:%M:%S' 2>&1", timeout_s=5.0)
                saved_utc = out_save.strip() if ok_save else ""
                ui_line("$ date -u '+%Y-%m-%d %H:%M:%S'  (save)")
                ui_line(saved_utc if saved_utc else "(no output)")
                ui_line("OK" if ok_save else "FAIL")

                # Set a test system time (use UTC to avoid TZ confusion)
                ok_setsys, out_setsys = self.exec.run("date -u -s '2022-01-01 12:00:00' 2>&1", timeout_s=6.0)
                ui_line("$ date -u -s '2022-01-01 12:00:00'  (temp)")
                ui_line(out_setsys.strip() if out_setsys.strip() else "(no output)")
                ui_line("OK" if ok_setsys else "FAIL")

                # Write system -> RTC
                ok_w, out_w = self.exec.run("hwclock -u -w 2>&1", timeout_s=6.0)
                ui_line("$ hwclock -u -w  (system -> RTC)")
                ui_line(out_w.strip() if out_w.strip() else "(no output)")
                ui_line("OK" if ok_w else "FAIL")

                # Readback RTC
                ok_rb, out_rb = self.exec.run("hwclock -r 2>&1", timeout_s=5.0)
                ui_line("$ hwclock -r  (readback)")
                ui_line(out_rb.strip() if out_rb.strip() else "(no output)")
                ui_line("OK" if ok_rb else "FAIL")

                # Restore original system time (UTC)
                if saved_utc:
                    ok_restore, out_restore = self.exec.run(f"date -u -s '{saved_utc}' 2>&1", timeout_s=6.0)
                    ui_line(f"$ date -u -s '{saved_utc}'  (restore)")
                    ui_line(out_restore.strip() if out_restore.strip() else "(no output)")
                    ui_line("OK" if ok_restore else "FAIL")
                else:
                    ok_restore = False
                    ui_line("WARN: Could not save system time, skip restore step.")

                # Restore RTC from restored system time
                ok_w2, out_w2 = self.exec.run("hwclock -u -w 2>&1", timeout_s=6.0)
                ui_line("$ hwclock -u -w  (restore RTC from restored system time)")
                ui_line(out_w2.strip() if out_w2.strip() else "(no output)")
                ui_line("OK" if ok_w2 else "FAIL")

                ui_line("")
                write_set_ok = ok_w and ok_setsys and ok_save and ok_restore and ok_w2
                readback_ok = ok_rb

            # 5) Show system time
            ok_date, out_date = self.exec.run("date 2>&1", timeout_s=5.0)
            ui_line("$ date")
            ui_line(out_date.strip() if out_date.strip() else "(no output)")
            ui_line("OK" if ok_date else "FAIL")
            ui_line("")

            # 6) Restore RTC from system time (no policy; just do it as part of test)
            ok_wr, out_wr = self.exec.run("hwclock -u -w 2>&1", timeout_s=6.0)
            ok_r3, out_r3 = self.exec.run("hwclock -r 2>&1", timeout_s=5.0)
            ui_line("$ hwclock -u -w")
            ui_line(out_wr.strip() if out_wr.strip() else "(no output)")
            ui_line("OK" if ok_wr else "FAIL")
            ui_line("$ hwclock -r  (after write system time)")
            ui_line(out_r3.strip() if out_r3.strip() else "(no output)")
            ui_line("OK" if ok_r3 else "FAIL")
            ui_line("")

            # 7) ntpd presence
            ok_ntp, out_ntp = self.exec.run("ps | grep [n]tpd 2>&1", timeout_s=5.0)
            ntp_running = bool(out_ntp.strip())
            ui_line("$ ps | grep [n]tpd")
            ui_line(out_ntp.strip() if out_ntp.strip() else "(not detected)")
            ui_line("OK" if ok_ntp else "FAIL")
            ui_line(f"NTP daemon detected: {ntp_running}")
            ui_line("")

            # 8) RTC vs system time (rough)
            # If busybox date supports +%s, we can do numeric diff.
            # Otherwise we just print both (already done).
            ok_rtcs, out_rtcs = self.exec.run("date -u +%s 2>/dev/null || echo NA", timeout_s=5.0)
            ok_sys, out_sys = self.exec.run("date -u +%s 2>/dev/null || echo NA", timeout_s=5.0)
            # Read RTC again and attempt to convert via date -d (may not exist). So we only do diff if we can.
            # We'll do a practical approach: compare strings already printed. For numeric diff, use busybox 'date -D' varies.
            # So here: only show whether epoch is available.
            epoch_ok = out_sys.strip().isdigit()
            ui_line("RTC vs system diff: (epoch diff not computed on this image)" if not epoch_ok else "RTC vs system diff: (see printed times)")
            ui_line("")
            ui_line("Summary (facts):")
            ui_line(f"- RTC device present: {ok_dev}")
            ui_line(f"- RTC ticking: {ticking if ticking is not None else 'unknown'}")
            if rtc1:
                ui_line(f"- RTC year at first read: {rtc1['year']}")
            ui_line(f"- RTC write test set/readback: set_ok={write_set_ok}, readback_ok={readback_ok}")
            ui_line(f"- NTP daemon detected: {ntp_running}")
            ui_line("Note: This test does not confirm presence/absence of a backup battery; full power removal is required for that.")
            ui_line("")

        threading.Thread(target=worker, daemon=True).start()


    def run_test(self, title: str, cmd: str):
        if not self.exec.is_connected():
            self._append("Not connected")
            return

        self._append(f"== {title} ==")
        self._append(f"$ {cmd}")

        def worker():
            ok, out = self.exec.run(cmd, timeout_s=8.0)
            def ui():
                self._append(out if out else "(no output)")
                self._append("OK" if ok else "FAIL")
                self._append("")
            self.after(0, ui)

        threading.Thread(target=worker, daemon=True).start()

    def run_all(self):
        # Run sequentially in one worker to avoid mixing outputs
        if not self.exec.is_connected():
            self._append("Not connected")
            return

        def worker():
            for title, cmd in CPU_COMMANDS:
                ok, out = self.exec.run(cmd, timeout_s=10.0)
                def ui_one(t=title, c=cmd, o=out, k=ok):
                    self._append(f"== {t} ==")
                    self._append(f"$ {c}")
                    self._append(o if o else "(no output)")
                    self._append("OK" if k else "FAIL")
                    self._append("")
                self.after(0, ui_one)

        threading.Thread(target=worker, daemon=True).start()
