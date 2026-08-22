---
name: rails-marketplace-surgeon
description: >-
  Inspect and, only with explicit approval, repair stale Agentic Rails Cursor
  marketplace/plugin cache payloads. Use when Doctor identifies stale payloads
  and Cursor's normal reinstall path has failed.
disable-model-invocation: true
---

# Agentic Rails Marketplace Surgeon

Surgeon mutates Cursor's internal marketplace/plugin cache and is experimental.
First run its dry-run and show the output:

```text
python ./scripts/marketplace_surgeon.py
```

Resolve `./` from the installed `rails-marketplace-surgeon` plugin root. Explain
which marketplace checkout and cache payloads would change. Only after the user
explicitly approves this exact cache mutation, run:

```text
python ./scripts/marketplace_surgeon.py --apply
```

Copy stdout verbatim. Do not invent a rollback: Surgeon deliberately creates no
backup or journal. Immediately run `/rails-marketplace-doctor` afterwards and
report its independent result.
