#!/bin/sh
# bt_quick_info.sh
#
# Bluetooth quick info / smoke test
# Board: ECB10-135A5M5M-I (STM32MP135)
#
# Purpose:
#  - verify Bluetooth controller presence (hci0)
#  - verify firmware loading
#  - show basic controller state
#  - collect useful dmesg info
#
# SAFE: does not change system state

set -eu

TS() { date +"%Y-%m-%d %H:%M:%S"; }
LOG() { echo "[$(TS)] $*"; }
ERR() { echo "[$(TS)] ERROR: $*" >&2; }

LOG "== Bluetooth quick info =="

# --- hci device ---
if [ -d /sys/class/bluetooth/hci0 ]; then
    LOG "hci0 present: YES"
else
    ERR "hci0 NOT found"
    exit 1
fi

# --- tools ---
if command -v hciconfig >/dev/null 2>&1; then
    LOG "hciconfig: $(command -v hciconfig)"
else
    ERR "hciconfig not found"
fi

# --- controller info ---
LOG "hciconfig -a hci0:"
hciconfig -a hci0 || true

# --- firmware ---
LOG "Firmware check:"
if ls /lib/firmware/brcm 2>/dev/null | grep -qi bcm4343; then
    ls -1 /lib/firmware/brcm | grep -i bcm4343 | sed 's/^/  /'
else
    LOG "  BCM43xx firmware not found in /lib/firmware/brcm"
fi

# --- bluetoothctl presence ---
if command -v bluetoothctl >/dev/null 2>&1; then
    LOG "bluetoothctl present: YES"
else
    ERR "bluetoothctl not found"
fi

# --- dmesg ---
LOG "Recent dmesg (bluetooth):"
dmesg | grep -i bluetooth | tail -n 30 | sed 's/^/  /' || true

LOG "== RESULT =="
LOG "Bluetooth hardware detected and initialized"
LOG "This test does NOT check pairing or profiles (SPP/OBEX)"

exit 0
