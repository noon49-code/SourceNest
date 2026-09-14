@echo off
setlocal
if defined BEYIN_PYTHON goto run
set "BEYIN_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%BEYIN_PYTHON%" goto run
:findpython
where python.exe >nul 2>&1
if errorlevel 1 (
  echo Python 3.11+ is required. Set BEYIN_PYTHON to its executable path.
  exit /b 1
)
set "BEYIN_PYTHON=python"
:run
"%BEYIN_PYTHON%" -X utf8 "%~dp0beyin.py" %*
exit /b %ERRORLEVEL%
