# test_{{tool_name}}_tool

Lightweight GUI test tool for embedded Linux boards using a shared serial console.

This project is a **standalone, single-purpose test application** built to develop and validate
one specific test tab in isolation before integrating it into a multi-tab tool.

---

## Purpose

`test_{{tool_name}}_tool` exists to:

- Develop and debug the `{{ToolName}}` test tab independently
- Validate UI, logic, and shell interaction without interference from other tests
- Produce a **self-contained, ready-to-copy test tab** for later integration

Once finalized, the `{{ToolName}}` tab can be copied **as-is** into a multi-tab project.

---

## Design Principles

- One shared serial connection
- One functional test tab + Terminal
- No background services
- No automatic decisions or policy enforcement
- Explicit command execution and visible output
- BusyBox-friendly

The tool **shows facts and results**, not conclusions.

---

## Application Structure

test_{{tool_name}}tool/
├── app_main.py # Main GUI application (Terminal + {{ToolName}} tab)
├── shell_executor.py # Shared serial shell executor
├── terminal_tab.py # Interactive terminal tab
├── test{{tool_name}}_tab.py # {{ToolName}} test tab (primary subject of this project)
└── README.md


---

## `{{ToolName}}` Test Tab

Implemented in:

test_{{tool_name}}_tab.py


### Responsibilities

- Provide a clear and explicit UI for `{{ToolName}}` testing
- Execute shell commands only via the shared `ShellExecutor`
- Avoid hard dependencies on `app_main.py`
- Remain fully portable between projects

---

## Requirements

- Python 3.8+
- pyserial
- tkinter (included with most Python distributions)

Install dependency:
```bash
pip install pyserial
Running the Tool
python app_main.py
Portability & Integration
After the {{ToolName}} tab is finalized:

Copy test_{{tool_name}}_tab.py into a multi-tab project

Add the import in app_main.py

Register the tab in the Notebook

No internal changes to the tab should be required.

