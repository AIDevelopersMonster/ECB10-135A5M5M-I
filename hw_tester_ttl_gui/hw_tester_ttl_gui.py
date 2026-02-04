# hw_tester_ttl_gui.py
# Windows GUI hardware tester over USB-TTL (serial console).
#
# Features:
#  - COM port dropdown (auto-detect) + Refresh
#  - "Run Tests" batch (parses results)
#  - Bottom command line (send arbitrary command, see output)
#  - Help tab: built-in help + optional external help.json / help.md (auto-load)
#
# Install:
#   pip install pyserial
#
# Run:
#   python hw_tester_ttl_gui.py

import os
import re
import time
import json
import queue
import threading
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Tuple

import serial
from serial.tools import list_ports

import tkinter as tk
from tkinter import ttk, messagebox, filedialog


# =========================
# CONFIG
# =========================
DEFAULT_BAUD = 115200
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = ""  # often empty on dev images

PROMPT_REGEX = r"(?m)^[^\n\r]*[#$]\s*$"
LOGIN_REGEX = r"(?im)^\s*(login|username)\s*:\s*$"
PASSWORD_REGEX = r"(?im)^\s*password\s*:\s*$"

READ_CHUNK = 4096
CMD_TIMEOUT_SEC = 10.0

HELP_JSON_PATH = "help.json"
HELP_MD_PATH = "help.md"


# =========================
# HELP (builtin + optional external)
# =========================

BUILTIN_HELP = {
    "Used by this tool": [
        {
            "cmd": "cat /proc/cpuinfo",
            "why": "CPU model/features/cores; quick sanity that kernel sees the SoC correctly.",
            "notes": "BogoMIPS is NOT performance; check Features includes neon/vfp if you care about SIMD/FPU."
        },
        {
            "cmd": "cat /proc/meminfo",
            "why": "RAM totals & availability.",
            "notes": "MemAvailable is the key; MemFree alone is misleading on Linux."
        },
        {
            "cmd": "cat /sys/class/hwmon/hwmon0/temp1_input  (fallback: /sys/class/thermal/thermal_zone0/temp)",
            "why": "CPU temperature in milli-degrees.",
            "notes": "Divide by 1000. Typical thresholds: <70 OK, 70–85 WARN, >85 FAIL (tune for your design)."
        },
        {
            "cmd": "cat /proc/mtd",
            "why": "NAND/MTD partition table; validates expected layout and that MTD driver is alive.",
            "notes": "Read-only. Avoid nandwrite in diagnostics unless you REALLY know what you're doing."
        },
        {
            "cmd": "lsusb",
            "why": "USB host enumeration; shows hub/devices attached.",
            "notes": "If lsusb missing, install usbutils (depends on image)."
        },
        {
            "cmd": "ip -brief addr  (and ip addr)",
            "why": "Network interface state and IPs; quick check of eth0/wlan0/can0 presence.",
            "notes": "wlan0 DOWN is normal without config; can0 DOWN is normal until bitrate is set."
        },
        {
            "cmd": "hwclock -r",
            "why": "RTC read; verifies RTC + VBAT retention.",
            "notes": "If missing, busybox build may not include it; check /dev/rtc0 and kernel config."
        },
        {
            "cmd": "uname -a ; uptime",
            "why": "Kernel/build info and overall system load/time since boot.",
            "notes": "Good for correlating reports and confirming expected image version."
        },
    ],
    "Recommended (safe, read-only) diagnostics": [
        {
            "cmd": "cat /proc/device-tree/model",
            "why": "Board identification; helps ensure you're testing the right target.",
            "notes": "Often ends with a NUL; use: strings /proc/device-tree/model"
        },
        {
            "cmd": "dmesg | tail -n 120",
            "why": "Recent kernel messages; catches driver failures, PHY issues, USB errors.",
            "notes": "Great after plugging devices."
        },
        {
            "cmd": "lsblk ; df -h",
            "why": "Storage visibility & mounted FS; SD/USB/NAND/UBI sanity.",
            "notes": "Read-only."
        },
        {
            "cmd": "cat /sys/kernel/debug/gpio  (if debugfs mounted)",
            "why": "GPIO state/owners; useful when peripherals don’t respond.",
            "notes": "Might require: mount -t debugfs none /sys/kernel/debug"
        },
        {
            "cmd": "ethtool eth0  (if present)",
            "why": "Ethernet link speed/duplex; PHY status.",
            "notes": "Requires ethtool package."
        },
        {
            "cmd": "journalctl -b --no-pager | tail -n 200  (systemd)",
            "why": "Boot logs at user-space level.",
            "notes": "If no systemd/journal, skip."
        },
    ],
    "Optional (may change state, use carefully)": [
        {
            "cmd": "memtester 10M 1",
            "why": "RAM stress (alloc+patterns).",
            "notes": "Consumes RAM and time; safe but affects system load."
        },
        {
            "cmd": "ip link set can0 type can bitrate 1000000 ; ip link set can0 up",
            "why": "Brings CAN up for testing.",
            "notes": "Requires can-utils for candump/cansend; needs proper transceiver wiring/termination."
        },
        {
            "cmd": "dd if=/dev/zero of=/tmp/test.bin bs=1M count=50 conv=fdatasync",
            "why": "Quick write throughput test to RAM-backed FS (tmpfs) or chosen target.",
            "notes": "DO NOT run against raw NAND partitions casually."
        },
    ],
}


