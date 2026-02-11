# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox


class TestMicTab(ttk.Frame):
    """
    Microphone test tab (FINAL, stable).

    Key facts (confirmed on hardware):
      - Capture device: hw:0,0 (ES8316)
      - CHANNELS=2 ONLY (mono is NOT supported)
      - arecord may lock capture device if not terminated properly
      - Info must NEVER leave arecord running
    """

    CAPTURE_DEVICE = "hw:0,0"
    PLAYBACK_DEVICE = "hw:0,0"
    OUT_FILE = "/tmp/mic_test.wav"
    RATE = 16000
    CHANNELS = 2
    DURATION_SEC = 5

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    # ------------------------------------------------------------------
    # Executor adapter
    # ------------------------------------------------------------------
    def _exec_cmd(self, cmd: str, timeout_s: float = 8.0):
        try:
            if callable(self.exec):
                res = self.exec(cmd)
            else:
                for attr in ("run", "exec", "execute", "shell"):
                    if hasattr(self.exec, attr):
                        fn = getattr(self.exec, attr)
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

        ttk.Label(left, text="Capture device:").pack(anchor="w")
        ttk.Entry(left, width=20).insert(0, self.CAPTURE_DEVICE)

        ttk.Label(left, text="Duration (sec):").pack(anchor="w")
        self.dur_var = tk.StringVar(value=str(self.DURATION_SEC))
        ttk.Entry(left, textvariable=self.dur_var, width=10).pack(anchor="w", pady=(2, 10))

        ttk.Button(left, text="Mic Test (REC → PLAY)", width=22, command=self.mic_test).pack(anchor="w", pady=3)
        ttk.Button(left, text="Info", width=22, command=self.info).pack(anchor="w", pady=3)

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

    def _run(self, cmd: str, timeout_s: float = 8.0):
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

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def mic_test(self):
        try:
            dur = int(self.dur_var.get())
        except Exception:
            dur = self.DURATION_SEC
        dur = max(1, min(dur, 20))

        messagebox.showinfo(
            "Microphone test",
            f"Recording {dur} sec, then playback.\n\n"
            "Speak clearly into microphone.\n"
            "Recording will stop automatically."
        )

        def do():
            self._append("== Microphone test ==")
            self._append(f"Device: {self.CAPTURE_DEVICE}")
            self._append(f"Channels: {self.CHANNELS}")
            self._append(f"Duration: {dur} sec")
            self._append("")

            # cleanup
            self._run("killall arecord >/dev/null 2>&1 || true", timeout_s=2)
            self._run(f'rm -f "{self.OUT_FILE}"', timeout_s=2)

            self._append("Recording... Speak now!")
            self._run(
                f'arecord -D "{self.CAPTURE_DEVICE}" '
                f'-f S16_LE -r {self.RATE} -c {self.CHANNELS} '
                f'-d {dur} "{self.OUT_FILE}"',
                timeout_s=dur + 10
            )

            ok_ls, out_ls = self._run(f'ls -lh "{self.OUT_FILE}"', timeout_s=4)
            if not ok_ls or "No such file" in (out_ls or ""):
                self._append("")
                self._append("FAIL: recording file not created")
                self._append("")
                return

            self._append("")
            self._append("Playing back recorded audio...")
            self._run(f'aplay "{self.OUT_FILE}"', timeout_s=dur + 10)

            self._append("")
            self._append("PASS (if you heard your voice)")
            self._append("")

        self._run_bg(do)

    def info(self):
        def do():
            self._append("== Microphone info ==")

            cmds = [
                "arecord -l",
                "aplay -l",
                "cat /proc/asound/cards",
                "cat /proc/asound/pcm",
                # SAFE: auto-exit after 1 sec
                f'arecord -D "{self.CAPTURE_DEVICE}" --dump-hw-params '
                f'-f S16_LE -r {self.RATE} -c {self.CHANNELS} -d 1 /dev/null || true',
                # HARD CLEANUP
                "killall arecord >/dev/null 2>&1 || true",
                "dmesg | grep -i es8316 | tail -n 20 || true",
            ]

            for c in cmds:
                self._run(c, timeout_s=6)

            self._append("OK\n")

        self._run_bg(do)
