---
name: rails-doctor-health
description: >-
  Rerun the Agentic Rails Marketplace Doctor and report its overall health
  state. Use after a Cursor marketplace refresh, reinstall, or Surgeon attempt.
disable-model-invocation: true
---

# Agentic Rails Marketplace Doctor health retest

Run the same read-only diagnostic as `/rails-marketplace-doctor`:

```text
python ./scripts/marketplace_doctor.py --health
```

Resolve `./` from the installed plugin root. Copy stdout verbatim, then state
the final `HEALTHY`, `DEGRADED`, `BROKEN`, or `UNKNOWN` result plainly. Do not
claim a repair succeeded merely because Surgeon reported success; Doctor is the
independent verifier.
