Ок, вот **готовый `bt_pairing_notes.md`** — короткий, инженерный и идеально подходящий **и для GitHub, и для показа в видео/Notebook**.
Без лишнего, с акцентом на **правильный порядок действий и типичные ошибки**.

Можно **класть в репозиторий как есть**.

---

````md
# Bluetooth pairing notes (ECB10-135A5M5M-I)

This document describes the **correct and tested Bluetooth pairing procedure**
for the ECB10-135A5M5M-I board using a **real terminal**
(MobaXterm, SSH, or serial console).

This is a **manual pairing process** intended for diagnostics and validation.

---

## Requirements

- Bluetooth hardware initialized (`hci0` present)
- `bluetoothctl` available
- Use a **real interactive terminal**
  - ✔ MobaXterm
  - ✔ SSH terminal
  - ✔ UART serial console
  - ✖ limited embedded pseudo-terminals

---

## Step 1 — Start bluetoothctl

```sh
bluetoothctl
````

---

## Step 2 — Prepare controller on the board

Inside `bluetoothctl`:

```text
power on
agent on
default-agent
discoverable-timeout 0
pairable-timeout 0
discoverable on
pairable on
```

Optional (set readable device name):

```text
system-alias EBYTE-13x
```

Expected:

* Controller powered on
* Device visible for pairing
* Agent ready to confirm passkey

---

## Step 3 — Start pairing from the phone

On the phone:

* Enable Bluetooth
* Search for devices
* Select **EBYTE-13x**

⚠ **IMPORTANT**
Pairing must be initiated **from the phone**, not from the board.

---

## Step 4 — Confirm passkey (CRITICAL STEP)

On the board you will see something like:

```text
[agent] Confirm passkey 498112 (yes/no):
```

✅ Correct action:

```text
yes
```

❌ Wrong actions:

* typing the digits (`498112`)
* pressing Enter without typing `yes`

After this, confirm pairing on the phone.

---

## Step 5 — Verify pairing result

Exit `bluetoothctl` or in another shell run:

```sh
bluetoothctl paired-devices
```

Expected output:

```text
Device XX:XX:XX:XX:XX:XX <PHONE_NAME>
```

---

## Step 6 — Trust the device (recommended)

Inside `bluetoothctl`:

```text
trust XX:XX:XX:XX:XX:XX
```

Verify:

```text
trusted-devices
```

Result:

* Device marked as trusted
* No passkey confirmation needed next time

---

## Expected behavior after pairing

* Device shows:

  * `Paired: yes`
  * `Trusted: yes`
* Phone may briefly show **“Connected”** and then disconnect

This is **EXPECTED** for the current Linux image.

Reason:

* No active Bluetooth profile (SPP / OBEX) is available on the board
* Phone disconnects because there is no service to use

This is **not a pairing error**.

---

## Common mistakes

* ❌ Trying to connect without pairing
* ❌ Typing the numeric passkey instead of `yes`
* ❌ Using non-interactive terminal
* ❌ Expecting stable connection without SPP/OBEX support

---

## Current limitation (important)

* **SPP / RFCOMM is NOT supported** in the current kernel
* `rfcomm` reports:

  ```
  Protocol not supported
  ```

This will be addressed later during **kernel rebuild**.

---

## Status

✔ Pairing verified
✔ Trusted device works
✔ Connection drop is expected
🟡 Ready for next stage: kernel rebuild with full SPP support

```

