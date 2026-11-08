# Project Constitution & Engineering Rules

## 1. Notion Ticket Tracking & 'No Idea Lost' Protocol
- **Single Source of Truth**: All epics, features, bug fixes, and spikes must be tracked in Notion under the project management hub: [kleinanzeigen-hardware-crawler](https://app.notion.com/p/thats-easy/kleinanzeigen-hardware-crawler-2f4d261b913c80c29bbec43b94062846) (`2f4d261b-913c-80c2-9bbe-c43b94062846`).
- **'No Idea Lost' Mandate**: Whenever the user mentions a side-idea, improvement, or future architecture variant in conversation, immediately capture it as a `[Backlog]` ticket in Notion without derailing the active sprint.
- **Ticket Lifecycle**:
  - `Not started` -> `In progress` -> `Verification / QA` -> `Done`.
  - Every completed ticket must be accompanied by automated tests, verification logs, and a semantic git commit referencing the ticket.

## 2. Dev-Logging & Telemetry-First Mandate
- **Logging upfront**: Before any implementation of a plan begins, an analysis of what must be logged (traffic, durations, HTTP response codes, fallback triggers, parsing confidence, browser console errors) is mandatory.
- **Structured Dev-Logging**:
  - Every session must log to structured JSONL (`logging_session.py`).
  - Network traffic, request counts, payload sizes, and cache hits must be monitored continuously (`TrafficMonitor`).
  - Pipeline duration per phase must be tracked with millisecond precision (`PerformanceTimer`).
- **Local Dev Documentation**:
  - Progress must be tracked item by item in `tasks/todo.md`.
  - After every user correction or critical bug fix, update `tasks/lessons.md` with root causes and preventive rules.

## 3. Strict Team Separation (Autonomous Agent Orchestration)
- To maintain context purity and rigorous validation, distinct teams (subagents) must be dispatched:
  1. **Team 1: Planning & Architecture Team**: Analyzes requirements, models domain logic, defines logging and telemetry schemas, and writes precise technical specifications.
  2. **Team 2: Implementation Team**: Strictly separate agent(s) from the planning team. Implements the code, hooks up telemetry, and passes unit/integration tests.
  3. **Team 3: QA Team**: Strictly separate agent from implementation. Must act as an end-user, navigating to real Kleinanzeigen listings, pasting actual ads into the running application via browser automation (Playwright / Windows MCP), and capturing visual screenshot evidence.

## 4. Hardware Integrity & Quality Standards
- **Python Tooling**: Always use `uv` for python environments and execution (`uv run pytest`, `uv run python`).
- **Deterministic First**: Prefer deterministic catalog-based 0ms lookups and regex lookarounds over expensive, slow, non-deterministic LLM calls.
- **Hardware Plausibility**: Never allow physically dangerous or under-specced recommendations (e.g. 400W PSU for an RTX 3080).
- **DOM-First Pricing**: Always pull prices primarily from DOM price nodes; never confuse description text (e.g. "NP war 800€") with current asking price.
