---
name: rails-surgeon-help
description: >-
  Explain the experimental Agentic Rails Marketplace Surgeon, its explicit
  mutation workflow, preserved state, and verification requirement. Use when a
  user asks how to repair stale Agentic Rails Cursor plugin cache payloads.
disable-model-invocation: true
---

# Agentic Rails Marketplace Surgeon help

`rails-marketplace-surgeon` is the mutating half of Cursor marketplace repair.
Use it only after `/rails-marketplace-doctor` identifies stale payloads and
Cursor's normal reinstall/update workflow did not resolve them.

## Commands

| Command | Purpose |
| --- | --- |
| `/rails-marketplace-surgeon` | Show the exact planned cache changes. |
| `/rails-surgeon-health` | Check whether the cache has a usable repair shape. |
| `/rails-surgeon-help` | This explanation. |

Surgeon requires an explicit `--apply` runner switch after the user approves
the discovered changes. It updates the Agentic Rails marketplace checkout and
creates latest-commit cache payloads for stale installed plugins. It does not
touch plugin-owned persistent settings, and it does not create backups,
transaction journals, or rollback records.

Cursor's authoritative plugin selection metadata is not fully documented. A
successful filesystem repair is therefore not proof that Cursor selected it.
Always run `/rails-marketplace-doctor` after surgery. If Doctor cannot verify
the expected state, report the final observed state rather than claiming repair.
