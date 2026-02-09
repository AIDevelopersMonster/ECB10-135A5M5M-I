```md
# bt_spp_check.sh — SPP (RFCOMM) capability check

This document explains what `bt_spp_check.sh` does, why it exists, and how to use it.

---

## Why this test exists

On many embedded Linux images, Bluetooth hardware and pairing can work,
but **SPP (Serial Port Profile)** may still be unavailable because it depends on
kernel RFCOMM support.

This script answers one concrete question:

> **Does the current kernel support RFCOMM/SPP or not?**

---

## What it checks

`bt_spp_check.sh` performs a **kernel capability check**, not a pairing test.

It checks:

- `rfcomm` userspace tool is present
- tries `modprobe rfcomm` (if possible)
- optionally reads `/proc/config.gz` (if available)
- runs a lightweight RFCOMM control socket action:
  - `rfcomm release 0`

If the kernel does not support RFCOMM, `rfcomm` will fail with:

```

Can't open RFCOMM control socket: Protocol not supported

````

---

## Expected result in the current image

✅ Bluetooth is present and pairing works  
❌ **SPP/RFCOMM is NOT supported** (expected FAIL)

So for the current build it is normal that this test reports:

- `Protocol not supported`
- exit code `2`

This is a **documented limitation of the Linux image**, not a hardware fault.

---

## How to run (on the board)

From the `test_bluetooth` directory:

```sh
chmod +x bt_spp_check.sh
./bt_spp_check.sh
echo $?
````

---

## Exit codes

* `0` — RFCOMM appears supported (PASS)
* `2` — RFCOMM not supported by kernel (`Protocol not supported`) (EXPECTED FAIL)
* `3` — `rfcomm` tool missing
* `4` — unexpected error

---

## What to do if it fails with "Protocol not supported"

This is expected for the current image.

To enable SPP later, the kernel must be rebuilt with at least:

* `CONFIG_BT_RFCOMM`
* `CONFIG_BT_RFCOMM_TTY`

After kernel rebuild, **the same script should return PASS** (exit code `0`)
without any changes.

---

## How this fits the project

In the Notebook/GUI this test is used to produce a clear final result:

* pairing proof works
* connection may drop
* SPP check confirms the reason:

  * kernel does not support RFCOMM
* next stage is kernel rebuild

---

## Status

🟡 Current image: EXPECTED FAIL
🟢 After kernel rebuild: should PASS

```
```
