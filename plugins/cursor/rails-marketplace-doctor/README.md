# rails-marketplace-doctor

Cursor-only, read-only diagnosis for the local `agentic-rails` marketplace.
It explains the two layers Cursor maintains: the marketplace Git checkout and
per-plugin cached payloads pinned to commits. It reports their freshness,
version/date metadata, cache orphaning, basic Claude/Codex reachability, and
installation hygiene.

## Commands

- `/rails-marketplace-doctor` — full report.
- `/rails-doctor-health` — concise health summary.
- `/rails-doctor-help` — usage and interpretation help.

The plugin never changes Cursor state. If it finds the known Cursor
stale-pinning condition, it recommends Cursor's normal reinstall flow first
and identifies `rails-marketplace-surgeon` as the experimental repair option.

## Requirements and limits

The implementation uses Python's standard library and `git` when available.
It discovers `%USERPROFILE%\.cursor` (or `~/.cursor`) and reports `UNKNOWN`
where Cursor has not exposed enough local information. It does not infer an
account-level or project-level plugin enablement state from a cache directory.

No project harness seam is required.
