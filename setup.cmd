@echo off
setlocal
powershell.exe -NoProfile -File "%~dp0setup.ps1" %*
exit /b %ERRORLEVEL%
