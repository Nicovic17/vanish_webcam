@echo off
setlocal
cd /d "%~dp0"
echo [VanishCam] Checking dependencies, models, assets and generated audio.
echo [VanishCam] This check does not open or record your webcam.
call "%~dp0AVVIA_LOCALE.bat" --self-test
set "CHECK_RESULT=%errorlevel%"
if "%CHECK_RESULT%"=="0" pause
exit /b %CHECK_RESULT%
