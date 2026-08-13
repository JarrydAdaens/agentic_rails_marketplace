# Copyright 2026 Jarryd Adaens
# Licensed under the Apache License, Version 2.0.
param([Parameter(Mandatory = $true)][string]$Script)
$pythonArgs = @($Script) + @($args)
if ($env:AGENTIC_RAILS_PYTHON) { & $env:AGENTIC_RAILS_PYTHON @pythonArgs; exit $LASTEXITCODE }
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) { & $py.Source -3 @pythonArgs; exit $LASTEXITCODE }
foreach ($name in @('python.exe', 'python')) {
    $python = Get-Command $name -ErrorAction SilentlyContinue
    if ($python) { & $python.Source @pythonArgs; exit $LASTEXITCODE }
}
$uv = Get-Command uv.exe -ErrorAction SilentlyContinue
if ($uv) { & $uv.Source run --no-project python @pythonArgs; exit $LASTEXITCODE }
Write-Error 'Python 3 was not found. Set AGENTIC_RAILS_PYTHON or install py.exe, python, or uv.'
exit 127
