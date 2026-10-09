@echo off
setlocal
cd /d "%~dp0\.."

set "VENV_DIR=.venv-local"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [Vanish Lab] Creo l'ambiente Python locale...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv "%VENV_DIR%"
  ) else (
    python -m venv "%VENV_DIR%"
  )
  if errorlevel 1 goto :error
)

"%VENV_PY%" -c "import cv2, mediapipe, numpy, pyvirtualcam" >nul 2>nul
if errorlevel 1 (
  echo [Vanish Lab] Installo i componenti necessari. Serve internet solo questa volta...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :error
  "%VENV_PY%" -m pip install -r "local_app\requirements.txt"
  if errorlevel 1 goto :error
)

echo [Vanish Lab] Avvio la webcam...
"%VENV_PY%" "local_app\vanish_cam.py" %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Impossibile avviare Vanish Lab. Leggi local_app\README.md per le soluzioni comuni.
pause
exit /b 1
