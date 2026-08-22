---
name: claude-advisor-version
description: >-
  Print the installed Claude advisor Cursor-plugin version and its version-file
  edit timestamp. Use when confirming that a manually copied local plugin update
  actually reached Cursor.
disable-model-invocation: true
---

# Claude advisor version

Resolve the installed plugin root and run:

```text
python ./cli/advisor_version.py
```

Copy stdout verbatim. It reports `Version is X.Y.Z last edited HH:SS DD-MM-YYYY`.
