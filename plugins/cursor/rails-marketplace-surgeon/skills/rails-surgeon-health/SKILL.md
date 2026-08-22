---
name: rails-surgeon-health
description: >-
  Check whether the local Agentic Rails Cursor marketplace/cache layout is
  discoverable and safe enough for an explicit Surgeon repair attempt. Use
  before approving a marketplace cache mutation.
disable-model-invocation: true
---

# Agentic Rails Marketplace Surgeon health check

Run Surgeon in dry-run mode:

```text
python ./scripts/marketplace_surgeon.py
```

Resolve `./` from the installed plugin root. Copy stdout verbatim. A healthy
result must identify an `agentic-rails` marketplace Git checkout, resolve an
upstream commit, and enumerate any stale cache payloads without mutating them.
If the runner reports `UNSAFE` or `UNKNOWN`, do not run `--apply`; report the
specific missing evidence.
