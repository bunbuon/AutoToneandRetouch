@echo off
rem ---------------------------------------------------------------------------
rem  HOC_MAU_LR.bat - HOC MAU LIGHTROOM tren anh RAW that cua mot buoi (14/10).
rem
rem  Plugin ap TAM 28 bien the (Exposure, WB, HSL, curve, Color Grading) len ~20 anh
rem  co mat, dung JPEG, TRA LAI nguyen thong so; cong cu hoc mo hinh mau Lightroom cho
rem  may / profile cua buoi. Chuoi mau da MOT LUOT chi dung mo hinh DAT. ~5-10 phut.
rem
rem  Can: Lightroom DANG MO, plugin moi (KIEM_TOAN_BO.bat muc 3, chon C), buoi DA phan
rem  tich trong app. Trong luc hoc: DUNG sua anh trong Lightroom, dung bam Xu ly anh.
rem  Ctrl+C = dung (anh duoc tra lai).
rem
rem  Keo tha thu muc buoi vao file nay, hoac chay roi go duong dan.
rem  Ket qua: ket_qua_kiem\hoc_mau_<may>_<gio>.txt - gui file nay cho Claude.
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
rem  moi may / profile cua buoi (may da co mo hinh DAT thi bo qua)
"%PY%" "%~dp0hoc_mau_lr.py" "%BUOI%" --tat_ca
echo.
for /f "delims=" %%f in ('dir /b /o-d "%~dp0ket_qua_kiem\hoc_mau_*.txt" 2^>nul') do (
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
