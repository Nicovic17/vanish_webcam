@echo off
call "%~dp0AVVIA_LOCALE.bat" --no-virtual-camera %*
exit /b %errorlevel%
