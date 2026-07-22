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

# PreToolUse guardrail for the Bash tool. Denies any command that invokes a
# python/pip interpreter directly instead of through uv, so Python work stays
# inside isolated, uv-managed environments rather than mutating a shared global
# interpreter. Pure pattern match, no LLM judgment.
#
# Ships in the python-uv-guardrail plugin and runs from the plugin cache. The
# guardrail is active by default wherever the plugin is enabled; an optional
# per-project escape hatch lives in the target project's
# harness/python-uv-guardrail/config.json seam (absent means "enforce with
# defaults"). Any internal error fails OPEN (exit 0) so a hook bug can never
# block every Bash command.

# Interpreter/installer basenames that must be run under uv. python, python3,
# python3.12, pip, pip3, and the Windows "py" launcher are all pollution paths.
$DefaultBlocked = "^(py|python(\d+(\.\d+)?)?|pip\d*)$"

# Leading tokens that mean "this segment is already delegated to uv".
$UvPrefixes = @("uv", "uvx")

# Wrapper commands to skip past so `sudo python`, `env FOO=bar python`, and
# `time python` are still caught on the real executable behind them.
$Wrappers = @("sudo", "env", "time", "nice", "command", "exec", "builtin", "\")

function Read-HookPayload {
    $stdin = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($stdin)) {
        return $null
    }

    try {
        return $stdin | ConvertFrom-Json
    }
    catch {
        return $null  # malformed payload: fail open
    }
}

function Get-ProjectConfig($Hook) {
    $projectRoot = $null
    if ($null -ne $Hook -and -not [string]::IsNullOrWhiteSpace($Hook.cwd)) {
        $projectRoot = $Hook.cwd
    }
    else {
        $projectRoot = (Get-Location).Path
    }

    $configPath = Join-Path $projectRoot "harness/python-uv-guardrail/config.json"
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
        return $null  # malformed config: treat as absent, enforce with defaults
    }
}

function Get-Segments($Command) {
    # Break a compound command into simple-command segments on the shell control
    # operators, so a bare python anywhere in the chain (piped, chained, or in a
    # subshell) is inspected as its own leading command.
    return [regex]::Split($Command, '\|\||&&|;|\||&|\r?\n|\(|\)')
}

function Get-LeadingExecutable($Segment) {
    $tokens = @($Segment -split '\s+' | Where-Object { $_ -ne "" })
    $i = 0
    while ($i -lt $tokens.Count) {
        $token = $tokens[$i]
        if ($token -match '^[A-Za-z_][A-Za-z0-9_]*=') {
            $i++  # inline environment assignment (VAR=value)
            continue
        }
        if ($Wrappers -contains $token) {
            $i++  # wrapper command; the real executable follows
            continue
        }
        break
    }

    if ($i -ge $tokens.Count) {
        return $null
    }

    return $tokens[$i]
}

function Get-Basename($Executable) {
    $leaf = $Executable -replace '.*[\\/]', ''  # strip any directory path
    return ($leaf -replace '(?i)\.exe$', '')    # strip a Windows .exe suffix
}

function Find-BareInterpreter($Command, $BlockedPattern) {
    foreach ($segment in Get-Segments $Command) {
        $exe = Get-LeadingExecutable $segment
        if ($null -eq $exe) {
            continue
        }

        if ($UvPrefixes -contains $exe.ToLowerInvariant()) {
            continue  # already delegated to uv
        }

        if ((Get-Basename $exe) -imatch $BlockedPattern) {
            return $exe
        }
    }

    return $null
}

function Deny($Executable) {
    $reason = "python-uv-guardrail: '$Executable' was invoked directly, without uv. " +
        "Re-run it through uv so it uses an isolated, project-scoped environment instead " +
        "of mutating a shared global interpreter. For example: 'uv run python <args>', " +
        "'uv run <script>.py', 'uv pip install <pkg>', or 'uvx <tool>'. Then retry."

    $output = [pscustomobject]@{
        hookSpecificOutput = [pscustomobject]@{
            hookEventName            = "PreToolUse"
            permissionDecision       = "deny"
            permissionDecisionReason = $reason
        }
    }

    Write-Output ($output | ConvertTo-Json -Depth 4 -Compress)
}

try {
    $hook = Read-HookPayload
    if ($null -eq $hook) {
        exit 0
    }

    $command = $hook.tool_input.command
    if ([string]::IsNullOrWhiteSpace($command)) {
        exit 0  # nothing to inspect
    }

    $blockedPattern = $DefaultBlocked
    $allowCommands = @()

    $config = Get-ProjectConfig $hook
    if ($null -ne $config) {
        if ($config.PSObject.Properties.Name -contains "enabled" -and -not $config.enabled) {
            exit 0  # guardrail disabled in this project
        }
        if ($null -ne $config.blockedPattern -and -not [string]::IsNullOrWhiteSpace($config.blockedPattern)) {
            $blockedPattern = $config.blockedPattern
        }
        if ($null -ne $config.allowCommands) {
            $allowCommands = @($config.allowCommands)
        }
    }

    foreach ($pattern in $allowCommands) {
        if (-not [string]::IsNullOrWhiteSpace($pattern) -and $command -imatch $pattern) {
            exit 0  # explicitly allowlisted by the project
        }
    }

    $offender = Find-BareInterpreter $command $blockedPattern
    if ($null -ne $offender) {
        Deny $offender
    }

    exit 0
}
catch {
    exit 0  # internal error: fail open so the guardrail never blocks all Bash
}
