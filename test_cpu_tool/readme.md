

---

```
# test_cpu_tool

Lightweight GUI tool for interacting with embedded Linux boards over a shared serial console.
Designed for quick diagnostics and informational tests without making policy decisions.

The tool is intentionally **simple, transparent, and non-destructive**.

---

## Overview

`test_cpu_tool` is a small Python/Tkinter application that connects to an embedded Linux device via a serial console (COM port) and provides:

- A shared interactive shell
- A terminal tab for manual commands
- A CPU test tab with predefined diagnostics
- A minimal, informational RTC (Real-Time Clock) test

The tool **does not try to decide what is “correct”** — it only shows facts and observable states.

---

## Key Principles

- One shared serial connection for all tabs
- No background daemons or hidden logic
- No assumptions about RTC priority, battery presence, or time sources
- BusyBox-friendly (works on minimal embedded systems)
- Explicit output of all executed commands

---

## Application Structure

```

test_cpu_tool/
├── app_main.py        # Main GUI application and tab management
├── shell_executor.py  # Shared serial shell executor
├── terminal_tab.py    # Interactive terminal tab
├── test_cpu_tab.py    # CPU diagnostics and RTC quick test
└── README.md

````

---

## Requirements

- Python 3.8+
- pyserial
- tkinter (usually included with Python on Linux/Windows)

Install dependency:
```bash
pip install pyserial
````

---

## Running the Tool

```bash
python app_main.py
```

---

## Serial Connection Model

* One serial connection is shared across all tabs
* Login/password handling is automatic if prompted
* Prompt detection supports common `#` / `$` shells
* Commands are executed sequentially (thread-safe)

Connection parameters:

* COM port
* Baud rate
* Username (default: `root`)
* Password (optional)

---

## Tabs

### 1. Terminal Tab

Provides a raw interactive shell:

* Manual command entry
* Full command output
* Explicit `OK / FAIL` status
* No interpretation or filtering

This tab is intended for:

* Manual diagnostics
* Quick experiments
* Direct interaction with the target system

---

### 2. Test CPU Tab

Contains predefined informational commands, such as:

* CPU information
* Device model
* Kernel version
* Memory info
* NAND / MTD info
* Uptime and load
* Top snapshot
* Recent dmesg output

All commands are **read-only** and informational.

---

## RTC Quick (Info) Test

The **RTC quick (info)** button performs a minimal, non-opinionated RTC inspection.

### What the test does

1. Detects RTC device presence (`/dev/rtc*`)
2. Reads RTC time
3. Waits and checks whether RTC is ticking
4. Notes if RTC appears to be in reset state (year = 2000)
5. Performs an RTC write/readback test:

   * Uses `hwclock -w` (system → RTC)
   * On BusyBox systems without `--set`, uses a temporary system-time fallback and restores it
6. Shows current system time
7. Detects whether `ntpd` is running
8. Prints a factual summary

### What the test does NOT do

* It does **not** decide whether RTC or system time is “primary”
* It does **not** decide whether a backup battery is present
* It does **not** assume UTC vs local time correctness
* It does **not** persist logs or infer power-loss history

### Important Note (shown in output)

> This test does not confirm presence or absence of a backup battery.
> Confirming VBAT requires full power removal.

This is intentional.

---

## BusyBox Compatibility

Many embedded systems use BusyBox `hwclock`, which often supports only:

* `-r` read RTC
* `-w` write RTC from system time
* `-s` set system time from RTC
* `-u / -l` UTC or local interpretation

The tool detects this and adapts accordingly.

---

## Design Philosophy

This tool follows a strict rule:

> **Show facts, not conclusions.**

Examples:

* “RTC ticking: true” instead of “RTC OK”
* “RTC year = 2000” instead of “battery missing”
* “ntpd detected” instead of “time is correct”

Final interpretation is left to the engineer.

---

## Intended Use

* Board bring-up
* Factory diagnostics
* Engineering validation
* Education and debugging
* Field diagnostics (with caution)

Not intended for:

* Automated pass/fail certification
* Forensic time analysis
* Long-term monitoring

---

## License

Internal / engineering use.
Adapt freely for your projects.

---

## Final Note

If you need:

* a more advanced RTC test,
* time drift analysis,
* boot-time sequencing checks,
* or policy-based decisions,

they belong in a **separate “Time” or “RTC advanced” tab**, not in CPU quick tests.

```

---
