@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_PREVIEW_LR.bat - do toc do PREVIEW LIGHTROOM tren may that (14/10).
rem
rem  Giai doan 0 cua chuoi mau da MOT LUOT: do Lightroom tra preview nhanh the nao
rem  (lan dau / lan sau, canh 1600 / 1024, luc may dang do da song song) va preview
rem  lech ban xuat that bao nhieu. KHONG doi gi trong catalog.
rem
rem  Can: Lightroom Classic DANG MO, plugin AutoTone moi (KIEM_TOAN_BO.bat muc 3
rem  chep plugin cua ma nguon), thu muc buoi da co trong catalog. Dung bam
rem  "Xu ly anh" trong luc do.
rem
rem  Cach chay: keo tha thu muc buoi vao file nay, hoac chay roi go duong dan.
rem  Ket qua: ket_qua_kiem\preview_lr_<gio>.txt - gui file nay cho Claude.
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
set "SO="
set /p "SO=  So anh (Enter = 120): "
if "%SO%"=="" set "SO=120"

"%PY%" "%~dp0kiem_preview_lr.py" "%BUOI%" --n %SO%
echo.
for /f "delims=" %%f in ('dir /b /o-d "%~dp0ket_qua_kiem\preview_lr_*.txt" 2^>nul') do (
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
