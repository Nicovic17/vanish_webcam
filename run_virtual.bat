@echo off
call "%~dp0run_local.bat" --virtual-camera %*
exit /b %errorlevel%
