# -*- coding: utf-8 -*-

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from serial.tools import list_ports

from shell_executor import ShellExecutor
from terminal_tab import TerminalTab
from test_usb_tab import TestUsbTab


def list_ports_pretty():
    out = []
    for p in list_ports.comports():
        desc = p.description or ""
        out.append(f"{p.device} — {desc}".strip())
    return out


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("USB — COM Tool")
        self.geometry("1150x780")

        self.exec = ShellExecutor()

        self._build_ui()
        self.scan_ports()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # top connection bar (shared)
        bar = ttk.Frame(self, padding=10)
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="COM:").pack(side="left")
        self.port_var = tk.StringVar(value="")
        self.port_combo = ttk.Combobox(bar, textvariable=self.port_var, width=45, state="readonly")
        self.port_combo.pack(side="left", padx=6)

        ttk.Button(bar, text="Scan", command=self.scan_ports).pack(side="left", padx=6)

        ttk.Label(bar, text="Baud:").pack(side="left")
        self.baud_var = tk.IntVar(value=115200)
        ttk.Spinbox(bar, from_=9600, to=3000000, width=10, textvariable=self.baud_var).pack(side="left", padx=6)

        ttk.Label(bar, text="User:").pack(side="left")
        self.user_var = tk.StringVar(value="root")
        ttk.Entry(bar, textvariable=self.user_var, width=10).pack(side="left", padx=6)

        ttk.Label(bar, text="Pass:").pack(side="left")
        self.pass_var = tk.StringVar(value="")
        ttk.Entry(bar, textvariable=self.pass_var, width=10, show="*").pack(side="left", padx=6)

        self.btn_conn = ttk.Button(bar, text="Connect", command=self.toggle_connect)
        self.btn_conn.pack(side="left", padx=10)

        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left", padx=12)

        # notebook
        self.nb = ttk.Notebook(self)
        self.nb.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))

        self.term_tab = TerminalTab(self.nb, executor=self.exec, log_fn=self.log)
        self.nb.add(self.term_tab, text="Terminal")

        # main test tab (single purpose)
        self.main_tab = TestUsbTab(self.nb, executor=self.exec, log_fn=self.log)
        self.nb.add(self.main_tab, text="USB")

        # global log (small)
        lf = ttk.Labelframe(self, text="App Log")
        lf.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        self.log_text = tk.Text(lf, height=6, wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def log(self, s: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {s}\n")
        self.log_text.see("end")

    def scan_ports(self):
        ports = list_ports_pretty()
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_combo.current(0)
        self.log(f"Ports: {ports}")

    def _selected_port_device(self):
        raw = (self.port_var.get() or "").strip()
        if not raw:
            return None
        return raw.split("—")[0].strip()

    def toggle_connect(self):
        if self.exec.is_connected():
            self.exec.disconnect()
            self.status_var.set("Disconnected")
            self.btn_conn.config(text="Connect")
            self.log("Disconnected")
            return

        port = self._selected_port_device()
        if not port:
            messagebox.showwarning("COM", "Select COM port")
            return

        baud = int(self.baud_var.get())
        user = self.user_var.get()
        pwd = self.pass_var.get()

        self.status_var.set(f"Connecting {port}...")
        self.btn_conn.config(state="disabled")

        def worker():
            try:
                self.exec.connect(port, baud=baud, username=user, password=pwd)
                ok, msg = self.exec.ensure_shell()

                def ui():
                    if ok:
                        self.status_var.set(f"Connected: {port}")
                        self.btn_conn.config(text="Disconnect", state="normal")
                        self.log(f"Connected: {port} ({msg})")
                    else:
                        self.exec.disconnect()
                        self.status_var.set("Disconnected")
                        self.btn_conn.config(text="Connect", state="normal")
                        messagebox.showerror("Shell", msg)

                self.after(0, ui)
            except Exception as e:
                err_msg = str(e)
                def ui2(msg=err_msg):
                    self.status_var.set("Disconnected")
                    self.btn_conn.config(text="Connect", state="normal")
                    messagebox.showerror("Connect error", msg)

                self.after(0, ui2)

        threading.Thread(target=worker, daemon=True).start()

    def _on_close(self):
        try:
            self.exec.disconnect()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    MainApp().mainloop()
