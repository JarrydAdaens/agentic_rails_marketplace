# Changelog — local-advisor-guardrail (Cursor host)

## 3.0.1 — 2026-08-22

- Toast on sessionStart after the project config loads, using PowerShell's
  registered App User Model ID. Disabled projects (`enabled: false`) stay silent.

## 3.0.0 — 2026-08-22

- Replace the MCP-launched second CLI process with bundled native Cursor custom
  subagents and a `postToolUse` consultation marker.
- Add persistent enablement, model, timeout, health, init, help, and version
  controls. Cursor owns per-model effort defaults.
