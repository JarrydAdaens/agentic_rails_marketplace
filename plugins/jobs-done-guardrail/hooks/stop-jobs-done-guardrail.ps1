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

# Stop-hook build + test guardrail. Ships in the jobs-done-guardrail plugin and
# runs from the plugin cache; everything project-specific lives in the target
# project's harness/jobs-done-guardrail/ seam folder (config.json, eval-mode.json,
# plus git-ignored runs/ and state/). No seam config means the guardrail is not
# adopted in this project and the hook exits silently.

function Get-RepoRoot {
    $root = (& git rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($root)) {
        return $null
    }

    return $root.Trim()
}

function Read-JsonFile($Path, $Fallback) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $Fallback
    }

    $content = Get-Content -LiteralPath $Path -Raw
    if ([string]::IsNullOrWhiteSpace($content)) {
        return $Fallback
    }

    return $content | ConvertFrom-Json
}

function Get-EvalMode($SeamRoot) {
    if (-not [string]::IsNullOrWhiteSpace($env:AGENTIC_RAILS_EVAL_MODE)) {
        return $env:AGENTIC_RAILS_EVAL_MODE.ToLowerInvariant()
    }

    $modePath = Join-Path $SeamRoot "eval-mode.json"
    $mode = Read-JsonFile $modePath ([pscustomobject]@{ jobsDoneGuardrail = "enabled" })
    if ($null -ne $mode.jobsDoneGuardrail) {
        return ($mode.jobsDoneGuardrail.ToString()).ToLowerInvariant()
    }

    if ($null -ne $mode.railsEvalJobsDone) {
        return ($mode.railsEvalJobsDone.ToString()).ToLowerInvariant()
    }

    return "enabled"
}

function Normalize-Path($Path) {
    return ($Path -replace "\\", "/").Trim()
}

function Get-RelevantChangedFiles($Config) {
    $lines = & git status --porcelain --untracked-files=all
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed while detecting changed files."
    }

    $paths = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.Length -lt 4) {
            continue
        }

        $pathText = $line.Substring(3).Trim()
        if ($pathText.Contains(" -> ")) {
            $pathText = ($pathText -split " -> ")[-1]
        }

        $pathText = $pathText.Trim('"')
        $path = Normalize-Path $pathText
        $extension = [System.IO.Path]::GetExtension($path).ToLowerInvariant()

        if ($Config.excludeExtensions -contains $extension) {
            continue
        }

        if ($Config.includeExtensions -notcontains $extension) {
            continue
        }

        $excluded = $false
        foreach ($excludePath in $Config.excludePaths) {
            if ($path.StartsWith((Normalize-Path $excludePath), [System.StringComparison]::OrdinalIgnoreCase)) {
                $excluded = $true
                break
            }
        }

        if (-not $excluded) {
            $paths.Add($path)
        }
    }

    return $paths | Sort-Object -Unique
}

function Get-FileHashText($Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return "DELETED"
    }

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-TextHash($Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes)) -replace "-", "").ToLowerInvariant()
}

function Join-CommandArguments($Arguments) {
    $escaped = foreach ($argument in @($Arguments)) {
        $text = [string]$argument
        if ($text.Length -eq 0) {
            '""'
        }
        elseif ($text -match '[\s"]') {
            '"' + ($text.Replace('"', '\"')) + '"'
        }
        else {
            $text
        }
    }

    return ($escaped -join " ")
}

function Get-Fingerprint($RepoRoot, $ConfigPath, $ScriptPath, $ChangedFiles) {
    $head = (& git rev-parse HEAD).Trim()
    $parts = New-Object System.Collections.Generic.List[string]
    $parts.Add("HEAD:$head")
    $parts.Add("CONFIG:$(Get-FileHashText $ConfigPath)")
    $parts.Add("SCRIPT:$(Get-FileHashText $ScriptPath)")

    foreach ($path in $ChangedFiles) {
        $fullPath = Join-Path $RepoRoot $path
        $parts.Add("FILE:${path}:$(Get-FileHashText $fullPath)")
    }

    return Get-TextHash ($parts -join "`n")
}

function Invoke-Stage($RepoRoot, $RunPath, $StageName, $StageConfig) {
    $outputPath = Join-Path $RunPath "$StageName-output.txt"
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $StageConfig.command
    $psi.Arguments = Join-CommandArguments $StageConfig.arguments
    $psi.WorkingDirectory = $RepoRoot
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false

    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $combined = @($stdout, $stderr) -join "`n"
    Set-Content -LiteralPath $outputPath -Value $combined -Encoding UTF8

    return [pscustomobject]@{
        Stage = $StageName
        Command = "$($StageConfig.command) $($StageConfig.arguments -join ' ')"
        ExitCode = $process.ExitCode
        OutputPath = $outputPath
    }
}

