# Changelog — claude-as-advisor-guardrail (Cursor host)

Keep this file and `VERSION` in sync with `.cursor-plugin/plugin.json`. This
tree carries only the Cursor host; the Codex host is a separate copy under
`plugins/codex/` and is consult-capable rather than gate-enforcing.

## 1.4.0 — 2026-08-22

- Add `/claude-advisor-install-hooks` and `/claude-advisor-remove-hooks` to
  merge or unmerge this plugin into `~/.cursor/hooks.json` with absolute
  command paths, so Cursor CLI can run the write gate. Sibling hooks and the
  home fence are left in place. Install is idempotent; malformed JSON is
  refused without writing.

## 1.3.3 — 2026-08-22

- Ensure generated advisor JSONC documents both timeout fields directly above
  their values, and regression-test the actual initializer output.

## 1.3.2 — 2026-08-22

- Add `/claude-advisor-timeout` for persisted, validated consult timeout
  changes, accepting numbers, compact English values, `default`, and cancel.
- Make health output show whether the JSONC config exists, its full path, and
  the available manually editable fields.

## 1.3.1 — 2026-08-22

- Replace the misleading Default model menu entry with Haiku, Sonnet, Opus, and
  Fable; mark the current listed model and effort.
- Add model/effort cancellation and the `/claude-advisor-version` skill, which
  prints the installed version plus its version-file timestamp.

## 1.3.0 — 2026-08-22

- Add a persisted `enabled` boolean to the project JSONC config. Disabled means
  the registered hooks early out: no health probe, no protocol injection, and
  no write gate.
- Add `/claude-advisor-enabled` and `/claude-advisor-model` skills plus their
  CLI helpers. They accept ordinary boolean wording, Claude-style model aliases
  or future model IDs, effort names, and compact selections such as `2a`.

## 1.2.0 — 2026-08-20

- Add the `lib/` layer this plugin never had: harness JSONC config
  (`harness/claude-as-advisor-guardrail/cursor-config.json` — `model`, `effort`,
  `consult_timeout_seconds`, `health_timeout_seconds`), session health markers,
  and a bounded health probe.
- Replace the unconditional write gate with the three-state health model
  (`pending` / `online` / `offline`) already used by `codex-as-*`: a session
  whose advisor cannot be reached disarms the gate instead of blocking work.
- Add user-invoked skills `claude-advisor-help`, `claude-advisor-health`, and
  `claude-advisor-init`, matching the `codex-as-advisor-guardrail` trio.
- Add `cli/advisor_health.py` and `cli/advisor_init.py` behind those skills.
- Drive the consult model and effort from config instead of the hardcoded
  `opus` / `high` pair; those remain the defaults.
- Adopt the fuller `windows_runtime.py` (uv discovery, `AGENTIC_RAILS_UV`
  override) already shipping in `codex-as-advisor-guardrail`.
- Add `tests/`, including a BOM-prefixed payload regression for the gate.

## 1.1.0 — Prior

Shell-CLI consult transport (no MCP), BOM-tolerant hook stdin, and a write gate
that denied until a consult succeeded with no health probe behind it.
