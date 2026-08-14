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

$ErrorActionPreference = "Stop"

# Cursor-only fence: deny agent access under Claude Code's home tree
# (%USERPROFILE%\.claude / ~/.claude). Pure path/text match, no LLM judgment.
# Ships in claude-home-fence-guardrail and as the user-level ~/.cursor hook.

$DenyReason = "claude-home-fence-guardrail: access to ~/.claude is banned in Cursor. " +
    "Use Cursor-native skills/plugins under ~/.cursor or the agentic_rails_tooling / " +
    "marketplace sources instead. Do not read, grep, glob, or shell into Claude Code's home."

$SessionPolicy = "HARD POLICY (claude-home-fence-guardrail): Do not read, grep, glob, write, " +
    "delete, or shell into ~/.claude (Claude Code's home: skills, plugins, agents, rules, cache). " +
    "Those paths are banned in Cursor. Prefer ~/.cursor skills/plugins, workspace sources, " +
    "or agentic_rails_tooling / agentic_rails_marketplace. If a listed skill path is under " +
    "~/.claude, ignore it and use a Cursor-native equivalent."

function Read-HookPayload {
    $stdin = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($stdin)) {
        return $null
    }
    try {
        return $stdin | ConvertFrom-Json
    }
    catch {
        return $null
    }
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

