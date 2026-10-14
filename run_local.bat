@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [Vanish Cam] Creating local Python environment in %VENV_DIR%...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv "%VENV_DIR%"
  ) else (
    python -m venv "%VENV_DIR%"
  )
  if errorlevel 1 goto :error
)

"%VENV_PY%" -c "import cv2, mediapipe, numpy, pyvirtualcam, pygame" >nul 2>nul
if errorlevel 1 (
  echo [Vanish Cam] Installing required dependencies (first run only)...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :error
  "%VENV_PY%" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 goto :error
)

echo [Vanish Cam] Launching webcam...
"%VENV_PY%" "%~dp0vanish_cam.py" %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Failed to launch Vanish Cam. Please check README.md for troubleshooting.
pause
exit /b 1
