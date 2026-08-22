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

# sessionStart toast: this guardrail was picked up and is active.
# Microsoft's registered PowerShell App User Model ID, same on every machine.
$ErrorActionPreference = "Stop"

$PluginRoot = Split-Path -Parent $PSScriptRoot
$PluginName = Split-Path -Leaf $PluginRoot
$PowershellAumid = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

function Read-HookStdin {
    $reader = [System.IO.StreamReader]::new(
        [Console]::OpenStandardInput(),
        [System.Text.UTF8Encoding]::new($false),
        $true)
    try { return $reader.ReadToEnd() }
    finally { $reader.Dispose() }
}

function Read-HookPayload {
    $stdin = Read-HookStdin
    if ([string]::IsNullOrWhiteSpace($stdin)) { return [pscustomobject]@{} }
    $stdin = $stdin.TrimStart([char]0xFEFF)
    try { return $stdin | ConvertFrom-Json }
    catch { return [pscustomobject]@{} }
}

function Get-ProjectRoot($Hook) {
    if ($null -ne $Hook -and $null -ne $Hook.workspace_roots) {
        $roots = @($Hook.workspace_roots)
        if ($roots.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace([string]$roots[0])) {
            return [string]$roots[0]
        }
    }
    if ($null -ne $Hook -and -not [string]::IsNullOrWhiteSpace($Hook.cwd)) {
        return $Hook.cwd
    }
    return (Get-Location).Path
}

function Read-JsonFile($Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $content = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($content)) { return $null }
    try { return $content | ConvertFrom-Json }
    catch { return $null }
}

function Test-ShouldToast($Hook) {
    $root = Get-ProjectRoot $Hook
    $configPath = Join-Path $root "harness/$PluginName/cursor-config.json"
    $config = Read-JsonFile $configPath
    $requireAdopted = ($PluginName -eq "jobs-done-guardrail")

    if ($requireAdopted) {
        if ($null -eq $config -or -not $config.enabled) { return $false }
        $seamRoot = Join-Path $root "harness/jobs-done-guardrail"
        $mode = "enabled"
        if (-not [string]::IsNullOrWhiteSpace($env:AGENTIC_RAILS_EVAL_MODE)) {
            $mode = $env:AGENTIC_RAILS_EVAL_MODE.ToLowerInvariant()
        }
        else {
            $modeFile = Read-JsonFile (Join-Path $seamRoot "eval-mode.json")
            if ($null -ne $modeFile -and $null -ne $modeFile.jobsDoneGuardrail) {
                $mode = ($modeFile.jobsDoneGuardrail.ToString()).ToLowerInvariant()
            }
            elseif ($null -ne $modeFile -and $null -ne $modeFile.railsEvalJobsDone) {
                $mode = ($modeFile.railsEvalJobsDone.ToString()).ToLowerInvariant()
            }
        }
        if ($mode -in @("ask", "plan", "disabled")) { return $false }
        return $true
    }

    if ($null -ne $config -and
        $config.PSObject.Properties.Name -contains "enabled" -and
        -not $config.enabled) {
        return $false
    }
    return $true
}

function Show-OnlineToast {
    $hooksPath = Join-Path $PSScriptRoot "cursor-hooks.json"
    $events = @()
    if (Test-Path -LiteralPath $hooksPath) {
        $raw = Get-Content -LiteralPath $hooksPath -Raw | ConvertFrom-Json
        if ($null -ne $raw.hooks) {
            $events = @($raw.hooks.PSObject.Properties.Name)
        }
    }
    $title = [System.Security.SecurityElement]::Escape("$PluginName is online")
    $bodyText = if ($events.Count -gt 0) { "Active on: " + ($events -join ", ") } else { "Active." }
    $body = [System.Security.SecurityElement]::Escape($bodyText)
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
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($PowershellAumid).Show($toast)
}

try {
    if ($env:PYTEST_CURRENT_TEST -or $env:AGENTIC_RAILS_SKIP_TOAST) { exit 0 }
    $hook = Read-HookPayload
    if (-not (Test-ShouldToast $hook)) { exit 0 }
    Show-OnlineToast
    exit 0
}
catch {
    exit 0
}
