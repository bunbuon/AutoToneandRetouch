@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_MOT_LUOT.bat - CONG chuoi mau da MOT LUOT tren mot buoi that (14/10).
rem
rem  Chay SAU khi da Xu ly anh buoi do voi chuoi mot luot bat (KIEM_TOAN_BO muc 12).
rem  Lay preview Lightroom that cua tung anh, do da, so voi du doan cua tool.
rem  DAT: lech du doan trung vi <= 1.5 do / 5%% va >= 85%% anh trong vung on cua dich.
rem
rem  Keo tha thu muc buoi vao file nay, hoac chay roi go duong dan.
rem  Ket qua: ket_qua_kiem\mot_luot_<buoi>_<gio>.txt - gui file nay cho Claude.
rem ---------------------------------------------------------------------------
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONWARNINGS=ignore"
set "OPENCV_LOG_LEVEL=ERROR"

set "PY="
if not exist "%~dp0ket_qua_kiem" mkdir "%~dp0ket_qua_kiem"
call :thu_py "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY call :thu_py py -3.12
if not defined PY call :thu_py py -3
if not defined PY call :thu_py python
if not defined PY (
  echo.
  echo   [!] Khong tim thay Python co du thu vien ^(numpy, opencv, Pillow^).
  echo       Cai:  pip install -r "%~dp0requirements.txt"
  echo.
  pause
  exit /b 1
)
set /p PY=<"%~dp0ket_qua_kiem\python.txt"
del "%~dp0ket_qua_kiem\python.txt" >nul 2>&1

set "BUOI=%~1"
if "%BUOI%"=="" set /p "BUOI=  Thu muc buoi chup (vd G:\2709): "
if "%BUOI%"=="" goto :eof
"%PY%" "%~dp0kiem_mot_luot.py" "%BUOI%"
echo.
for /f "delims=" %%f in ('dir /b /o-d "%~dp0ket_qua_kiem\mot_luot_*.txt" 2^>nul') do (
  start "" notepad "%~dp0ket_qua_kiem\%%f"
  goto xong
)
:xong
pause
exit /b 0

rem --- :thu_py <lenh python...>  dat PY neu lenh do import duoc du thu vien ---
:thu_py
%* -c "import numpy, cv2, PIL, sys; print(sys.executable)" >"%~dp0ket_qua_kiem\python.txt" 2>nul && set "PY=%*"
exit /b 0
