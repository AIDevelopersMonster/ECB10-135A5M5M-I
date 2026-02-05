Purpose of This Document

This document defines the architecture and workflow for a system of test tools based on reusable test tabs.

The core idea is that each test tab is developed as a complete, standalone project, while at the same time remaining fully portable and suitable for integration into a larger multi-test application.

Core Concept: Standalone Tab as a Finished Tool

Each generated project serves two roles at the same time:

1. Standalone Test Tool

A generated project:

test_<name>_tool


is a fully functional application that can be:

launched and used on its own

shared with other engineers

extended and evolved independently

used for real diagnostics and validation

In this mode, the project is a finished tool, not a demo or prototype.

2. Source of a Reusable Test Tab

At the same time, the core test logic inside:

test_<name>_tab.py


is designed to be:

self-contained

independent of the surrounding application

free of hard-coded assumptions

safe to copy without refactoring

This allows the same test tab to be imported or copied into a larger project that combines multiple tests.

Generator Philosophy

The generator creates test tabs, not just projects.

The generated project is intentionally structured so that:

the application (app_main.py) is minimal

the test tab contains the actual value

the tab can live independently of the project that hosts it

In other words:

The project exists to serve the tab.
The tab does not depend on the project.

Dual-Use Design (Important)

Each generated test tab supports two equally important workflows:

Workflow A — Independent Development and Usage

run test_<name>_tool as a standalone application

iterate on UI and logic

debug hardware interaction in isolation

treat the tool as a production-ready utility

Workflow B — Integration into a Multi-Test Tool

copy test_<name>_tab.py into a larger project

import the tab class

register it in a shared Notebook

reuse the same tested logic without modification

No changes inside the tab should be required for integration.

Why This Approach Is Used

This architecture intentionally avoids:

developing tests only inside a large monolithic application

tight coupling between tests

premature integration complexity

Instead, it ensures that:

each test is complete and useful on its own

tests can be combined later without redesign

development remains focused and debuggable

long-term maintenance stays manageable

Resulting Benefits

✔ Each test can be used immediately

✔ Each test can be maintained independently

✔ Integration is mechanical, not creative

✔ The multi-test project becomes a composition of finished tools

✔ No test becomes a “second-class citizen”

Summary (One Sentence)

The generator creates test tabs that are finished standalone tools on one side, and drop-in reusable components for a larger diagnostic system on the other.