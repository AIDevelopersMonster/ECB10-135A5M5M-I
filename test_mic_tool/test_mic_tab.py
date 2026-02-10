# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox


class TestMicTab(ttk.Frame):
    """
    Microphone test tab (standalone).

    Notes for THIS project constraints:
      - GUI runs on PC, commands run on TARGET via shared ShellExecutor.
      - One button test: record N seconds -> playback recorded file.
      - No Stop needed: arecord uses -d (fixed duration) and exits by itself.
      - Honest PASS/FAIL: PASS only if recording succeeded AND file exists AND playback started.

    Board-specific:
      - Capture device is hw:0,0 (es8316-ebyte).
      - Capture supports CHANNELS=2 only (mono not available).
    """

    CAPTURE_DEVICE = "hw:0,0"
    PLAYBACK_DEVICE = "hw:0,0"
    OUT_FILE = "/tmp/mic_test.wav"
    RATE = 16000
    DURATION_SEC = 5

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    # ---------------- Executor adapter ----------------
    def _exec_cmd(self, cmd: str, timeout_s: float = 8.0):
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

    # ---------------- UI ----------------
    def _build_ui(self):
        left = ttk.Frame(self, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Microphone").pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="Capture device:").pack(anchor="w")
        self.cap_var = tk.StringVar(value=self.CAPTURE_DEVICE)
        ttk.Entry(left, textvariable=self.cap_var, width=24).pack(anchor="w", pady=(2, 8))

        ttk.Label(left, text="Playback device:").pack(anchor="w")
        self.play_var = tk.StringVar(value=self.PLAYBACK_DEVICE)
        ttk.Entry(left, textvariable=self.play_var, width=24).pack(anchor="w", pady=(2, 8))

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

    # ---------------- Helpers ----------------
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

    def _require_connected(self) -> bool:
        if hasattr(self.exec, "is_connected") and callable(getattr(self.exec, "is_connected")):
            if not self.exec.is_connected():
                self._append("Not connected")
                return False
        return True

    # ---------------- Actions ----------------
    def mic_test(self):
        if not self._require_connected():
            return

        cap = (self.cap_var.get() or self.CAPTURE_DEVICE).strip()
        play = (self.play_var.get() or self.PLAYBACK_DEVICE).strip()
        try:
            dur = int((self.dur_var.get() or str(self.DURATION_SEC)).strip())
        except Exception:
            dur = self.DURATION_SEC
        dur = max(1, min(dur, 30))

        out_file = self.OUT_FILE

        messagebox.showinfo(
            "Microphone test",
            f"Recording {dur} sec, then playback.\n\n"
            f"Speak close to MIC input during recording.\n"
            f"Output file: {out_file}"
        )

        def do():
            self._append("== Microphone test ==")
            self._append(f"Capture device: {cap}")
            self._append(f"Playback device: {play}")
            self._append(f"Duration: {dur} sec")
            self._append("")

            self._run(f'rm -f "{out_file}" >/dev/null 2>&1 || true', timeout_s=4.0)

            channels = 2  # board supports CHANNELS=2 only

            self._append("Recording... Speak now!")
            self._run(
                f'arecord -D "{cap}" -f S16_LE -r {self.RATE} -c {channels} -d {dur} "{out_file}"',
                timeout_s=dur + 10
            )

            ok_ls, out_ls = self._run(f'ls -lh "{out_file}"', timeout_s=6.0)
            if (not ok_ls) or ("No such file" in (out_ls or "")):
                self._append("")
                self._append("FAIL: record file not created (capture params not supported?)")
                self._append("Tip: use Info button and check CHANNELS/RATE/FORMAT.")
                self._append("")
                return

            self._append("")
            self._append("Playing back recorded audio...")
            ok_play, _ = self._run(f'aplay -D "{play}" "{out_file}"', timeout_s=dur + 10)

            self._append("")
            if ok_play:
                self._append("PASS (if you heard your voice)")
            else:
                self._append("FAIL: playback failed")
            self._append("")

        self._run_bg(do)

    def info(self):
        if not self._require_connected():
            return

        def do():
            self._append("== Microphone info ==")
            cmds = [
                "arecord -l",
                "aplay -l",
                "cat /proc/asound/cards",
                "cat /proc/asound/pcm",
                f'arecord -D "{self.CAPTURE_DEVICE}" --dump-hw-params -f S16_LE -r {self.RATE} -c 2 /dev/null || true',
                "which arecord || true",
                "which aplay || true",
                "dmesg | grep -i es8316 | tail -n 50 || true",
                "dmesg | grep -i alsa | tail -n 50 || true",
            ]
            for c in cmds:
                self._run(c, timeout_s=6.0)
            self._append("OK\n")

        self._run_bg(do)
