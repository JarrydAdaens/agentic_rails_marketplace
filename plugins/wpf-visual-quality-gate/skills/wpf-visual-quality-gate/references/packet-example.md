---
name: packet-example
description: >-
  A filled example of the evaluator packet an implementing agent hands to the
  WPF visual quality gate evaluator, drawn from the gate's origin project.
metadata:
  version: "1.0"
---

# Evaluator Packet — Example

This is a worked example from the gate's origin project (Quota-Tank, a WPF
tray app), for a story that restyled tooltips into width-capped callouts. The
launch, title, and cleanup values are that project's defaults — illustrations
only, never universal defaults.

```text
Task goal
- Restyle shared tooltips as callouts: width-capped, wrapping, with a pointer
  aimed at the owning element.

Expected visible behavior
- Hovering any control with a tooltip shows a callout anchored under the
  element, no wider than 320px, with long text wrapping instead of running
  off-screen, and the pointer touching the hovered element.

Visual launch command
- source\QuotaTank.WPF\bin\Debug\net8.0-windows\QuotaTank.WPF.exe --show-popup

Window title
- Quota-Tank

Interaction path
- 1. Hover the pin button on a provider card (short tooltip).
- 2. Open Settings and hover the Cursor provider's info glyph (the longest
     tooltip in the app, ~450 characters).

Pass criteria
- Short tooltip renders as a callout anchored under the pin button.
- Long tooltip wraps inside the 320px callout with no clipping or overflow.
- The callout pointer visually touches the hovered element in both cases.
- No other visible regression on the popup or Settings screen.

Cleanup command
- Stop-Process -Id (Get-Process | Where-Object { $_.ProcessName -eq 'QuotaTank.WPF' }).Id

Commands already run
- dotnet build source\QuotaTank.sln  (clean)
- dotnet test source\QuotaTank.sln   (223/223 passed)

Files changed
- source\QuotaTank.WPF\Themes\SharedStyles.xaml
```
