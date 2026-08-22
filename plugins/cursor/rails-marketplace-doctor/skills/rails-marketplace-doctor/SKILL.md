---
name: rails-marketplace-doctor
description: >-
  Diagnose the local Agentic Rails Cursor marketplace and plugin cache without
  changing Cursor state. Use when Cursor plugins appear stale, missing,
  duplicated, or inconsistent after a marketplace update.
disable-model-invocation: true
---

# Agentic Rails Marketplace Doctor

Run the bundled diagnostic and present its output verbatim. This is read-only:
do not substitute cache deletion, reinstall commands, or Surgeon mutations.

```text
python ./scripts/marketplace_doctor.py
```

Resolve `./` from the installed `rails-marketplace-doctor` plugin root. If
`python` is unavailable, use `py -3` on Windows. Explain that `UNKNOWN` is an
intentional result where Cursor does not expose trustworthy local state.
