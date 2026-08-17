@echo off
setlocal EnableExtensions DisableDelayedExpansion
if "%~1"=="" (
  echo launch-windows.cmd requires a Python script path. 1>&2
  exit /b 64
)

if not defined SystemRoot set "SystemRoot=C:\Windows"
set "AGENTIC_RAILS_REG=%SystemRoot%\System32\reg.exe"
set "AGENTIC_RAILS_WHERE=%SystemRoot%\System32\where.exe"

if not defined USERPROFILE for /f "skip=1 tokens=2,*" %%A in ('"%AGENTIC_RAILS_REG%" query "HKCU\Volatile Environment" /v USERPROFILE 2^>nul') do set "USERPROFILE=%%B"
if not defined LOCALAPPDATA for /f "skip=1 tokens=2,*" %%A in ('"%AGENTIC_RAILS_REG%" query "HKCU\Volatile Environment" /v LOCALAPPDATA 2^>nul') do set "LOCALAPPDATA=%%B"
if not defined APPDATA for /f "skip=1 tokens=2,*" %%A in ('"%AGENTIC_RAILS_REG%" query "HKCU\Volatile Environment" /v APPDATA 2^>nul') do set "APPDATA=%%B"

set "AGENTIC_RAILS_USER_PATH="
set "AGENTIC_RAILS_MACHINE_PATH="
if not defined AGENTIC_RAILS_SKIP_REGISTRY_PATH for /f "skip=1 tokens=2,*" %%A in ('"%AGENTIC_RAILS_REG%" query "HKCU\Environment" /v Path 2^>nul') do set "AGENTIC_RAILS_USER_PATH=%%B"
if not defined AGENTIC_RAILS_SKIP_REGISTRY_PATH for /f "skip=1 tokens=2,*" %%A in ('"%AGENTIC_RAILS_REG%" query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "AGENTIC_RAILS_MACHINE_PATH=%%B"
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0;%AGENTIC_RAILS_USER_PATH%;%AGENTIC_RAILS_MACHINE_PATH%;%PATH%"
call set "PATH=%%PATH%%"

set "AGENTIC_RAILS_UV_EXE="
if defined AGENTIC_RAILS_UV if exist "%AGENTIC_RAILS_UV%" set "AGENTIC_RAILS_UV_EXE=%AGENTIC_RAILS_UV%"
if not defined AGENTIC_RAILS_UV_EXE if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe" set "AGENTIC_RAILS_UV_EXE=%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe"
if not defined AGENTIC_RAILS_UV_EXE if defined USERPROFILE if exist "%USERPROFILE%\.local\bin\uv.exe" set "AGENTIC_RAILS_UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
if not defined AGENTIC_RAILS_UV_EXE if defined USERPROFILE if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "AGENTIC_RAILS_UV_EXE=%USERPROFILE%\.cargo\bin\uv.exe"
if not defined AGENTIC_RAILS_UV_EXE if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Programs\uv\uv.exe" set "AGENTIC_RAILS_UV_EXE=%LOCALAPPDATA%\Programs\uv\uv.exe"
if not defined AGENTIC_RAILS_UV_EXE for /f "delims=" %%U in ('"%AGENTIC_RAILS_WHERE%" uv.exe 2^>nul') do if not defined AGENTIC_RAILS_UV_EXE set "AGENTIC_RAILS_UV_EXE=%%U"
if not defined AGENTIC_RAILS_UV_EXE (
  echo uv was not found after restoring the Windows user and machine PATH. Install uv or set AGENTIC_RAILS_UV to an absolute uv.exe path. 1>&2
  exit /b 127
)
"%AGENTIC_RAILS_UV_EXE%" run --no-project python %*
exit /b
