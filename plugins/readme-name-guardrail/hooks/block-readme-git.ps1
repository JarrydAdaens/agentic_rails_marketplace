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
. "$PSScriptRoot/readme-guard-common.ps1"

# PreToolUse guardrail on the Bash tool. Inspects `git add` and `git commit`
# commands and denies any that would stage or commit a forbidden readme.md (a
# readme.md anywhere but the repository root). The Write hook is the primary
# guard against creation; this is the backstop for readmes created outside the
# agent, or before the plugin was installed. Any internal error fails OPEN.

# Leading tokens to skip past so `sudo git ...`, `env FOO=bar git ...`, and
# `time git ...` are still recognized as git invocations.
$Wrappers = @("sudo", "env", "time", "nice", "command", "exec", "builtin", "\")

function Get-Segments($Command) {
    # Break a compound command into simple-command segments on shell control
    # operators, so a git call anywhere in the chain is inspected on its own.
    return [regex]::Split($Command, '\|\||&&|;|\||&|\r?\n|\(|\)')
}

function Get-GitInvocation($Segment) {
    # Parse one segment into @{ RepoDir; Sub; Args } when it is a git call, else
    # $null. Honors the `-C <dir>` global option; skips other global options.
    $tokens = @($Segment -split '\s+' | Where-Object { $_ -ne "" })
    $i = 0
    while ($i -lt $tokens.Count) {
        $t = $tokens[$i]
        if ($t -match '^[A-Za-z_][A-Za-z0-9_]*=') { $i++; continue }  # VAR=value
        if ($Wrappers -contains $t) { $i++; continue }
        break
    }
    if ($i -ge $tokens.Count) { return $null }

    $exe = ($tokens[$i] -replace '.*[\\/]', '') -replace '(?i)\.exe$', ''
    if ($exe -ne "git") { return $null }
    $i++

    $repoDir = $null
    while ($i -lt $tokens.Count) {
        $t = $tokens[$i]
        if ($t -eq "-C") { $repoDir = $tokens[$i + 1]; $i += 2; continue }
        if ($t -eq "-c") { $i += 2; continue }          # -c key=value config
        if ($t.StartsWith("-")) { $i++; continue }       # other global option
        break
    }
    if ($i -ge $tokens.Count) { return $null }

    $sub = $tokens[$i]
    $i++
    $rest = @()
    if ($i -lt $tokens.Count) { $rest = @($tokens[$i..($tokens.Count - 1)]) }
    return @{ RepoDir = $repoDir; Sub = $sub; Args = $rest }
}

function Get-RepoDir($Invocation, $Root) {
    if (-not [string]::IsNullOrWhiteSpace($Invocation.RepoDir)) {
        return (Resolve-AbsolutePath $Invocation.RepoDir $Root)
    }
    return $Root
}

function Invoke-Git($RepoDir, [string[]]$GitArgs) {
    try { return @(& git -C $RepoDir @GitArgs 2>$null) } catch { return @() }
}

function Get-PorcelainEntries($Lines) {
    # Parse `git status --porcelain` output into @{ Status; Path } entries.
    $entries = @()
    foreach ($line in $Lines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $status = $line.Substring(0, [Math]::Min(2, $line.Length))
        $rest = if ($line.Length -gt 3) { $line.Substring(3) } else { "" }
        if ($rest -match '->') { $rest = ($rest -split '->')[-1] }   # renames: take the new path
        $rest = $rest.Trim().Trim('"')
        if (-not [string]::IsNullOrWhiteSpace($rest)) {
            $entries += @{ Status = $status; Path = $rest }
        }
    }
    return $entries
}

function Get-AddOffenders($Invocation, $RepoDir) {
    $offenders = @()
    $bulkAll = $false        # -A / --all
    $updateOnly = $false     # -u
    $dirSpecs = @()          # explicit directory pathspecs (absolute)

    foreach ($a in $Invocation.Args) {
        $raw = $a.Trim('"')
        if ($raw -eq "-A" -or $raw -eq "--all") { $bulkAll = $true; continue }
        if ($raw -eq "-u" -or $raw -eq "--update") { $updateOnly = $true; continue }
        if ($raw -eq "." -or $raw -eq "./") { $bulkAll = $true; continue }
        if ($raw -eq "--") { continue }
        if ($raw.StartsWith("-")) { continue }           # any other flag

        $absSpec = Resolve-AbsolutePath $raw $RepoDir
        if (Test-Path -LiteralPath $absSpec -PathType Container) {
            $dirSpecs += $absSpec.TrimEnd('\', '/')
        }
        elseif (Test-ForbiddenReadme $absSpec $RepoDir) {
            $offenders += (Get-RelativePosixPath $absSpec $RepoDir)  # explicit file / pathspec
        }
    }

    $needEnum = $bulkAll -or $updateOnly -or ($dirSpecs.Count -gt 0)
    if (-not $needEnum) { return $offenders }

    foreach ($entry in Get-PorcelainEntries (Invoke-Git $RepoDir @("status", "--porcelain", "--untracked-files=all"))) {
        if ($updateOnly -and -not $bulkAll -and $entry.Status -eq "??") { continue }  # -u ignores untracked
        $absEntry = Resolve-AbsolutePath $entry.Path $RepoDir
        if (-not (Test-ForbiddenReadme $absEntry $RepoDir)) { continue }

        if ($dirSpecs.Count -gt 0 -and -not $bulkAll -and -not $updateOnly) {
            $under = $false
            foreach ($d in $dirSpecs) {
                if ($absEntry.StartsWith($d, [System.StringComparison]::OrdinalIgnoreCase)) { $under = $true; break }
            }
            if (-not $under) { continue }
        }
        $offenders += (Get-RelativePosixPath $absEntry $RepoDir)
    }
    return $offenders
}

function Get-CommitOffenders($Invocation, $RepoDir) {
    $offenders = @()
    $all = $false
    foreach ($a in $Invocation.Args) {
        if ($a -eq "--all") { $all = $true; continue }
        # short-flag bundle containing 'a' (-a, -am, -av ...): in `git commit`, 'a' always means --all
        if ($a -match '^-[a-zA-Z]+$' -and $a.Contains('a')) { $all = $true }
    }

    $candidates = @(Invoke-Git $RepoDir @("diff", "--cached", "--name-only"))  # already staged
    if ($all) { $candidates += @(Invoke-Git $RepoDir @("ls-files", "-m")) }     # -a also stages tracked mods

    foreach ($p in ($candidates | Select-Object -Unique)) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        $abs = Resolve-AbsolutePath ($p.Trim().Trim('"')) $RepoDir
        if (Test-ForbiddenReadme $abs $RepoDir) { $offenders += (Get-RelativePosixPath $abs $RepoDir) }
    }
    return $offenders
}

try {
    $hook = Read-HookPayload
    if ($null -eq $hook) { exit 0 }

    $command = $hook.tool_input.command
    if ([string]::IsNullOrWhiteSpace($command)) { exit 0 }
    if ($command -notmatch '(?i)\bgit\b') { exit 0 }   # fast bail: no git, nothing to inspect

    $root = Get-ProjectRoot $hook
    $config = Get-GuardConfig $root
    if (Test-ConfigDisabled $config) { exit 0 }

    $offenders = @()
    foreach ($segment in Get-Segments $command) {
        $inv = Get-GitInvocation $segment
        if ($null -eq $inv) { continue }
        $repoDir = Get-RepoDir $inv $root
        if ($inv.Sub -eq "add") { $offenders += Get-AddOffenders $inv $repoDir }
        elseif ($inv.Sub -eq "commit") { $offenders += Get-CommitOffenders $inv $repoDir }
    }

    $filtered = @()
    foreach ($o in ($offenders | Select-Object -Unique)) {
        if (-not (Test-AllowedByConfig $o $config)) { $filtered += $o }
    }
    if ($filtered.Count -eq 0) { exit 0 }

    $list = ($filtered | ForEach-Object { "'$_'" }) -join ", "
    $reason = "readme-name-guardrail: this git command would stage or commit forbidden README " +
        "file(s): $list. The name 'readme.md' (any capitalization) is reserved for the single " +
        "project-root README; extra files with that exact name crowd terminal file references. " +
        "Rename each with a descriptive prefix - e.g. 'creatures-readme.md' - and 'git restore " +
        "--staged <path>' any that are already staged, then retry."
    Deny-PreToolUse $reason
    exit 0
}
catch {
    exit 0  # internal error: fail open so the guardrail never blocks all Bash
}
