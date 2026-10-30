@echo off
setlocal
cd /d "%~dp0"
echo [VanishCam] Starting 720p at 30 FPS. Virtual camera is enabled automatically.
echo [VanishCam] Choose an effect in the menu, then step out of frame for 4 seconds.
call "%~dp0AVVIA_LOCALE.bat" --width 1280 --height 720 --fps 30 %*
exit /b %errorlevel%
