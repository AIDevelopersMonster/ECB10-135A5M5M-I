# terminal_gui.py
# Minimal Windows GUI terminal over USB-TTL (serial console)
#
# Features:
#  - COM dropdown + Refresh
#  - Connect/Disconnect
#  - Terminal output window
#  - Bottom command line: send command, wait for prompt, show output
#  - Optional auto-login (same logic as in hw_tester_ttl_gui.py)
#
# Install:
#   pip install pyserial
#
# Run:
#   python terminal_gui.py

import re
import time
import threading
import queue
from typing import Optional, Tuple, List

import serial
from serial.tools import list_ports

import tkinter as tk
from tkinter import ttk, messagebox

# ---------- CONFIG (same spirit as your original) ----------
DEFAULT_BAUD = 115200
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = ""

PROMPT_REGEX = r"(?m)^[^\n\r]*[#$]\s*$"
LOGIN_REGEX = r"(?im)^\s*(login|username)\s*:\s*$"
PASSWORD_REGEX = r"(?im)^\s*password\s*:\s*$"

READ_CHUNK = 4096
CMD_TIMEOUT_SEC = 8.0


def list_com_ports() -> List[str]:
    ports = []
    for p in list_ports.comports():
        desc = p.description or ""
        ports.append(f"{p.device} — {desc}".strip())
    return ports