function Get-TrimmedOutput($Path, $LineLimit) {
    $lines = @(Get-Content -LiteralPath $Path)
    $interesting = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ($line -match "(?i)error|failed|failure|exception|assert|expected|actual") {
            $interesting.Add($line)
        }
    }

    $sourceLines = $interesting
    if ($interesting.Count -eq 0) {
        $sourceLines = $lines
    }

    return ($sourceLines | Select-Object -First $LineLimit) -join "`n"
}

function New-RepairPrompt($StageResult, $RunPath, $LineLimit, $Attempt, $MaxAttempts) {
    $trimmed = Get-TrimmedOutput $StageResult.OutputPath $LineLimit
    $prompt = @(
        "jobs-done-guardrail failed.",
        "",
        "Stage: $($StageResult.Stage)",
        "Command: $($StageResult.Command)",
        "Exit Code: $($StageResult.ExitCode)",
        "Attempt: $Attempt of $MaxAttempts",
        "",
        "Relevant output:",
        "",
        '```text',
        $trimmed,
        '```',
        "",
        "Repair instructions:",
        "",
        "1. Fix only the failure shown above.",
        "2. Do not broaden scope.",
        "3. Do not refactor unrelated code.",
        "4. Do not delete, weaken, or bypass tests unless the test is demonstrably wrong and the implementation plan allows changing it.",
        "5. After fixing, stop. jobs-done-guardrail will run again.",
        "",
        "Full logs:",
        $RunPath
    ) -join "`n"

    $promptPath = Join-Path $RunPath "repair-prompt.md"
    Set-Content -LiteralPath $promptPath -Value $prompt -Encoding UTF8
    return $prompt
}

function Write-Result($RunPath, $Result) {
    $resultPath = Join-Path $RunPath "result.json"
    $Result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding UTF8
}

