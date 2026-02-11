# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox


class TestAudioTab(ttk.Frame):
    """
    Audio tab (minimal for real-life constraints):

    - Play: starts mpg123 in FOREGROUND (works reliably on your target).
      While playing, the shell is busy (no other commands from this tool).
      Player stops automatically when track ends.

    - Stop: intentionally NOT provided (cannot be done from same serial shell
      while mpg123 is in foreground). Stop only from a real terminal via Ctrl+C.

    - Info: collects basic ALSA / driver / tool info (busybox-friendly).
    """

    MUSIC_TRACK = "/root/ebyte/myMusic/1.mp3"

    def __init__(self, parent, executor, log_fn=None):
        super().__init__(parent)
        self.exec = executor
        self.log_fn = log_fn or (lambda s: None)
        self._build_ui()

    # ------------------------------------------------------------------
    # Executor adapter
    # ------------------------------------------------------------------
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

        ttk.Label(left, text="Audio").pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="Track:").pack(anchor="w")
        self.track_var = tk.StringVar(value=self.MUSIC_TRACK)
        ttk.Entry(left, textvariable=self.track_var, width=42).pack(anchor="w", pady=(4, 10), fill="x")

        ttk.Button(left, text="Play", width=22, command=self.play).pack(anchor="w", pady=3)
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

    def _require_connected(self) -> bool:
        if hasattr(self.exec, "is_connected") and callable(getattr(self.exec, "is_connected")):
            if not self.exec.is_connected():
                self._append("Not connected")
                return False
        return True

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def play(self):
        if not self._require_connected():
            return

        track = (self.track_var.get() or "").strip()
        if not track:
            messagebox.showwarning("Audio", "Set track path first.")
            return

        # Alert BEFORE starting (because while playing, shell is busy)
        messagebox.showinfo(
            "Audio",
            "Track will play until the end.\n"
            "Stop from this tool is not available.\n"
            "To stop immediately, use a real terminal and press Ctrl+C.\n\n"
            "While playing, this serial shell is busy."
        )

        def do():
            self._append("== Play ==")
            self._append(f"Track: {track}")
            self._append("Starting mpg123 (foreground). It will exit automatically at track end.")

            # Optional quick checks
            self._run("aplay -l", timeout_s=6.0)

            # Start playback (foreground)
            # NOTE: No background, no kill — per your platform behavior.
            self._run(f'mpg123 "{track}"', timeout_s=3600.0)

            self._append("Playback finished (mpg123 exited).")
            self._append("OK\n")

        self._run_bg(do)

    def info(self):
        if not self._require_connected():
            return

        def do():
            self._append("== Audio info ==")

            cmds = [
                # Basic ALSA presence
                "aplay -l",
                "arecord -l",
                "cat /proc/asound/cards",
                "cat /proc/asound/pcm",

                # Driver / modules (may be missing on some images)
                "lsmod | grep -E '(^snd|es8316|snd_)' || true",

                # dmesg hints (may be restricted)
                "dmesg | grep -i es8316 | tail -n 50 || true",
                "dmesg | grep -i alsa | tail -n 50 || true",

                # Userspace player availability
                "which mpg123 || true",
                "mpg123 --version || true",
            ]

            for c in cmds:
                self._run(c, timeout_s=6.0)

            self._append("Info collection done.")
            self._append("OK\n")

        self._run_bg(do)
