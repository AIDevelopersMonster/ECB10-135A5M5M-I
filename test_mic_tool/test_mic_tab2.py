# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox


class TestMicTab(ttk.Frame):
    """
    Microphone test tab (standalone, safe, deterministic).

    Design goals (matches our project constraints):
      - No background "player control" and no Stop button required.
      - One button runs a finite test: record N seconds -> playback -> PASS if you hear it.
      - Works via shared executor (serial/ssh shell) where commands run on the TARGET.

    Target requirements:
      - arecord (ALSA utils)
      - aplay  (ALSA utils)
      - writable /tmp
    """

    DEFAULT_CAPTURE_DEV = "hw:0,0"
    DEFAULT_PLAYBACK_DEV = "hw:0,0"

    RECORD_PATH = "/tmp/mic_test.wav"

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)

        self._build_ui()

    # ------------------------------------------------------------------
    # Executor adapter
    # ------------------------------------------------------------------
    def _exec_cmd(self, cmd: str, timeout_s: float = 10.0):
        """
        Unified executor adapter.

        Returns: (ok: bool, out: str)
        """
        try:
            if callable(self.exec):
                res = self.exec(cmd)
            else:
                for attr in ("run", "exec", "execute", "shell"):
                    if hasattr(self.exec, attr):
                        fn = getattr(self.exec, attr)
                        # ShellExecutor.run(cmd, timeout_s=...)
                        try:
                            res = fn(cmd, timeout_s=timeout_s)
                        except TypeError:
                            res = fn(cmd)
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

        ttk.Label(left, text="Microphone").pack(anchor="w", pady=(0, 8))

        # Devices
        ttk.Label(left, text="Capture device (ALSA):").pack(anchor="w")
        self.cap_var = tk.StringVar(value=self.DEFAULT_CAPTURE_DEV)
        ttk.Entry(left, textvariable=self.cap_var, width=26).pack(anchor="w", pady=(4, 10), fill="x")

        ttk.Label(left, text="Playback device (ALSA):").pack(anchor="w")
        self.pb_var = tk.StringVar(value=self.DEFAULT_PLAYBACK_DEV)
        ttk.Entry(left, textvariable=self.pb_var, width=26).pack(anchor="w", pady=(4, 10), fill="x")

        ttk.Label(left, text="Record duration (sec):").pack(anchor="w")
        self.dur_var = tk.StringVar(value="5")
        ttk.Entry(left, textvariable=self.dur_var, width=10).pack(anchor="w", pady=(4, 10))

        ttk.Button(left, text="Mic Test (REC → PLAY)", width=22, command=self.mic_test).pack(anchor="w", pady=3)
        ttk.Button(left, text="Info", width=22, command=self.info).pack(anchor="w", pady=3)

        ttk.Separator(left).pack(fill="x", pady=10)

        ttk.Label(
            left,
            text="Note:\n"
                 "This test records a short WAV\n"
                 "and plays it back automatically.\n"
                 "No STOP is needed.\n",
            justify="left"
        ).pack(anchor="w")

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

    def _run(self, cmd: str, timeout_s: float = 10.0):
        self._append(f"$ {cmd}")
        ok, out = self._exec_cmd(cmd, timeout_s=timeout_s)

        out = (out or "").rstrip("\n")
        if out:
            for line in out.splitlines():
                self._append(line)

        if not ok and not out:
            self._append("(command failed)")

        return ok, out

    def _run_bg(self, fn):
        def worker():
            try:
                fn()
            except Exception as e:
                self.after(0, lambda: self._append(f"ERROR: {e}"))
        threading.Thread(target=worker, daemon=True).start()

    def _require_connected(self) -> bool:
        if hasattr(self.exec, "is_connected") and callable(getattr(self.exec, "is_connected")):
            if not self.exec.is_connected():
                self._append("Not connected")
                return False
        return True

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def mic_test(self):
        if not self._require_connected():
            return

        cap = (self.cap_var.get() or "").strip()
        pb = (self.pb_var.get() or "").strip()
        dur_s = (self.dur_var.get() or "").strip()

        if not cap or not pb:
            messagebox.showwarning("Mic Test", "Set capture and playback devices (e.g. hw:0,0).")
            return

        try:
            dur = int(float(dur_s))
            if dur <= 0 or dur > 30:
                raise ValueError()
        except Exception:
            messagebox.showwarning("Mic Test", "Duration must be 1..30 seconds.")
            return

        messagebox.showinfo(
            "Mic Test",
            "Mic test will:\n"
            f"1) Record {dur} sec to {self.RECORD_PATH}\n"
            "2) Play the recording back\n\n"
            "Speak into the microphone during recording.\n"
            "If you hear your voice on playback → PASS."
        )

        def do():
            self._append("== Microphone test ==")
            self._append(f"Capture device: {cap}")
            self._append(f"Playback device: {pb}")
            self._append(f"Duration: {dur} sec")
            self._append("")

            # cleanup old file (ignore errors)
            self._run(f"rm -f {self.RECORD_PATH} >/dev/null 2>&1 || true", timeout_s=3.0)

            # Record (finite)
            self._append("Recording... Speak now!")
            rec_cmd = f'arecord -D "{cap}" -f S16_LE -r 16000 -c 1 -d {dur} "{self.RECORD_PATH}"'
            ok, _ = self._run(rec_cmd, timeout_s=dur + 15)
            if not ok:
                self._append("Recording failed")
                self._append("FAIL\n")
                return

            # Verify file
            ok, _ = self._run(f'ls -lh "{self.RECORD_PATH}"', timeout_s=5.0)
            if not ok:
                self._append("Recorded file not found")
                self._append("FAIL\n")
                return

            self._append("")
            self._append("Playing back recorded audio...")
            play_cmd = f'aplay -D "{pb}" "{self.RECORD_PATH}"'
            ok, _ = self._run(play_cmd, timeout_s=dur + 20)
            if not ok:
                self._append("Playback failed")
                self._append("FAIL\n")
                return

            self._append("")
            self._append("PASS (if you heard your voice)")
            self._append("")

        self._run_bg(do)

    def info(self):
        if not self._require_connected():
            return

        def do():
            self._append("== Microphone / ALSA info ==")

            cmds = [
                "arecord -l",
                "aplay -l",
                "cat /proc/asound/cards",
                "cat /proc/asound/pcm",
                "ls -l /dev/snd 2>/dev/null || true",
                "lsmod | grep -E '(^snd|es8316|snd_)' || true",
                "dmesg | grep -i es8316 | tail -n 50 || true",
                "dmesg | grep -i alsa | tail -n 50 || true",
                "which arecord || true",
                "which aplay || true",
            ]
            for c in cmds:
                self._run(c, timeout_s=6.0)

            self._append("Info collection done.")
            self._append("OK\n")

        self._run_bg(do)