# ---------- Serial shell (expect-like, simplified from your original) ----------
class SerialShell:
    def __init__(self, port: str, baud: int, username: str, password: str):
        self.port = port
        self.baud = baud
        self.username = username
        self.password = password

        self.prompt_re = re.compile(PROMPT_REGEX)
        self.login_re = re.compile(LOGIN_REGEX)
        self.pass_re = re.compile(PASSWORD_REGEX)

        self.ser: Optional[serial.Serial] = None
        self.buffer = ""

    def open(self):
        self.ser = serial.Serial(
            self.port,
            self.baud,
            timeout=0.1,
            write_timeout=1.0,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None

    def is_open(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def _read_some(self) -> str:
        if not self.ser:
            return ""
        data = self.ser.read(READ_CHUNK)
        if not data:
            return ""
        return data.decode("utf-8", errors="ignore")

    def _write(self, s: str):
        if not self.ser:
            raise RuntimeError("Serial not open")
        self.ser.write(s.encode("utf-8", errors="ignore"))

    def _drain(self, duration: float = 0.3) -> str:
        end = time.time() + duration
        out = ""
        while time.time() < end:
            chunk = self._read_some()
            if chunk:
                out += chunk
                self.buffer += chunk
            else:
                time.sleep(0.02)
        return out

    def ensure_shell(self, overall_timeout: float = 20.0) -> Tuple[bool, str]:
        """
        Wake + detect prompt/login/password. Same concept as your original.
        Returns (ok, msg).
        """
        start = time.time()
        self.buffer = ""

        # Wake attempts
        for _ in range(2):
            self._write("\n")
            time.sleep(0.1)
            self._drain(0.4)

        while time.time() - start < overall_timeout:
            self._write("\n")
            time.sleep(0.08)
            self._drain(0.4)

            if self.prompt_re.search(self.buffer):
                return True, "Shell prompt detected."

            if self.login_re.search(self.buffer):
                self._write(self.username + "\n")
                self._drain(0.8)

            if self.pass_re.search(self.buffer):
                self._write(self.password + "\n")
                self._drain(1.0)

            if re.search(r"activate this console", self.buffer, flags=re.I):
                self._write("\n")
                self._drain(0.8)

        return False, "Could not detect prompt/login within timeout. Check COM/baud/UART wiring."

    def run_cmd(self, cmd: str, timeout: float = CMD_TIMEOUT_SEC) -> str:
        """
        Send command, wait for prompt, return command output (without echoed cmd and prompt).
        """
        if not self.ser:
            raise RuntimeError("Serial not open")

        self.buffer = ""
        self._write(cmd.strip() + "\n")

        end = time.time() + timeout
        collected = ""

        while time.time() < end:
            chunk = self._read_some()
            if chunk:
                collected += chunk
                self.buffer += chunk
                if self.prompt_re.search(self.buffer):
                    break
            else:
                time.sleep(0.02)

        # strip ANSI + CR
        text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", collected).replace("\r", "")
        lines = text.split("\n")

        # drop echoed command
        if lines and lines[0].strip() == cmd.strip():
            lines = lines[1:]

        # drop trailing prompt-ish lines
        while lines and self.prompt_re.match(lines[-1] + "\n"):
            lines = lines[:-1]

        return "\n".join(lines).strip()


# ---------- GUI ----------
class TerminalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TTL Terminal (ECB10)")
        self.geometry("1100x760")

        self.q = queue.Queue()
        self.shell: Optional[SerialShell] = None

        self._build_ui()
        self.refresh_ports()

        self.after(100, self._poll_queue)

    def _build_ui(self):
        # Top bar
        frm = ttk.Frame(self, padding=10)
        frm.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(frm, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(frm, textvariable=self.port_var, width=42, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Button(frm, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=(0, 12))

        ttk.Label(frm, text="Baud:").grid(row=0, column=3, sticky="w")
        self.baud_var = tk.IntVar(value=DEFAULT_BAUD)
        ttk.Entry(frm, textvariable=self.baud_var, width=10).grid(row=0, column=4, sticky="w", padx=6)

        ttk.Label(frm, text="User:").grid(row=0, column=5, sticky="w")
        self.user_var = tk.StringVar(value=DEFAULT_USERNAME)
        ttk.Entry(frm, textvariable=self.user_var, width=12).grid(row=0, column=6, sticky="w", padx=6)

        ttk.Label(frm, text="Pass:").grid(row=0, column=7, sticky="w")
        self.pass_var = tk.StringVar(value=DEFAULT_PASSWORD)
        ttk.Entry(frm, textvariable=self.pass_var, width=12, show="*").grid(row=0, column=8, sticky="w", padx=6)

        self.connect_btn = ttk.Button(frm, text="Connect", command=self.on_connect)
        self.connect_btn.grid(row=0, column=9, padx=(12, 4))

        self.disconnect_btn = ttk.Button(frm, text="Disconnect", command=self.on_disconnect, state=tk.DISABLED)
        self.disconnect_btn.grid(row=0, column=10, padx=4)

        self.status_var = tk.StringVar(value="Idle.")
        ttk.Label(frm, textvariable=self.status_var).grid(row=1, column=0, columnspan=11, sticky="w", pady=(8, 0))

        # Terminal output
        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Terminal:").pack(anchor="w")

        self.text = tk.Text(body, wrap=tk.NONE)
        self.text.pack(fill=tk.BOTH, expand=True)

        # Bottom command line
        cmdbar = ttk.Frame(body, padding=(0, 8, 0, 0))
        cmdbar.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Label(cmdbar, text="Command:").pack(side=tk.LEFT)
        self.cmd_var = tk.StringVar()
        self.cmd_entry = ttk.Entry(cmdbar, textvariable=self.cmd_var)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.cmd_entry.bind("<Return>", lambda e: self.on_send())

        self.send_btn = ttk.Button(cmdbar, text="Send", command=self.on_send, state=tk.DISABLED)
        self.send_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(cmdbar, text="Clear", command=self.on_clear).pack(side=tk.LEFT)

    def _selected_port_device(self) -> Optional[str]:
        raw = (self.port_var.get() or "").strip()
        if not raw:
            return None
        return raw.split("—")[0].strip()

    def _set_status(self, s: str):
        self.status_var.set(s)

    def _log(self, s: str):
        self.text.insert(tk.END, s)
        if not s.endswith("\n"):
            self.text.insert(tk.END, "\n")
        self.text.see(tk.END)

    def on_clear(self):
        self.text.delete("1.0", tk.END)

    def refresh_ports(self):
        ports = list_com_ports()
        self.port_combo["values"] = ports
        if ports:
            cur = self.port_var.get()
            if cur in ports:
                self.port_combo.current(ports.index(cur))
            else:
                self.port_combo.current(0)
            self._set_status(f"Found {len(ports)} COM port(s).")
        else:
            self.port_var.set("")
            self._set_status("No COM ports found. Plug USB-TTL and press Refresh.")

    def _set_connected_ui(self, connected: bool):
        self.connect_btn.config(state=tk.DISABLED if connected else tk.NORMAL)
        self.disconnect_btn.config(state=tk.NORMAL if connected else tk.DISABLED)
        self.send_btn.config(state=tk.NORMAL if connected else tk.DISABLED)

    def on_connect(self):
        if self.shell and self.shell.is_open():
            self._set_status("Already connected.")
            return

        port = self._selected_port_device()
        if not port:
            messagebox.showerror("Error", "Select COM port first (or press Refresh).")
            return

        try:
            baud = int(self.baud_var.get())
        except Exception:
            messagebox.showerror("Error", "Invalid baud rate.")
            return

        user = self.user_var.get()
        pwd = self.pass_var.get()

        self._set_status(f"Connecting to {port} @ {baud}...")
        self.connect_btn.config(state=tk.DISABLED)

        def worker():
            try:
                sh = SerialShell(port, baud, user, pwd)
                sh.open()
                ok, msg = sh.ensure_shell()
                if not ok:
                    sh.close()
                    self.q.put(("error", msg))
                    return
                self.q.put(("connected", sh))
                self.q.put(("status", f"Connected: {msg}"))
            except Exception as e:
                self.q.put(("error", f"{type(e).__name__}: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def on_disconnect(self):
        if self.shell:
            try:
                self.shell.close()
            except Exception:
                pass
        self.shell = None
        self._set_connected_ui(False)
        self._set_status("Disconnected.")
        self._log("[DISCONNECTED]")

    def on_send(self):
        cmd = (self.cmd_var.get() or "").strip()
        if not cmd:
            return
        if not (self.shell and self.shell.is_open()):
            messagebox.showerror("Not connected", "Press Connect first.")
            return

        self.cmd_var.set("")
        self.send_btn.config(state=tk.DISABLED)
        self._log(f"$ {cmd}")

        def worker():
            try:
                out = self.shell.run_cmd(cmd, timeout=CMD_TIMEOUT_SEC)
                self.q.put(("cmd_out", out))
            except Exception as e:
                self.q.put(("error", f"{type(e).__name__}: {e}"))
            finally:
                self.q.put(("cmd_done", None))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()

                if kind == "status":
                    self._set_status(payload)

                elif kind == "error":
                    self.connect_btn.config(state=tk.NORMAL if not (self.shell and self.shell.is_open()) else tk.DISABLED)
                    self.send_btn.config(state=tk.NORMAL if (self.shell and self.shell.is_open()) else tk.DISABLED)
                    self._set_status("Error.")
                    messagebox.showerror("Error", payload)

                elif kind == "connected":
                    self.shell = payload
                    self._set_connected_ui(True)
                    self._set_status("Connected.")
                    self._log("[CONNECTED] Shell ready.")

                elif kind == "cmd_out":
                    out = (payload or "").strip()
                    self._log(out if out else "(no output)")

                elif kind == "cmd_done":
                    if self.shell and self.shell.is_open():
                        self.send_btn.config(state=tk.NORMAL)

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)


if __name__ == "__main__":
    TerminalApp().mainloop()
