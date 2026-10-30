@echo off
setlocal
cd /d "%~dp0"

if not defined PYTHON_BIN set "PYTHON_BIN=python"
"%PYTHON_BIN%" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if errorlevel 1 (
  echo Usa Python 3.12 nel PATH oppure imposta PYTHON_BIN al suo eseguibile.
  goto :error
)

"%PYTHON_BIN%" -c "import PyInstaller, cv2, mediapipe, numpy, pyvirtualcam, pygame" >nul 2>nul
if errorlevel 1 (
  echo Installo le dipendenze di build...
  "%PYTHON_BIN%" -m pip install -r requirements.txt "pyinstaller>=6,<7"
  if errorlevel 1 goto :error
)

if not exist "models\gesture_recognizer.task" goto :models
if not exist "models\selfie_segmenter_landscape.tflite" goto :models
goto :build

:models
echo Scarico i modelli MediaPipe necessari...
"%PYTHON_BIN%" -c "from vanish_cam import download_models; download_models()"
if errorlevel 1 goto :error

:build
"%PYTHON_BIN%" -m PyInstaller --noconfirm --distpath dist --workpath build VanishCam.spec
if errorlevel 1 goto :error

"dist\VanishCam.exe" --self-test
if errorlevel 1 goto :error

echo.
echo Pronto: dist\VanishCam.exe
exit /b 0

:error
echo.
echo Build non riuscita. Controlla i messaggi qui sopra.
pause
exit /b 1
