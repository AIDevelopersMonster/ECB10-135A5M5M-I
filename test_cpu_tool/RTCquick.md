

---

````markdown
# RTCquick.md

## RTC Quick (Info) Test

This document describes the **RTC quick (info)** test implemented in the CPU tab of `test_cpu_tool`.

The test is **informational only**.  
It reports observable facts about the RTC and system time without making assumptions or decisions.

---

## Purpose

The RTC quick test is designed to:

- Verify that an RTC device exists
- Check that the RTC is readable and ticking
- Observe whether the RTC calendar appears reset
- Verify that RTC accepts written values
- Show the relationship between RTC, system time, and NTP

The test intentionally **does not**:
- Decide whether a backup battery is present
- Decide which time source is authoritative
- Infer power-loss history
- Enforce UTC or local-time policy

---

## Design Philosophy

**Show facts, not conclusions.**

All results are presented as:
- raw command output
- boolean observations (e.g. “ticking: true”)
- neutral notes

Final interpretation is left to the engineer.

---

## Test Steps (What the Tool Does)

### 1. RTC Device Presence

Command:
```sh
ls -l /dev/rtc*
````

Purpose:

* Verify that an RTC device node exists
* Confirm kernel driver availability

Output example:

```
/dev/rtc -> rtc0
/dev/rtc0
```

---

### 2. Initial RTC Read

Command:

```sh
hwclock -r
```

Purpose:

* Read the current RTC calendar value

Observation:

* The full date/time is printed
* The year is inspected

Special note:

* If the year is `2000`, the RTC calendar **appears reset**
* This typically indicates that the RTC backup domain lost power at some point

No assumption is made about *why* this happened.

---

### 3. RTC Ticking Check

Commands:

```sh
sleep 5
hwclock -r
```

Purpose:

* Verify that RTC time advances

Observation:

* If the second read differs from the first, RTC is ticking
* If not, RTC may not be running or readable

This only confirms **current operation**, not persistence.

---

### 4. RTC Write / Readback Test

Purpose:

* Verify that RTC accepts written values

#### BusyBox-Compatible Method

On most embedded systems, BusyBox `hwclock` does **not** support:

* `--set`
* `--date`

Therefore, the test uses this approach:

1. Save current system time (UTC)
2. Temporarily set system time to a known value
3. Write system time to RTC (`hwclock -u -w`)
4. Read RTC back (`hwclock -r`)
5. Restore original system time
6. Restore RTC from restored system time

This ensures:

* RTC write path is tested
* System time and RTC are returned to their original state

All steps and outputs are printed.

---

### 5. System Time Display

Command:

```sh
date
```

Purpose:

* Show current system time and timezone
* Provide context for RTC comparison

No synchronization or correction is performed here.

---

### 6. NTP Detection

Command:

```sh
ps | grep [n]tpd
```

Purpose:

* Detect whether an NTP daemon is running

Observation:

* Presence of `ntpd` is reported as a fact
* No assumption is made that system time is correct

---

### 7. Summary Output

The test prints a summary block, for example:

```
Summary (facts):
- RTC device present: True
- RTC ticking: True
- RTC year at first read: 2026
- RTC write test set/readback: set_ok=True, readback_ok=True
- NTP daemon detected: True
```

This summary contains **only observable facts**.

---

## What the Test Cannot Determine

### Backup Battery Presence (VBAT)

The test **cannot** confirm whether a backup battery is present or functional.

Reasons:

* RTC may be powered from main VDD
* Residual or standby power may be present
* Large capacitors may sustain RTC operation
* Power may not be fully removed during reboot

### Correct Method to Verify VBAT (Manual)

To confirm backup battery operation:

1. Write time to RTC
2. **Fully remove all external power**
3. Ensure no LEDs or standby power remain
4. Wait sufficiently (30–120 seconds recommended)
5. Reapply power
6. Read RTC time

Only this procedure can confirm VBAT behavior.

---

## Interpretation Guidelines (Non-Normative)

These are **observations**, not decisions:

* RTC year = 2000
  → RTC calendar appears reset at some point

* RTC ticking = true
  → RTC is currently running

* RTC write/readback succeeds
  → RTC accepts writes via driver

* NTP daemon detected
  → System time may be synchronized externally

---

## Why This Test Is Minimal by Design

The RTC quick test lives in the **CPU tab** and is intended to be:

* Fast
* Safe
* Non-invasive
* Always executable

More advanced checks (drift, alarms, boot sequencing, policy decisions) belong in a dedicated **Time / RTC Advanced** section.

---

## Summary

The RTC quick (info) test provides:

* Immediate visibility into RTC state
* BusyBox-compatible verification
* Zero assumptions about system policy
* Honest, reproducible results

It is a **diagnostic snapshot**, not a verdict.

---

## Final Note

If you need:

* authoritative time selection
* drift analysis
* alarm/wakeup testing
* RTC vs NTP arbitration

these should be implemented as **separate, explicit tests**.

Keeping RTC quick informational avoids false conclusions and makes the tool reliable in diverse hardware configurations.

```

---


