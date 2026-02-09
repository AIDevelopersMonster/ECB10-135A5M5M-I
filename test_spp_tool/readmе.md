

```md
# Bluetooth tests for ECB10-135A5M5M-I (STM32MP135)

This repository contains practical Bluetooth tests and helper tools for the  
**EBYTE ECB10-135A5M5M-I (STM32MP135)** board running Linux.

The goal of this stage is **not full Bluetooth application support**, but:
- verify that Bluetooth hardware is present and initialized
- verify that pairing with a phone works
- clearly document current limitations of the Linux image
- prepare a clean base for future kernel rebuild with full SPP support

---

## Hardware and Bluetooth chip

- Module: **AP6212**
- Bluetooth chipset: **Broadcom BCM43430 / BCM43438 family**
- Interface: **UART (HCI UART, H4 protocol)**
- Firmware loaded from:
```

/lib/firmware/brcm/BCM43430A1.hcd

```

Bluetooth is detected and initialized correctly by the kernel.

---

## What is confirmed to work

✔ Bluetooth controller (`hci0`) is present  
✔ Firmware is loaded  
✔ Bluetooth can be powered on/off  
✔ Device is discoverable  
✔ Phone can see the board  
✔ Pairing with phone works (numeric confirmation)  
✔ Device becomes **Paired** and **Trusted**

---

## What is NOT working (important)

❌ **SPP (Serial Port Profile) is NOT supported in the current build**

Symptoms:
- `rfcomm` exists but fails:
```

rfcomm listen /dev/rfcomm0 1
Can't open RFCOMM control socket: Protocol not supported

```
- Connection from phone is immediately dropped
- No `/dev/rfcomm*` devices appear

This is **expected behavior** for this image.

Reason:
- Required kernel options and modules are missing:
- `CONFIG_BT_RFCOMM`
- `CONFIG_BT_RFCOMM_TTY`
- related BlueZ kernel support

➡ **Fix requires kernel rebuild**  
➡ This will be covered later in a dedicated kernel build stage

---

## Folder structure

```

test_bluetooth/
├── README.md               # this file
├── bt_quick_info.sh        # Bluetooth smoke / info test
├── bt_spp_check.sh         # SPP check (expected FAIL)
├── bt_pairing_notes.md     # pairing logic notes

````

---

## Terminal requirements

Use a **real interactive terminal**, not embedded pseudo-terminals.

Recommended:
- **MobaXterm**
- Linux terminal over SSH
- Serial console (UART)

Avoid:
- limited embedded consoles
- GUI-only wrappers without stdin support

---

## Basic Bluetooth commands (step by step)

### 1. Start bluetoothctl

```sh
bluetoothctl
````

### 2. Enable controller

```text
power on
agent on
default-agent
discoverable on
pairable on
```

Optional (set visible name):

```text
system-alias EBYTE-13x
```

---

### 3. Pairing sequence (IMPORTANT)

**Correct order:**

1. Start pairing from the **phone**
2. Board shows numeric code
3. Type `yes` on the board
4. Confirm on the phone

Example:

```text
[agent] Confirm passkey 498112 (yes/no): yes
```

After that:

* device becomes `Paired: yes`
* device becomes `Trusted: yes`

---

### 4. Verify paired devices

```sh
bluetoothctl paired-devices
```

Example output:

```
Device 1C:F0:XX:XX:XX XXXX
```

---

### 5. Inspect device info

```sh
bluetoothctl info <MAC>
```

Typical output shows many UUIDs (Audio, OBEX, PAN, etc.)
**SPP UUID (00001101)** is missing — this is expected.

---

## Automated smoke test

### Bluetooth info test

```sh
./bt_quick_info.sh info
```

Checks:

* hci0 presence
* firmware
* recent dmesg
* basic controller state

---

### SPP check (expected FAIL)

```sh
./bt_spp_check.sh
```

Expected result:

* clear message that RFCOMM/SPP is not supported
* test marked as **FAIL by design**

This is intentional and documented.

---

## GUI / Notebook integration (current status)

Our Notebook / GUI:

* successfully controls Bluetooth power
* shows pairing state
* demonstrates that:

  * pairing works
  * connection drops due to missing SPP support

This is an **important diagnostic result**, not a bug.

---

## Final conclusion (current stage)

✔ Bluetooth hardware works
✔ Linux sees and initializes Bluetooth
✔ Pairing with phone works
❌ SPP does NOT work in current kernel

➡ This stage is **complete and successful**
➡ Next step: **kernel rebuild with full Bluetooth RFCOMM/SPP support**

This will be addressed in a future video and documentation.

---

## Repository

Project repository:
[https://github.com/AIDevelopersMonster/ECB10-135A5M5M-I](https://github.com/AIDevelopersMonster/ECB10-135A5M5M-I)

---

**Status:**
🟡 Bluetooth partially functional
🟡 SPP intentionally deferred
🟢 Ready for kernel rebuild stage

```

---

