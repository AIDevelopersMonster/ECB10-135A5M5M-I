# ECB10 / ECK10 (STM32MP135) — Practical Builds and Engineering Notes

This repository is a **practical knowledge base and collection of verified builds** for
**ECB10-135A5M5M-I / ECK10-135A5M5M-I boards based on STM32MP135 (Cortex-A7)**.

There is **no copy-paste of official documentation** here.
Only things that actually help when working with this board in **real development and production**.

## Why this repository exists

Vendor documentation is usually:

* fragmented
* focused on “it boots, so it works”
* weak at explaining *why* things behave the way they do and *what happens if you do it wrong*

The goal of this repository is to:

* document **working configurations**
* collect **practical recommendations**
* preserve **pitfalls, limitations, and workarounds**
* explain **how not to kill NAND and avoid boot loops**

## What you will find here

### 🧩 Verified builds

* tested images (SD / NAND)
* working configurations for TF-A / OP-TEE / U-Boot / Kernel
* proven device tree + rootfs combinations
* minimal and **production-friendly** builds

### ⚙️ Boot and memory

* boot modes: SD / NAND / USB
* STM32MP135 boot flow (TF-A → OP-TEE → U-Boot → Linux)
* NAND layout (A/B, metadata, UBI)
* **what you can and cannot write to NAND**

### 🧠 SoC behavior and performance

* real Cortex-A7 behavior @ 650 MHz
* memory: what is actually available and where it goes
* temperature, throttling, watchdog
* power consumption and suspend behavior

### 🔌 Peripherals (without magic)

* UART / RS232 / RS485 / RS422 — no surprises
* CAN / Ethernet / Wi-Fi (AP6212)
* USB Host / OTG (what works and what doesn’t)
* HDMI vs LCD (why they can’t be used simultaneously)
* GPIO, LEDs, RTC

### 🧪 Diagnostics and testing

* useful Linux commands specific to this board
* memory and NAND stress tests
* RTC, watchdog, and power checks
* debugging early boot and startup failures

### 🧨 Pitfalls and limitations

* common beginner mistakes
* “I broke NAND — what now?”
* where documentation is misleading
* things that **look like bugs but are actually features**

## Who this repository is for

* embedded developers
* engineers bringing this board into a product
* anyone tired of digging through PDFs to understand how things really work
* future you, six months from now 😄

## What you will **not** find here

* copies of official PDFs
* “how to install minicom”
* marketing descriptions
* advice like “try rebooting”

## Status

This is a living repository, updated as a result of:

* real development work
* recorded videos
* answering “why does it work like this?”

If you are working with this board — **stars, issues, and PRs are welcome**.