function Get-GuardConfig($Root) {
    $configPath = Join-Path $Root "harness/claude-home-fence-guardrail/config.json"
    if (-not (Test-Path -LiteralPath $configPath)) {
        return $null
    }
    $content = Get-Content -LiteralPath $configPath -Raw
    if ([string]::IsNullOrWhiteSpace($content)) {
        return $null
    }
    try {
        return $content | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Test-ConfigDisabled($Config) {
    return ($null -ne $Config -and
            $Config.PSObject.Properties.Name -contains "enabled" -and
            -not $Config.enabled)
}

function Get-BlockedRoot {
    $profileRoot = $env:USERPROFILE
    if ([string]::IsNullOrWhiteSpace($profileRoot)) {
        $profileRoot = $env:HOME
    }
    if ([string]::IsNullOrWhiteSpace($profileRoot)) {
        return $null
    }
    try {
        return [System.IO.Path]::GetFullPath((Join-Path $profileRoot ".claude"))
    }
    catch {
        return (Join-Path $profileRoot ".claude")
    }
}

function Normalize-PathText([string]$PathText) {
    if ([string]::IsNullOrWhiteSpace($PathText)) {
        return $null
    }
    $trimmed = $PathText.Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        return $null
    }
    return ($trimmed -replace '/', '\')
}

function Test-PathUnderClaudeHome([string]$Candidate, [string]$BlockedRoot) {
    if ([string]::IsNullOrWhiteSpace($Candidate) -or [string]::IsNullOrWhiteSpace($BlockedRoot)) {
        return $false
    }

    $normalized = Normalize-PathText $Candidate
    if ($null -eq $normalized) {
        return $false
    }

    # Expand common home/Claude placeholders before rooted checks.
    $expanded = $normalized
    $userProfile = Normalize-PathText $env:USERPROFILE
    $homeEnv = Normalize-PathText $env:HOME
    if (-not [string]::IsNullOrWhiteSpace($userProfile)) {
        $expanded = $expanded -replace '(?i)%USERPROFILE%', $userProfile
        $expanded = $expanded -replace '(?i)\$env:USERPROFILE', $userProfile
        $expanded = $expanded -replace '(?i)\$\{env:USERPROFILE\}', $userProfile
    }
    if (-not [string]::IsNullOrWhiteSpace($homeEnv)) {
        $expanded = $expanded -replace '(?i)\$HOME', $homeEnv
        $expanded = $expanded -replace '(?i)\$\{HOME\}', $homeEnv
    }
    if ($expanded.StartsWith('~\', [System.StringComparison]::Ordinal) -or
        $expanded.StartsWith('~/', [System.StringComparison]::Ordinal) -or
        $expanded -eq '~') {
        $homeRoot = if (-not [string]::IsNullOrWhiteSpace($userProfile)) { $userProfile } else { $homeEnv }
        if (-not [string]::IsNullOrWhiteSpace($homeRoot)) {
            if ($expanded -eq '~') {
                $expanded = $homeRoot
            }
            else {
                $expanded = Join-Path $homeRoot $expanded.Substring(2)
            }
        }
    }

    $blockedNorm = (Normalize-PathText $BlockedRoot).TrimEnd('\')
    if ($expanded -ieq $blockedNorm -or $expanded -ieq ($blockedNorm + '\')) {
        return $true
    }

    if (-not [System.IO.Path]::IsPathRooted($expanded)) {
        # Relative paths are not Claude-home unless they literally target .claude as a segment
        # after expansion failed; treat unresolved relatives as not under the fence.
        return $false
    }

    try {
        $full = [System.IO.Path]::GetFullPath($expanded)
    }
    catch {
        $full = $expanded
    }

    $fullNorm = (Normalize-PathText $full).TrimEnd('\')
    if ($fullNorm -ieq $blockedNorm) {
        return $true
    }
    $prefix = $blockedNorm + '\'
    return $fullNorm.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-TextReferencesClaudeHome([string]$Text) {
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }
    # Explicit Claude-home markers only — avoid matching workspace CLAUDE.md or prose.
    $patterns = @(
        '(?i)(^|[\\/\s"''`(=])~[\\/]\.claude([\\/]|$)',
        '(?i)%USERPROFILE%[\\/]\.claude([\\/]|$)',
        '(?i)\$env:USERPROFILE[\\/]\.claude([\\/]|$)',
        '(?i)\$\{env:USERPROFILE\}[\\/]\.claude([\\/]|$)',
        '(?i)\$HOME[\\/]\.claude([\\/]|$)',
        '(?i)\$\{HOME\}[\\/]\.claude([\\/]|$)',
        '(?i)[A-Za-z]:[\\/]Users[\\/][^\\/\s"''`]+[\\/]\.claude([\\/]|$)',
        '(?i)/Users/[^\\/\s"''`]+/\.claude([\\/]|$)',
        '(?i)/home/[^\\/\s"''`]+/\.claude([\\/]|$)'
    )
    foreach ($pattern in $patterns) {
        if ($Text -match $pattern) {
            return $true
        }
    }
    return $false
}

function Get-ToolInputObject($Hook) {
    if ($null -eq $Hook) {
        return $null
    }
    $input = $Hook.tool_input
    if ($null -eq $input) {
        return $null
    }
    if ($input -is [string]) {
        try {
            return $input | ConvertFrom-Json
        }
        catch {
            return $null
        }
    }
    return $input
}

function Collect-CandidatePaths($Hook) {
    $paths = New-Object System.Collections.Generic.List[string]

    if ($null -ne $Hook -and -not [string]::IsNullOrWhiteSpace($Hook.file_path)) {
        $paths.Add([string]$Hook.file_path)
    }

    $toolInput = Get-ToolInputObject $Hook
    if ($null -ne $toolInput) {
        foreach ($name in @(
                "path", "file_path", "target_directory", "working_directory",
                "target_notebook", "notebook_path"
            )) {
            if ($toolInput.PSObject.Properties.Name -contains $name) {
                $value = [string]$toolInput.$name
                if (-not [string]::IsNullOrWhiteSpace($value)) {
                    $paths.Add($value)
                }
            }
        }
    }

    return @($paths)
}

function Get-ShellCommand($Hook) {
    if ($null -eq $Hook) {
        return $null
    }
    if (-not [string]::IsNullOrWhiteSpace($Hook.command)) {
        return [string]$Hook.command
    }
    $toolInput = Get-ToolInputObject $Hook
    if ($null -ne $toolInput -and ($toolInput.PSObject.Properties.Name -contains "command")) {
        $value = [string]$toolInput.command
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }
    return $null
}

function Emit-Deny($Hook) {
    $event = ""
    if ($null -ne $Hook -and -not [string]::IsNullOrWhiteSpace($Hook.hook_event_name)) {
        $event = [string]$Hook.hook_event_name
    }

    if ($event -ceq "beforeReadFile" -or $event -ceq "beforeTabFileRead") {
        $output = [pscustomobject]@{
            permission   = "deny"
            user_message = $DenyReason
        }
    }
    elseif ($event -ceq "beforeShellExecution" -or $event -ceq "preToolUse") {
        $output = [pscustomobject]@{
            permission    = "deny"
            user_message  = $DenyReason
            agent_message = $DenyReason
        }
    }
    else {
        # Default Cursor deny shape for any other gating event.
        $output = [pscustomobject]@{
            permission    = "deny"
            user_message  = $DenyReason
            agent_message = $DenyReason
        }
    }

    Write-Output ($output | ConvertTo-Json -Depth 4 -Compress)
}

function Emit-SessionPolicy {
    $output = [pscustomobject]@{
        additional_context = $SessionPolicy
    }
    Write-Output ($output | ConvertTo-Json -Depth 4 -Compress)
}

function Test-IsReadGate($Hook) {
    if ($null -eq $Hook -or [string]::IsNullOrWhiteSpace($Hook.hook_event_name)) {
        return $false
    }
    $event = [string]$Hook.hook_event_name
    return ($event -ceq "beforeReadFile" -or $event -ceq "beforeTabFileRead")
}

$hook = $null
try {
    $hook = Read-HookPayload
    if ($null -eq $hook) {
        # Malformed/empty: fail closed only for read gates when Cursor sets failClosed.
        exit 0
    }

    $event = [string]$hook.hook_event_name

    if ($event -ceq "sessionStart") {
        Emit-SessionPolicy
        exit 0
    }

    $root = Get-ProjectRoot $hook
    $config = Get-GuardConfig $root
    if (Test-ConfigDisabled $config) {
        exit 0
    }

    $blockedRoot = Get-BlockedRoot
    if ([string]::IsNullOrWhiteSpace($blockedRoot)) {
        exit 0
    }

    foreach ($candidate in Collect-CandidatePaths $hook) {
        if (Test-PathUnderClaudeHome $candidate $blockedRoot) {
            Emit-Deny $hook
            exit 0
        }
    }

    $command = Get-ShellCommand $hook
    if (-not [string]::IsNullOrWhiteSpace($command)) {
        if (Test-TextReferencesClaudeHome $command) {
            Emit-Deny $hook
            exit 0
        }

        # Also catch absolute expanded paths embedded in the command.
        $tokenPattern = '(?i)(%USERPROFILE%|\$env:USERPROFILE|\$\{env:USERPROFILE\}|\$HOME|\$\{HOME\}|~|[A-Za-z]:[\\/][^\s"''`]+|/[^\s"''`]+)'
        $tokenHits = [regex]::Matches($command, $tokenPattern)
        foreach ($match in $tokenHits) {
            if (Test-PathUnderClaudeHome $match.Value $blockedRoot) {
                Emit-Deny $hook
                exit 0
            }
        }
    }

    exit 0
}
catch {
    if (Test-IsReadGate $hook) {
        exit 2
    }
    exit 0
}