def load_help_text() -> str:
    """
    Priority:
      1) help.md if exists
      2) help.json if exists
      3) builtin help formatted
    """
    # 1) Markdown file
    if os.path.exists(HELP_MD_PATH):
        try:
            with open(HELP_MD_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass

    # 2) JSON file
    if os.path.exists(HELP_JSON_PATH):
        try:
            with open(HELP_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return format_help_from_dict(data)
        except Exception:
            pass

    # 3) Builtin
    return format_help_from_dict(BUILTIN_HELP)


def format_help_from_dict(d: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=== HELP: Commands & Diagnostics ===\n")
    for section, items in d.items():
        lines.append(f"\n## {section}\n")
        if isinstance(items, list):
            for it in items:
                cmd = it.get("cmd", "").strip()
                why = it.get("why", "").strip()
                notes = it.get("notes", "").strip()
                lines.append(f"- CMD: {cmd}")
                if why:
                    lines.append(f"  WHY: {why}")
                if notes:
                    lines.append(f"  NOTES: {notes}")
                lines.append("")
        else:
            lines.append(str(items))
            lines.append("")
    lines.append("\nTip: You can place a custom help.md or help.json next to this script to override the built-in help.\n")
    return "\n".join(lines)


# =========================
# Utility
# =========================

def list_com_ports() -> List[str]:
    ports = []
    for p in list_ports.comports():
        desc = p.description or ""
        ports.append(f"{p.device} — {desc}".strip())
    return ports


@dataclass
class TestResult:
    name: str
    ok: bool
    summary: str
    details: str = ""
    data: Optional[Dict[str, Any]] = None


# =========================
# Serial shell (expect-like)
# =========================

class SerialShell:
    def __init__(
        self,
        port: str,
        baud: int,
        username: str,
        password: str,
        prompt_regex: str = PROMPT_REGEX,
    ):
        self.port = port
        self.baud = baud
        self.username = username
        self.password = password

        self.prompt_re = re.compile(prompt_regex)
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

    def ensure_shell(self, overall_timeout: float = 25.0) -> Tuple[bool, str]:
        start = time.time()
        self.buffer = ""

        # Wake attempt
        for _ in range(3):
            self._write("\n")
            time.sleep(0.1)
            self._write("\n")
            self._drain(0.4)

        while time.time() - start < overall_timeout:
            self._write("\n")
            time.sleep(0.1)
            self._drain(0.5)

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

        # Remove ANSI escapes + CR
        text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", collected).replace("\r", "")
        lines = text.split("\n")

        # Drop echoed command if first line matches
        if lines and lines[0].strip() == cmd.strip():
            lines = lines[1:]

        # Drop trailing prompt-ish lines
        while lines and self.prompt_re.match(lines[-1] + "\n"):
            lines = lines[:-1]

        return "\n".join(lines).strip()


# =========================
# Parsers
# =========================

def parse_cpuinfo(txt: str) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for key in ["model name", "Processor", "Hardware", "Revision", "BogoMIPS", "Features", "CPU architecture", "Serial"]:
        m = re.search(rf"(?m)^{re.escape(key)}\s*:\s*(.+)$", txt)
        if m:
            d[key] = m.group(1).strip()
    procs = re.findall(r"(?m)^processor\s*:\s*\d+", txt)
    d["cores_detected"] = len(procs) if procs else 1
    return d


def parse_meminfo(txt: str) -> Dict[str, Any]:
    def get_kb(name: str) -> Optional[int]:
        m = re.search(rf"(?m)^{name}:\s+(\d+)\s+kB", txt)
        return int(m.group(1)) if m else None

    mt = get_kb("MemTotal")
    ma = get_kb("MemAvailable")
    mf = get_kb("MemFree")
    return {
        "MemTotal_kB": mt,
        "MemAvailable_kB": ma,
        "MemFree_kB": mf,
        "MemAvailable_pct": round((ma / mt) * 100, 1) if (mt and ma) else None,
    }


def parse_temp_millideg(txt: str) -> Optional[float]:
    m = re.search(r"(-?\d+)", txt.strip())
    if not m:
        return None
    return int(m.group(1)) / 1000.0


def parse_proc_mtd(txt: str) -> Dict[str, Any]:
    mtds = []
    for line in txt.splitlines():
        m = re.match(r"^(mtd\d+):\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+\"(.+)\"", line.strip())
        if m:
            mtds.append({
                "name": m.group(1),
                "size_hex": m.group(2),
                "erase_hex": m.group(3),
                "label": m.group(4),
            })
    return {"mtd_count": len(mtds), "mtd": mtds}


def parse_ip_addr_full(txt: str) -> Dict[str, Any]:
    ifaces: Dict[str, Any] = {}
    current = None
    for line in txt.splitlines():
        m = re.match(r"^\d+:\s+([^:]+):\s+<([^>]*)>.*state\s+(\w+)", line)
        if m:
            current = m.group(1)
            ifaces[current] = {"state": m.group(3), "flags": m.group(2), "inet": []}
        m2 = re.match(r"^\s+inet\s+([0-9.]+)/(\d+)", line)
        if m2 and current:
            ifaces[current]["inet"].append(f"{m2.group(1)}/{m2.group(2)}")
    return {"interfaces": ifaces}


def parse_lsusb(txt: str) -> Dict[str, Any]:
    devices = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    return {"device_count": len(devices), "devices": devices}


# =========================
# Tests
# =========================

def build_tests(shell: SerialShell) -> List[TestResult]:
    results: List[TestResult] = []

    # CPU
    cpu_txt = shell.run_cmd("cat /proc/cpuinfo")
    cpu = parse_cpuinfo(cpu_txt)
    ok = cpu.get("cores_detected", 0) >= 1
    hw = cpu.get("Hardware") or cpu.get("Processor") or "unknown"
    results.append(TestResult(
        name="CPU info",
        ok=ok,
        summary=f"Cores: {cpu.get('cores_detected')} | {hw}",
        details=cpu_txt,
        data=cpu
    ))

    # Memory
    mem_txt = shell.run_cmd("cat /proc/meminfo")
    mem = parse_meminfo(mem_txt)
    ma_pct = mem.get("MemAvailable_pct")
    ok = (ma_pct is None) or (ma_pct >= 10.0)
    details = "\n".join([ln for ln in mem_txt.splitlines() if ln.startswith(("MemTotal", "MemAvailable", "MemFree"))])
    results.append(TestResult(
        name="Memory",
        ok=ok,
        summary=f"Total: {mem.get('MemTotal_kB')} kB | Avail: {mem.get('MemAvailable_pct')}%",
        details=details,
        data=mem
    ))

    # Temperature
    temp_paths = [
        "/sys/class/hwmon/hwmon0/temp1_input",
        "/sys/class/thermal/thermal_zone0/temp",
    ]
    temp_c = None
    temp_raw = ""
    used_path = None
    for p in temp_paths:
        out = shell.run_cmd(f"cat {p} 2>/dev/null || true")
        if out and re.search(r"\d", out):
            t = parse_temp_millideg(out)
            if t is not None and abs(t) < 300:
                temp_c = t
                temp_raw = out.strip()
                used_path = p
                break
    ok = (temp_c is None) or (temp_c < 85.0)
    results.append(TestResult(
        name="CPU Temperature",
        ok=ok,
        summary=("Not found" if temp_c is None else f"{temp_c:.1f} °C"),
        details=(f"path: {used_path}\nraw: {temp_raw}" if used_path else "Not found"),
        data={"temp_c": temp_c, "path": used_path}
    ))

    # NAND / MTD
    mtd_txt = shell.run_cmd("cat /proc/mtd || true")
    mtd = parse_proc_mtd(mtd_txt)
    ok = mtd.get("mtd_count", 0) > 0
    results.append(TestResult(
        name="NAND / MTD",
        ok=ok,
        summary=f"MTD partitions: {mtd.get('mtd_count')}",
        details=mtd_txt,
        data=mtd
    ))

    # USB (lsusb)
    lsusb_txt = shell.run_cmd("lsusb 2>/dev/null || echo 'lsusb not available'")
    if "not available" in lsusb_txt.lower():
        lsusb = {"device_count": 0, "devices": []}
        ok = True
    else:
        lsusb = parse_lsusb(lsusb_txt)
        ok = True  # don't fail if nothing plugged
    results.append(TestResult(
        name="USB (lsusb)",
        ok=ok,
        summary=f"Devices seen: {lsusb.get('device_count')}",
        details=lsusb_txt,
        data=lsusb
    ))

    # Network
    ip_txt_brief = shell.run_cmd("ip -brief addr 2>/dev/null || ip addr")
    ip_txt_full = shell.run_cmd("ip addr")
    net = parse_ip_addr_full(ip_txt_full)
    results.append(TestResult(
        name="Network (ip addr)",
        ok=True,
        summary=f"Interfaces: {len(net.get('interfaces', {}))}",
        details=ip_txt_brief.strip(),
        data=net
    ))

    # RTC
    hw_txt = shell.run_cmd("hwclock -r 2>/dev/null || echo 'hwclock not available'")
    rtc_ok = "not available" not in hw_txt.lower()
    results.append(TestResult(
        name="RTC (hwclock -r)",
        ok=rtc_ok,
        summary=("OK" if rtc_ok else "hwclock missing"),
        details=hw_txt,
        data={"raw": hw_txt.strip()}
    ))

    # System
    uname_txt = shell.run_cmd("uname -a")
    up_txt = shell.run_cmd("uptime")
    results.append(TestResult(
        name="System",
        ok=True,
        summary=(uname_txt[:90] + ("..." if len(uname_txt) > 90 else "")),
        details=f"{uname_txt}\n\n{up_txt}",
        data={"uname": uname_txt, "uptime": up_txt}
    ))

    return results


# =========================
# GUI App
# =========================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ECB10 TTL Hardware Tester")
        self.geometry("1100x760")

        self.q = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.current_results: List[TestResult] = []

        # Persistent serial session for command line (connect/disconnect)
        self.shell: Optional[SerialShell] = None

        # ===== Top configuration bar =====
        frm = ttk.Frame(self, padding=10)
        frm.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(frm, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(frm, textvariable=self.port_var, width=35, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky="w", padx=6)

        self.refresh_btn = ttk.Button(frm, text="Refresh", command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=2, padx=(0, 12))

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

        self.run_btn = ttk.Button(frm, text="Run Tests", command=self.on_run_tests)
        self.run_btn.grid(row=0, column=11, padx=(12, 4))

        self.save_btn = ttk.Button(frm, text="Save JSON", command=self.on_save, state=tk.DISABLED)
        self.save_btn.grid(row=0, column=12, padx=4)

        self.status_var = tk.StringVar(value="Idle.")
        ttk.Label(frm, textvariable=self.status_var).grid(row=1, column=0, columnspan=13, sticky="w", pady=(8, 0))

        # ===== Notebook tabs =====
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Tab: Results
        self.tab_results = ttk.Frame(nb)
        nb.add(self.tab_results, text="Results")

        # Tab: Help
        self.tab_help = ttk.Frame(nb)
        nb.add(self.tab_help, text="Help")

        # ===== Results tab layout =====
        pan = ttk.Panedwindow(self.tab_results, orient=tk.HORIZONTAL)
        pan.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        left = ttk.Frame(pan)
        right = ttk.Frame(pan)
        pan.add(left, weight=1)
        pan.add(right, weight=2)

        self.tree = ttk.Treeview(left, columns=("ok", "name", "summary"), show="headings", height=18)
        self.tree.heading("ok", text="OK")
        self.tree.heading("name", text="Test")
        self.tree.heading("summary", text="Summary")
        self.tree.column("ok", width=50, anchor="center")
        self.tree.column("name", width=180, anchor="w")
        self.tree.column("summary", width=360, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<<TreeviewSelect>>", self.on_select_result)

        ttk.Label(right, text="Details / Console Log:").pack(anchor="w")
        self.details = tk.Text(right, wrap=tk.NONE)
        self.details.pack(fill=tk.BOTH, expand=True)

        # ===== Bottom command line (in Results tab) =====
        cmdbar = ttk.Frame(self.tab_results, padding=(0, 8, 0, 0))
        cmdbar.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Label(cmdbar, text="Command:").pack(side=tk.LEFT)
        self.cmd_var = tk.StringVar()
        self.cmd_entry = ttk.Entry(cmdbar, textvariable=self.cmd_var)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.cmd_entry.bind("<Return>", lambda e: self.on_send_command())

        self.send_btn = ttk.Button(cmdbar, text="Send", command=self.on_send_command, state=tk.DISABLED)
        self.send_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.clear_log_btn = ttk.Button(cmdbar, text="Clear Log", command=self.on_clear_log)
        self.clear_log_btn.pack(side=tk.LEFT)

        # ===== Help tab =====
        help_top = ttk.Frame(self.tab_help, padding=8)
        help_top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(help_top, text="Help source:").pack(side=tk.LEFT)
        self.help_source_var = tk.StringVar(value="builtin")
        self.help_source_label = ttk.Label(help_top, textvariable=self.help_source_var)
        self.help_source_label.pack(side=tk.LEFT, padx=6)

        self.reload_help_btn = ttk.Button(help_top, text="Reload Help", command=self.reload_help)
        self.reload_help_btn.pack(side=tk.LEFT, padx=12)

        self.help_text = tk.Text(self.tab_help, wrap=tk.WORD)
        self.help_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Init
        self.refresh_ports()
        self.reload_help()

        # Poll queue
        self.after(100, self.poll_queue)

    # ---------- UI helpers ----------
    def set_status(self, s: str):
        self.status_var.set(s)

    def log(self, s: str):
        self.details.insert(tk.END, s)
        if not s.endswith("\n"):
            self.details.insert(tk.END, "\n")
        self.details.see(tk.END)

    def on_clear_log(self):
        self.details.delete("1.0", tk.END)

    def refresh_ports(self):
        ports = list_com_ports()
        self.port_combo["values"] = ports
        if ports:
            cur = self.port_var.get()
            if cur in ports:
                self.port_combo.current(ports.index(cur))
            else:
                self.port_combo.current(0)
            self.set_status(f"Found {len(ports)} COM port(s).")
        else:
            self.port_var.set("")
            self.set_status("No COM ports found. Plug USB-TTL and press Refresh.")

    def reload_help(self):
        text = load_help_text()
        # Determine which source was used
        if os.path.exists(HELP_MD_PATH):
            src = f"{HELP_MD_PATH}"
        elif os.path.exists(HELP_JSON_PATH):
            src = f"{HELP_JSON_PATH}"
        else:
            src = "builtin"
        self.help_source_var.set(src)

        self.help_text.delete("1.0", tk.END)
        self.help_text.insert(tk.END, text)
        self.help_text.see("1.0")

    def _selected_port_device(self) -> Optional[str]:
        raw = (self.port_var.get() or "").strip()
        if not raw:
            return None
        return raw.split("—")[0].strip()

    def _get_conn_params(self) -> Tuple[str, int, str, str]:
        port = self._selected_port_device()
        if not port:
            raise ValueError("Select COM port first (or press Refresh).")
        try:
            baud = int(self.baud_var.get())
        except Exception:
            raise ValueError("Invalid baud rate.")
        return port, baud, self.user_var.get(), self.pass_var.get()

    def _set_connected_ui(self, connected: bool):
        self.connect_btn.config(state=tk.DISABLED if connected else tk.NORMAL)
        self.disconnect_btn.config(state=tk.NORMAL if connected else tk.DISABLED)
        self.send_btn.config(state=tk.NORMAL if connected else tk.DISABLED)

    # ---------- Connect / Disconnect ----------
    def on_connect(self):
        if self.shell and self.shell.is_open():
            self.set_status("Already connected.")
            return

        try:
            port, baud, user, pwd = self._get_conn_params()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        self.set_status(f"Connecting to {port} @ {baud}...")
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
        self.set_status("Disconnected.")
        self.log("[DISCONNECTED]")

    # ---------- Run tests ----------
    def on_run_tests(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Busy", "Tests are already running.")
            return

        # Use existing connection if present, else do a one-shot connection for tests
        if self.shell and self.shell.is_open():
            sh = self.shell
            self._run_tests_with_shell(sh, close_after=False)
        else:
            try:
                port, baud, user, pwd = self._get_conn_params()
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return

            self.run_btn.config(state=tk.DISABLED)
            self.refresh_btn.config(state=tk.DISABLED)
            self.set_status(f"Connecting for tests to {port} @ {baud}...")

            def worker():
                try:
                    sh = SerialShell(port, baud, user, pwd)
                    sh.open()
                    ok, msg = sh.ensure_shell()
                    self.q.put(("status", msg))
                    if not ok:
                        sh.close()
                        self.q.put(("error", msg))
                        return
                    self.q.put(("run_tests_shell", sh))
                except Exception as e:
                    self.q.put(("error", f"{type(e).__name__}: {e}"))

            self.worker_thread = threading.Thread(target=worker, daemon=True)
            self.worker_thread.start()

    def _run_tests_with_shell(self, sh: SerialShell, close_after: bool):
        self.tree.delete(*self.tree.get_children())
        self.current_results = []
        self.save_btn.config(state=tk.DISABLED)

        self.run_btn.config(state=tk.DISABLED)
        self.refresh_btn.config(state=tk.DISABLED)
        self.set_status("Running tests...")

        def worker():
            try:
                results = build_tests(sh)
                if close_after:
                    sh.close()
                self.q.put(("results", results))
                self.q.put(("status", "Done."))
            except Exception as e:
                try:
                    if close_after:
                        sh.close()
                except Exception:
                    pass
                self.q.put(("error", f"{type(e).__name__}: {e}"))

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    # ---------- Command line ----------
    def on_send_command(self):
        cmd = (self.cmd_var.get() or "").strip()
        if not cmd:
            return
        if not (self.shell and self.shell.is_open()):
            messagebox.showerror("Not connected", "Press Connect first to use the command line.")
            return

        self.cmd_var.set("")  # clear input quickly
        self.send_btn.config(state=tk.DISABLED)

        self.log(f"$ {cmd}")

        def worker():
            try:
                out = self.shell.run_cmd(cmd, timeout=CMD_TIMEOUT_SEC)
                self.q.put(("cmd_out", out))
            except Exception as e:
                self.q.put(("error", f"{type(e).__name__}: {e}"))
            finally:
                self.q.put(("cmd_done", None))

        threading.Thread(target=worker, daemon=True).start()

    # ---------- Save ----------
    def on_save(self):
        if not self.current_results:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            port = self._selected_port_device()
            baud = int(self.baud_var.get())
        except Exception:
            port, baud = None, None

        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "port": port,
            "baud": baud,
            "results": [asdict(r) for r in self.current_results],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Saved", f"Saved to:\n{path}")

    # ---------- Results selection ----------
    def populate(self, results: List[TestResult]):
        for i, r in enumerate(results):
            ok_str = "YES" if r.ok else "NO"
            self.tree.insert("", tk.END, iid=str(i), values=(ok_str, r.name, r.summary))
        if results:
            self.tree.selection_set("0")
            self.on_select_result()

    def on_select_result(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except Exception:
            return
        if idx < 0 or idx >= len(self.current_results):
            return

        r = self.current_results[idx]
        # Write into details box, but don't nuke console log entirely — we show it in the same pane.
        # We'll append a "block" instead.
        self.log("\n" + "=" * 60)
        self.log(f"[{r.name}] OK={r.ok}")
        self.log(r.summary)
        if r.details:
            self.log(r.details)
        if r.data:
            self.log("--- Parsed data (JSON) ---")
            self.log(json.dumps(r.data, ensure_ascii=False, indent=2))
        self.log("=" * 60 + "\n")

    # ---------- Queue polling ----------
    def poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()

                if kind == "status":
                    self.set_status(payload)

                elif kind == "error":
                    self.run_btn.config(state=tk.NORMAL)
                    self.refresh_btn.config(state=tk.NORMAL)
                    self.connect_btn.config(state=tk.NORMAL if not (self.shell and self.shell.is_open()) else tk.DISABLED)
                    self.send_btn.config(state=tk.NORMAL if (self.shell and self.shell.is_open()) else tk.DISABLED)
                    self.set_status("Error.")
                    messagebox.showerror("Error", payload)

                elif kind == "connected":
                    self.shell = payload
                    self._set_connected_ui(True)
                    self.set_status("Connected.")
                    self.log("[CONNECTED] Shell ready.")

                elif kind == "run_tests_shell":
                    sh = payload
                    # one-shot test connection
                    self._run_tests_with_shell(sh, close_after=True)

                elif kind == "results":
                    self.current_results = payload
                    self.populate(payload)
                    self.save_btn.config(state=tk.NORMAL)
                    self.run_btn.config(state=tk.NORMAL)
                    self.refresh_btn.config(state=tk.NORMAL)

                elif kind == "cmd_out":
                    out = payload or ""
                    if out.strip():
                        self.log(out)
                    else:
                        self.log("(no output)")

                elif kind == "cmd_done":
                    # re-enable send button if still connected
                    if self.shell and self.shell.is_open():
                        self.send_btn.config(state=tk.NORMAL)

        except queue.Empty:
            pass

        self.after(100, self.poll_queue)


if __name__ == "__main__":
    App().mainloop()
