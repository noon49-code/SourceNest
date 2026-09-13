@echo off
setlocal
if not defined BEYIN_PYTHON goto findpython
"%BEYIN_PYTHON%" -X utf8 "%~dp0beyin.py" %*
exit /b %ERRORLEVEL%
:findpython
python -X utf8 "%~dp0beyin.py" %*
exit /b %ERRORLEVEL%
