---
name: rails-doctor-help
description: >-
  Explain the Agentic Rails Marketplace Doctor, its read-only checks, status
  meanings, and the correct next action. Use when the user asks how to inspect
  or interpret Agentic Rails Cursor marketplace/plugin health.
disable-model-invocation: true
---

# Agentic Rails Marketplace Doctor help

`rails-marketplace-doctor` is the read-only half of Cursor marketplace repair.
It compares the `agentic-rails` marketplace Git checkout with its upstream when
possible, then compares each cached Agentic Rails Cursor plugin payload with the
marketplace commit. Git commit identity is authoritative; version strings and
dates are reporting metadata only.

## Commands

| Command | Purpose |
| --- | --- |
| `/rails-marketplace-doctor` | Full diagnosis, including stale/orphaned payloads and hygiene. |
| `/rails-doctor-health` | Short rerun and overall state. |
| `/rails-doctor-help` | This explanation. |

## Results

- `CURRENT`: the observed payload commit matches the marketplace checkout.
- `STALE`: the payload is pinned to an older commit.
- `ORPHANED`: cache exists for an identifier absent from the current catalogue.
- `MISSING`: a catalogue entry has no observed cache payload.
- `UNKNOWN`: Cursor or Git did not expose enough reliable state.

Doctor does not prove account/project scope from cache files alone. It never
rewrites Cursor state. For stale payloads, try Cursor's normal uninstall and
reinstall path, then rerun Doctor. Cursor's known personal-Git stale-pinning
bug can reproduce the old snapshot; only then consider the explicit,
experimental `/rails-marketplace-surgeon` path.