function Save-State($Path, $State) {
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Write-BlockingOutput($Text, $Hook) {
    if ($Hook.hook_event_name -ceq "stop") {
        Write-Output ([pscustomobject]@{ followup_message = $Text } | ConvertTo-Json -Compress)
        return
    }

    # Claude's Stop hook reads stderr on a blocking exit; Codex reads stdout.
    # Emit to both so one script serves both vendors.
    Write-Output $Text
    [Console]::Error.WriteLine($Text)
}

try {
    $stdin = [Console]::In.ReadToEnd()
    $hook = [pscustomobject]@{}
    if (-not [string]::IsNullOrWhiteSpace($stdin)) {
        try { $hook = $stdin | ConvertFrom-Json } catch { $hook = [pscustomobject]@{} }
    }

    $repoRoot = Get-RepoRoot
    if ($null -eq $repoRoot) {
        exit 0  # not a git repository: the guardrail has nothing to gate here
    }
    Set-Location $repoRoot

    $seamRoot = Join-Path $repoRoot "harness/jobs-done-guardrail"
    $configPath = Join-Path $seamRoot "config.json"
    $scriptPath = $PSCommandPath
    $runRoot = Join-Path $seamRoot "runs"
    $stateRoot = Join-Path $seamRoot "state"
    $statePath = Join-Path $stateRoot "jobs-done-guardrail-state.json"

    $config = Read-JsonFile $configPath $null
    if ($null -eq $config -or -not $config.enabled) {
        exit 0  # no seam config: guardrail not adopted in this project
    }

    New-Item -ItemType Directory -Force -Path $runRoot, $stateRoot | Out-Null

    $mode = Get-EvalMode $seamRoot
    if (($hook.permission_mode -eq "plan") -or ($mode -in @("ask", "plan", "disabled"))) {
        exit 0
    }

    $changedFiles = @(Get-RelevantChangedFiles $config)
    if ($changedFiles.Count -eq 0) {
        exit 0
    }

    $fingerprint = Get-Fingerprint $repoRoot $configPath $scriptPath $changedFiles
    $state = Read-JsonFile $statePath ([pscustomobject]@{})
    if ($mode -ne "force" -and $state.lastFingerprint -eq $fingerprint -and $state.lastResult -eq "passed") {
        exit 0
    }

    $turnId = "unknown"
    if ($null -ne $hook.turn_id) {
        $turnId = $hook.turn_id.ToString()
    }
    elseif ($null -ne $hook.session_id) {
        $turnId = $hook.session_id.ToString()
    }
    elseif ($null -ne $hook.conversation_id) {
        $turnId = $hook.conversation_id.ToString()
    }

    $attemptCount = 0
    if ($state.activeRepairTurnId -eq $turnId) {
        if ($null -ne $state.activeRepairAttemptCount) {
            $attemptCount = [int]$state.activeRepairAttemptCount
        }
    }

    $attempt = $attemptCount + 1
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmmss")
    $runPath = Join-Path $runRoot $timestamp
    New-Item -ItemType Directory -Force -Path $runPath | Out-Null
    Set-Content -LiteralPath (Join-Path $runPath "changed-files.txt") -Value ($changedFiles -join "`n") -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $runPath "fingerprint.txt") -Value $fingerprint -Encoding UTF8

    $started = (Get-Date).ToUniversalTime().ToString("o")
    $buildResult = Invoke-Stage $repoRoot $runPath "build" $config.build
    $commands = @(@{
        stage = "build"
        command = $config.build.command
        arguments = @($config.build.arguments)
        exitCode = $buildResult.ExitCode
        outputPath = "build-output.txt"
    })

    $failedStage = $null
    $stageResult = $null
    if ($buildResult.ExitCode -ne 0) {
        $failedStage = "compile"
        $stageResult = $buildResult
    }

    if ($null -eq $failedStage) {
        $testResult = Invoke-Stage $repoRoot $runPath "test" $config.test
        $commands += @{
            stage = "test"
            command = $config.test.command
            arguments = @($config.test.arguments)
            exitCode = $testResult.ExitCode
            outputPath = "test-output.txt"
        }

        if ($testResult.ExitCode -ne 0) {
            $failedStage = "test"
            $stageResult = $testResult
        }
    }

    if ($null -eq $failedStage) {
        $state = [pscustomobject]@{
            lastFingerprint = $fingerprint
            lastResult = "passed"
            lastStage = "test"
            lastRunPath = Normalize-Path $runPath.Substring($repoRoot.Length + 1)
            lastEvaluatedUtc = (Get-Date).ToUniversalTime().ToString("o")
            activeRepairTurnId = $null
            activeRepairAttemptCount = 0
        }
        Save-State $statePath $state
        Write-Result $runPath ([pscustomobject]@{
            evalId = $config.evalId
            status = "passed"
            stage = "test"
            fingerprint = $fingerprint
            startedUtc = $started
            finishedUtc = (Get-Date).ToUniversalTime().ToString("o")
            commands = $commands
            fullRunPath = Normalize-Path $runPath.Substring($repoRoot.Length + 1)
        })
        exit 0
    }

    $state = [pscustomobject]@{
        lastFingerprint = $fingerprint
        lastResult = "failed"
        lastStage = $failedStage
        lastRunPath = Normalize-Path $runPath.Substring($repoRoot.Length + 1)
        lastEvaluatedUtc = (Get-Date).ToUniversalTime().ToString("o")
        activeRepairTurnId = $turnId
        activeRepairAttemptCount = $attempt
    }
    Save-State $statePath $state

    if ($attempt -gt [int]$config.maxRepairAttempts) {
        $message = "jobs-done-guardrail is blocked after $($config.maxRepairAttempts) repair attempts. Human review required.`nRun path: $(Normalize-Path $runPath.Substring($repoRoot.Length + 1))"
        Write-Result $runPath ([pscustomobject]@{
            evalId = $config.evalId
            status = "blocked"
            stage = "repair-limit"
            fingerprint = $fingerprint
            startedUtc = $started
            finishedUtc = (Get-Date).ToUniversalTime().ToString("o")
            commands = $commands
            fullRunPath = Normalize-Path $runPath.Substring($repoRoot.Length + 1)
        })
        Write-BlockingOutput $message $hook
        if ($hook.hook_event_name -ceq "stop") { exit 0 }
        exit 2
    }

    $repairPrompt = New-RepairPrompt $stageResult (Normalize-Path $runPath.Substring($repoRoot.Length + 1)) $config.outputLineLimit $attempt $config.maxRepairAttempts
    Write-Result $runPath ([pscustomobject]@{
        evalId = $config.evalId
        status = "failed"
        stage = $failedStage
        fingerprint = $fingerprint
        startedUtc = $started
        finishedUtc = (Get-Date).ToUniversalTime().ToString("o")
        commands = $commands
        repairPromptPath = "repair-prompt.md"
        fullRunPath = Normalize-Path $runPath.Substring($repoRoot.Length + 1)
    })

    Write-BlockingOutput $repairPrompt $hook
    if ($hook.hook_event_name -ceq "stop") { exit 0 }
    exit 2
}
catch {
    Write-BlockingOutput "jobs-done-guardrail internal error: $($_.Exception.Message)" $hook
    if ($hook.hook_event_name -ceq "stop") { exit 0 }
    exit 2
}
