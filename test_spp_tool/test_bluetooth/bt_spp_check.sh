#!/bin/sh
# bt_spp_check.sh — SPP/RFCOMM kernel capability check (expected FAIL on current image)
#
# Purpose:
#   - Determine whether the current kernel supports Bluetooth SPP (RFCOMM).
#   - This is NOT a pairing test. It is a kernel capability test.
#
# Expected on your current image:
#   - "Protocol not supported"  -> exit 2
#
# Usage:
#   chmod +x bt_spp_check.sh
#   ./bt_spp_check.sh
#
# Exit codes:
#   0  RFCOMM appears supported (PASS)
#   2  RFCOMM not supported ("Protocol not supported") (EXPECTED FAIL)
#   3  rfcomm tool missing
#   4  other/unexpected error

set -eu

TS(){ date +"%Y-%m-%d %H:%M:%S"; }
LOG(){ echo "[$(TS)] $*"; }
ERR(){ echo "[$(TS)] ERROR: $*" >&2; }
have(){ command -v "$1" >/dev/null 2>&1; }

LOG "== Bluetooth SPP (RFCOMM) check =="

if ! have rfcomm; then
  ERR "rfcomm tool not found in userspace."
  exit 3
fi

LOG "rfcomm: $(command -v rfcomm)"

# Try to load rfcomm module (if modular). Not fatal if it fails.
if have modprobe; then
  if modprobe rfcomm >/dev/null 2>&1; then
    LOG "modprobe rfcomm: OK (module loaded or built-in)"
  else
    LOG "modprobe rfcomm: failed (module absent or modules disabled)"
  fi
else
  LOG "modprobe not available; skipping module load attempt."
fi

# Optional: show kernel config hints if available
if [ -r /proc/config.gz ] && have zcat; then
  cfg="$(zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_BT_RFCOMM(=| )|^CONFIG_BT_RFCOMM_TTY(=| )|^# CONFIG_BT_RFCOMM' || true)"
  if [ -n "$cfg" ]; then
    LOG "Kernel config hints (RFCOMM):"
    echo "$cfg" | sed 's/^/[CFG] /'
  else
    LOG "Kernel config: no RFCOMM lines found (may be not enabled)."
  fi
else
  LOG "Kernel config not accessible at /proc/config.gz; skipping."
fi

LOG "RFCOMM control socket test: rfcomm release 0"
tmp="$(mktemp -t rfcomm_err.XXXXXX)"

if rfcomm release 0 >/dev/null 2>"$tmp"; then
  LOG "PASS: RFCOMM control socket available (SPP likely supported)."
  rm -f "$tmp"
  exit 0
fi

msg="$(cat "$tmp" 2>/dev/null || true)"
rm -f "$tmp"

if echo "$msg" | grep -qi "Protocol not supported"; then
  ERR "EXPECTED FAIL: SPP/RFCOMM not supported by current kernel (Protocol not supported)."
  ERR "Next step: kernel rebuild with CONFIG_BT_RFCOMM + CONFIG_BT_RFCOMM_TTY."
  exit 2
fi

ERR "FAIL: unexpected rfcomm error:"
echo "$msg" | sed 's/^/  /' >&2
exit 4
