@echo off
setlocal EnableExtensions DisableDelayedExpansion
if "%~1"=="" (
  echo launch-uv.cmd requires a Python script path. 1>&2
  exit /b 64
)
set "AGENTIC_RAILS_UV_EXE="
if defined AGENTIC_RAILS_UV if exist "%AGENTIC_RAILS_UV%" set "AGENTIC_RAILS_UV_EXE=%AGENTIC_RAILS_UV%"
if not defined AGENTIC_RAILS_UV_EXE if exist "%USERPROFILE%\.local\bin\uv.exe" set "AGENTIC_RAILS_UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
if not defined AGENTIC_RAILS_UV_EXE if exist "%USERPROFILE%\.cargo\bin\uv.exe" set "AGENTIC_RAILS_UV_EXE=%USERPROFILE%\.cargo\bin\uv.exe"
if not defined AGENTIC_RAILS_UV_EXE if exist "%LOCALAPPDATA%\Programs\uv\uv.exe" set "AGENTIC_RAILS_UV_EXE=%LOCALAPPDATA%\Programs\uv\uv.exe"
if not defined AGENTIC_RAILS_UV_EXE for %%U in (uv.exe) do if not "%%~$PATH:U"=="" set "AGENTIC_RAILS_UV_EXE=%%~$PATH:U"
if not defined AGENTIC_RAILS_UV_EXE (
  echo uv was not found. Install uv or set AGENTIC_RAILS_UV to the absolute uv.exe path. 1>&2
  exit /b 127
)
"%AGENTIC_RAILS_UV_EXE%" run --no-project python %*
exit /b
