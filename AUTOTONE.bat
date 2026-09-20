@echo off
chcp 65001 >nul
cd /d "%~dp0"

python -c "import numpy, PIL, tkinter" 2>nul
if errorlevel 1 (
  echo.
  echo Thieu thu vien hoac chua cai Python.
  echo Chay lenh sau roi mo lai:
  echo     pip install -r "%~dp0requirements.txt"
  echo.
  pause
  exit /b 1
)

start "" pythonw "%~dp0autotone_gui.py"
