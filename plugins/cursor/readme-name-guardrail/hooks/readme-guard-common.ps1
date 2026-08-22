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

# Shared helpers for the readme-name-guardrail hooks. Dot-sourced by both the
# Write hook (blocks creating a non-root readme.md) and the Bash git hook
# (blocks staging/committing one). Every helper is side-effect free except the
# IO ones (Read-HookPayload, Get-GuardConfig, Deny-PreToolUse); callers fail
# OPEN on any error so a hook bug can never wedge the tool it guards.

function Read-HookStdin {
    # [Console]::In decodes using the console INPUT encoding, which on Windows is
    # the OEM code page -- so a UTF-8 payload arrives as mojibake and Cursor's
    # UTF-8 BOM arrives as replacement characters rather than U+FEFF, which no
    # amount of trimming can then remove. Read the raw stream and decode it as
    # UTF-8 explicitly; StreamReader's BOM detection consumes a leading BOM.
    $reader = [System.IO.StreamReader]::new(
        [Console]::OpenStandardInput(),
        [System.Text.UTF8Encoding]::new($false),
        $true)
    try { return $reader.ReadToEnd() }
    finally { $reader.Dispose() }
}

function Read-HookPayload {
    # Failing open on a parse error silently disarmed this guardrail on Windows,
    # so report whatever is still unparsable -- a hook that fails open quietly
    # looks exactly like one that is working.
    $stdin = Read-HookStdin
    if ([string]::IsNullOrWhiteSpace($stdin)) { return $null }
    $stdin = $stdin.TrimStart([char]0xFEFF)
    try { return $stdin | ConvertFrom-Json }
    catch {
        [Console]::Error.WriteLine("readme-name-guardrail could not parse its stdin payload ($($_.Exception.Message)); allowing.")
        return $null
    }
}

function Get-ProjectRoot($Hook) {
    # The "project root" is the tool's working directory: the one place a
    # readme.md is allowed. Matches the convention used by the sibling plugins.
    if ($null -ne $Hook -and -not [string]::IsNullOrWhiteSpace($Hook.cwd)) {
        return $Hook.cwd
    }
    return (Get-Location).Path
}

function Get-GuardConfig($Root) {
    # Optional per-project escape hatch at harness/readme-name-guardrail/cursor-config.json.
    # Absent, empty, or malformed all mean "enforce with defaults."
    $configPath = Join-Path $Root "harness/readme-name-guardrail/cursor-config.json"
    if (-not (Test-Path -LiteralPath $configPath)) { return $null }
    $content = Get-Content -LiteralPath $configPath -Raw
    if ([string]::IsNullOrWhiteSpace($content)) { return $null }
    try { return $content | ConvertFrom-Json } catch { return $null }
}

function Test-ConfigDisabled($Config) {
    return ($null -ne $Config -and
            $Config.PSObject.Properties.Name -contains "enabled" -and
            -not $Config.enabled)
}

function Resolve-AbsolutePath($Path, $Root) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $combined = $Path
    } else {
        $combined = Join-Path $Root $Path
    }
    try { return [System.IO.Path]::GetFullPath($combined) } catch { return $combined }
}

function Get-RelativePosixPath($AbsPath, $Root) {
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    if ($AbsPath.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        $rel = $AbsPath.Substring($rootFull.Length).TrimStart('\', '/')
    } else {
        $rel = $AbsPath
    }
    return ($rel -replace '\\', '/')
}

function Test-IsReadmeName($Path) {
    $leaf = Split-Path -Leaf $Path
    return ($leaf.ToLowerInvariant() -eq "readme.md")
}

function Test-ForbiddenReadme($AbsPath, $Root) {
    # A path is forbidden when its filename is exactly readme.md (any casing) and
    # it is NOT the single file sitting directly in the project/repo root.
    if ([string]::IsNullOrWhiteSpace($AbsPath)) { return $false }
    if (-not (Test-IsReadmeName $AbsPath)) { return $false }
    $parent = [System.IO.Path]::GetFullPath((Split-Path -Parent $AbsPath)).TrimEnd('\', '/')
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    if ($parent -ieq $rootFull) { return $false }   # the one allowed root README
    return $true
}

function Test-AllowedByConfig($RelPosixPath, $Config) {
    # allowPaths: regexes matched against the repo-relative POSIX path; any match
    # is a narrow, project-declared exception (e.g. a docs generator's output).
    if ($null -eq $Config -or $null -eq $Config.allowPaths) { return $false }
    foreach ($pattern in @($Config.allowPaths)) {
        if (-not [string]::IsNullOrWhiteSpace($pattern) -and $RelPosixPath -imatch $pattern) {
            return $true
        }
    }
    return $false
}

function Get-SuggestedName($AbsPath) {
    # Suggest a descriptive prefix drawn from the containing folder, matching the
    # "creatures-readme.md" shape the guardrail asks agents to adopt.
    $parentLeaf = Split-Path -Leaf (Split-Path -Parent $AbsPath)
    if ([string]::IsNullOrWhiteSpace($parentLeaf)) { return "topic-readme.md" }
    $slug = ($parentLeaf.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($slug)) { return "topic-readme.md" }
    return "$slug-readme.md"
}

function Deny-PreToolUse($Reason, $Hook) {
    if ($Hook.hook_event_name -ceq "preToolUse") {
        $output = [pscustomobject]@{
            permission    = "deny"
            user_message  = $Reason
            agent_message = $Reason
        }
    }
    else {
        $output = [pscustomobject]@{
            hookSpecificOutput = [pscustomobject]@{
                hookEventName            = "PreToolUse"
                permissionDecision       = "deny"
                permissionDecisionReason = $Reason
            }
        }
    }
    Write-Output ($output | ConvertTo-Json -Depth 4 -Compress)
}
