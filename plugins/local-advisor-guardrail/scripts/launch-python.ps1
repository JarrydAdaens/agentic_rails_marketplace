# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0. See the repository LICENSE.

param(
    [Parameter(Mandatory = $true)]
    [string]$Script,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArguments
)

$ErrorActionPreference = "Stop"

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [string[]]$PrefixArguments = @()
    )

    & $Command @PrefixArguments $Script @ScriptArguments
    exit $LASTEXITCODE
}

if ($env:AGENTIC_RAILS_PYTHON) {
    Invoke-Python -Command $env:AGENTIC_RAILS_PYTHON
}

$pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    Invoke-Python -Command $pythonLauncher.Source -PrefixArguments @("-3")
}

$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if ($python) {
    Invoke-Python -Command $python.Source
}

$uv = Get-Command uv.exe -ErrorAction SilentlyContinue
if (-not $uv) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
}
if ($uv) {
    & $uv.Source run --no-project python $Script @ScriptArguments
    exit $LASTEXITCODE
}

Write-Error "No Python 3 launcher was found. Set AGENTIC_RAILS_PYTHON or install py.exe, python, or uv."
exit 127
