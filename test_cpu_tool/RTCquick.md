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
