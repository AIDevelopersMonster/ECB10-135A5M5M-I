# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import shutil
import sys
import traceback
from pathlib import Path
from datetime import datetime

TEMPLATE_DIRNAME = "test_new_tool"
LOG_FILENAME = "gen_tool.log"


def log(msg: str, log_path: Path):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write(line + "\n")
    except Exception:
        # do not crash on logging
        pass


def sanitize_name(raw: str) -> str:
    s = (raw or "").strip().lower()
    s = s.replace(" ", "_").replace("-", "_")
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("Пустое или недопустимое имя. Пример: gpio, rtc_quick, nand")
    return s


def to_camel(name_snake: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in name_snake.split("_") if part)


def to_upper_words(name_snake: str) -> str:
    specials = {"gpio": "GPIO", "rtc": "RTC", "cpu": "CPU", "nand": "NAND", "usb": "USB", "eth": "ETH"}
    parts = name_snake.split("_")
    out = []
    for p in parts:
        out.append(specials.get(p, p[:1].upper() + p[1:]))
    return " ".join(out)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write_text(p: Path, s: str):
    p.write_text(s, encoding="utf-8")


def list_tree(root: Path) -> list[str]:
    items = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_dir():
            items.append(f"DIR  {rel}")
        else:
            items.append(f"FILE {rel} ({p.stat().st_size} bytes)")
    return items


def patch_text_files(root: Path, mapping: dict[str, str], log_path: Path):
    patched_files = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix == ".py" or p.name.lower() == "readme.md":
            txt = read_text(p)
            before = txt
            for k, v in mapping.items():
                txt = txt.replace(k, v)
            if txt != before:
                write_text(p, txt)
                patched_files += 1
                log(f"PATCH: {p.relative_to(root)}", log_path)
    log(f"Patched files count: {patched_files}", log_path)


def pause():
    try:
        input("\nНажми Enter чтобы закрыть...")
    except Exception:
        pass


def main():
    base_dir = Path(__file__).resolve().parent
    log_path = base_dir / LOG_FILENAME

    # reset log for each run
    try:
        log_path.unlink(missing_ok=True)
    except Exception:
        pass

    log("== Generator started ==", log_path)
    log(f"Script dir: {base_dir}", log_path)

    template_dir = base_dir / TEMPLATE_DIRNAME
    log(f"Template dir: {template_dir}", log_path)

    if not template_dir.is_dir():
        raise FileNotFoundError(
            f"Не найдена папка шаблона: {template_dir}\n"
            f"Она должна лежать рядом со скриптом и называться строго: {TEMPLATE_DIRNAME}"
        )

    log("Template tree:", log_path)
    for line in list_tree(template_dir):
        log("  " + line, log_path)

    raw = input("Введите name вкладки (например gpio, rtc_quick, nand): ").strip()
    name = sanitize_name(raw)

    out_dir = base_dir / f"test_{name}_tool"
    log(f"Target dir: {out_dir}", log_path)

    if out_dir.exists():
        raise FileExistsError(f"Папка уже существует: {out_dir}")

    camel = to_camel(name)
    tool_title = to_upper_words(name)
    tab_module = f"test_{name}_tab"
    tab_class = f"Test{camel}Tab"

    mapping = {
        "{{tool_name}}": name,
        "{{ToolName}}": tool_title,
        "{{tab_module}}": tab_module,
        "{{tab_class}}": tab_class,
    }

    log(f"Resolved name: {name}", log_path)
    log(f"ToolName:      {tool_title}", log_path)
    log(f"tab_module:    {tab_module}", log_path)
    log(f"tab_class:     {tab_class}", log_path)

    log(f"Ensure parent dir exists: {out_dir.parent}", log_path)
    out_dir.parent.mkdir(parents=True, exist_ok=True)

    # --- write permission test ---
    try:
        test_dir = out_dir.parent / "__write_test__"
        test_file = test_dir / "t.txt"
        log(f"Write test: creating {test_dir}", log_path)
        test_dir.mkdir(parents=True, exist_ok=True)
        log(f"Write test: writing {test_file}", log_path)
        test_file.write_text("ok", encoding="utf-8")
        log("Write test: OK", log_path)
        test_file.unlink(missing_ok=True)
        test_dir.rmdir()
    except Exception as e:
        log(f"Write test: FAIL: {e}", log_path)
        raise

    log("Copy template -> target ...", log_path)
    shutil.copytree(template_dir, out_dir)
    log("Copy done.", log_path)

    # verify copy
    log("Target tree after copy:", log_path)
    for line in list_tree(out_dir):
        log("  " + line, log_path)

    src_tab = out_dir / "test_new_tab.py"
    dst_tab = out_dir / f"test_{name}_tab.py"

    log(f"Expecting tab template: {src_tab}", log_path)
    if not src_tab.exists():
        raise FileNotFoundError(
            f"В скопированной папке нет test_new_tab.py: {src_tab}\n"
            f"Проверь, что в шаблоне файл называется строго test_new_tab.py"
        )

    log(f"Rename tab: {src_tab.name} -> {dst_tab.name}", log_path)
    src_tab.rename(dst_tab)

    log("Patch placeholders in .py and README.md ...", log_path)
    patch_text_files(out_dir, mapping, log_path)

    # check for leftover placeholders
    leftovers = []
    for p in out_dir.rglob("*"):
        if p.is_file() and (p.suffix == ".py" or p.name.lower() == "readme.md"):
            txt = read_text(p)
            if "{{" in txt and "}}" in txt:
                leftovers.append(str(p.relative_to(out_dir)))
    if leftovers:
        log("WARNING: leftover placeholders found in:", log_path)
        for x in leftovers:
            log("  " + x, log_path)

    log("DONE ✅", log_path)
    log(f"Created project: {out_dir}", log_path)
    log("Run:", log_path)
    log(f"  cd {out_dir.name}", log_path)
    log("  python app_main.py", log_path)

    print(f"\nЛог сохранён в файл: {log_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        base_dir = Path(__file__).resolve().parent
        log_path = base_dir / LOG_FILENAME
        log("ERROR ❌ " + str(e), log_path)
        log("--- traceback ---", log_path)
        traceback.print_exc()
        try:
            with log_path.open("a", encoding="utf-8", errors="ignore") as f:
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass
        print(f"\nЛог сохранён в файл: {log_path}")
        pause()
        sys.exit(1)

    pause()
