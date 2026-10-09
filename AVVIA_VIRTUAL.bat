@echo off
call "%~dp0AVVIA_LOCALE.bat" --virtual-camera %*
exit /b %errorlevel%
