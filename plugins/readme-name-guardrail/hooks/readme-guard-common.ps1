# Shared helpers for the readme-name-guardrail hooks. Dot-sourced by both the
# Write hook (blocks creating a non-root readme.md) and the Bash git hook
# (blocks staging/committing one). Every helper is side-effect free except the
# IO ones (Read-HookPayload, Get-GuardConfig, Deny-PreToolUse); callers fail
# OPEN on any error so a hook bug can never wedge the tool it guards.

function Read-HookPayload {
    $stdin = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($stdin)) { return $null }
    try { return $stdin | ConvertFrom-Json } catch { return $null }
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
    # Optional per-project escape hatch at harness/readme-name-guardrail/config.json.
    # Absent, empty, or malformed all mean "enforce with defaults."
    $configPath = Join-Path $Root "harness/readme-name-guardrail/config.json"
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

function Deny-PreToolUse($Reason) {
    $output = [pscustomobject]@{
        hookSpecificOutput = [pscustomobject]@{
            hookEventName            = "PreToolUse"
            permissionDecision       = "deny"
            permissionDecisionReason = $Reason
        }
    }
    Write-Output ($output | ConvertTo-Json -Depth 4 -Compress)
}
