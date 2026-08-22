# Copyright 2026 Jarryd Adaens
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Fire-and-forget Windows toast when a Cursor guardrail is active.

Unpackaged toasts need a registered App User Model ID. This uses Windows'
built-in PowerShell identity, which is the same on every machine.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

# Microsoft's registered identity for Windows PowerShell. Not a session id.
POWERSHELL_AUMID = (
    r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
)
CREATE_NO_WINDOW = 0x08000000


def notify_guardrail_online(plugin_root: Path | None = None) -> None:
    """Fire-and-forget toast. Never raises. No-op off Windows and under pytest."""
    try:
        _notify(plugin_root)
    except Exception:
        return


def _notify(plugin_root: Path | None) -> None:
    if os.name != "nt":
        return
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("AGENTIC_RAILS_SKIP_TOAST"):
        return
    root = plugin_root or Path(__file__).resolve().parents[1]
    events = _hook_events(root)
    title = f"{root.name} is online"
    body = "Active on: " + ", ".join(events) if events else "Active."
    env = os.environ.copy()
    env["AR_TOAST_TITLE"] = title
    env["AR_TOAST_BODY"] = body
    env["AR_TOAST_AUMID"] = POWERSHELL_AUMID
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-Command",
            _POWERSHELL,
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )


def _hook_events(plugin_root: Path) -> list[str]:
    path = plugin_root / "hooks" / "cursor-hooks.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    hooks = raw.get("hooks")
    if not isinstance(hooks, dict):
        return []
    return [str(name) for name in hooks]


_POWERSHELL = r"""
$title = [System.Security.SecurityElement]::Escape($env:AR_TOAST_TITLE)
$body = [System.Security.SecurityElement]::Escape($env:AR_TOAST_BODY)
$aumid = $env:AR_TOAST_AUMID
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime]
$template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>$title</text>
      <text>$body</text>
    </binding>
  </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($aumid).Show($toast)
"""
