# shell_executor.py
# -*- coding: utf-8 -*-

import time
import re
import threading
from typing import Optional, Tuple

import serial


PROMPT_REGEX = r"(?m)^[^\n\r]*[#$]\s*$"
LOGIN_REGEX = r"(?im)^\s*(login|username)\s*:\s*$"
PASSWORD_REGEX = r"(?im)^\s*password\s*:\s*$"

READ_CHUNK = 4096


class ShellExecutor:
    """
    Shared COM shell connection (single instance for all tabs).

    - connect()/disconnect()
    - ensure_shell(): tries to reach a prompt (login/password if needed)
    - run(cmd): send command, wait for prompt, return output
    """

    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()

        self.prompt_re = re.compile(PROMPT_REGEX)
        self.login_re = re.compile(LOGIN_REGEX)
        self.pass_re = re.compile(PASSWORD_REGEX)

        self.username = "root"
        self.password = ""

    def is_connected(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def connect(self, port: str, baud: int = 115200, username: str = "root", password: str = ""):
        self.disconnect()

        self.username = username
        self.password = password

        self.ser = serial.Serial(
            port=port,
            baudrate=baud,
            timeout=0.1,          # short timeout -> responsive
            write_timeout=1.0,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None

    def _read_some(self) -> str:
        if not self.ser:
            return ""
        data = self.ser.read(READ_CHUNK)
        if not data:
            return ""
        return data.decode("utf-8", errors="ignore")

    def _write(self, s: str):
        if not self.ser:
            raise RuntimeError("Not connected")
        self.ser.write(s.encode("utf-8", errors="ignore"))

    def _drain(self, duration: float = 0.25) -> str:
        end = time.time() + duration
        out = ""
        while time.time() < end:
            chunk = self._read_some()
            if chunk:
                out += chunk
            else:
                time.sleep(0.02)
        return out

    def ensure_shell(self, overall_timeout: float = 15.0) -> Tuple[bool, str]:
        """
        Wake console and try to get prompt.
        Returns (ok, message)
        """
        if not self.ser:
            return False, "Not connected"

        buf = ""

        # wake
        for _ in range(2):
            self._write("\n")
            time.sleep(0.08)
            buf += self._drain(0.35)

        start = time.time()
        while time.time() - start < overall_timeout:
            self._write("\n")
            time.sleep(0.06)
            buf += self._drain(0.35)

            if self.prompt_re.search(buf):
                return True, "Shell prompt detected."

            if self.login_re.search(buf):
                self._write(self.username + "\n")
                buf += self._drain(0.8)

            if self.pass_re.search(buf):
                self._write(self.password + "\n")
                buf += self._drain(1.0)

            if re.search(r"activate this console", buf, flags=re.I):
                self._write("\n")
                buf += self._drain(0.6)

        return False, "Prompt not detected (timeout)."

    def run(self, cmd: str, timeout_s: float = 6.0) -> Tuple[bool, str]:
        """
        Run a command and wait for prompt. Thread-safe (single command at once).
        Returns (ok, output_text)
        """
        if not self.ser:
            return False, "Not connected"

        cmd = (cmd or "").strip()
        if not cmd:
            return True, ""

        with self._lock:
            # clear noise
            self.ser.reset_input_buffer()

            # send
            self._write(cmd + "\n")

            # collect until prompt
            end = time.time() + timeout_s
            collected = ""

            while time.time() < end:
                chunk = self._read_some()
                if chunk:
                    collected += chunk
                    if self.prompt_re.search(collected):
                        break
                else:
                    time.sleep(0.02)

            # sanitize
            text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", collected).replace("\r", "")
            lines = text.split("\n")

            # remove echoed cmd if it appears as first line
            if lines and lines[0].strip() == cmd:
                lines = lines[1:]

            # remove trailing prompt lines
            while lines and self.prompt_re.match(lines[-1] + "\n"):
                lines = lines[:-1]

            out = "\n".join(lines).strip()
            if "Operation not permitted" in out or "Permission denied" in out:
                return False, out
            if time.time() >= end and not out:
                return False, "[timeout]"
            return True, out
