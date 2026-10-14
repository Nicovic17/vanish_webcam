@echo off
call "%~dp0run_local.bat" --no-virtual-camera %*
exit /b %errorlevel%
