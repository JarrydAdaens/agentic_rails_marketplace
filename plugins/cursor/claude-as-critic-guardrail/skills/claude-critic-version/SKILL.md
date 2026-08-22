---
name: claude-critic-version
description: >-
  Print the installed Claude critic Cursor-plugin version and its version-file
  edit timestamp. Use when confirming that a manually copied local plugin update
  actually reached Cursor.
disable-model-invocation: true
---

# Claude critic version

Resolve the installed plugin root and run:

```text
python ./cli/critic_version.py
```

Copy stdout verbatim. It reports `Version is X.Y.Z last edited HH:SS DD-MM-YYYY`.
