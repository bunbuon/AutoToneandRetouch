@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_TOAN_BO.bat - kiem TOAN BO tinh nang AutoTone tu ma nguon (14/10).
rem
rem  1-2. Bai kiem TU DONG (kiem_toan_bo.py): ~100 bai theo nhom tinh nang, moi bai
rem       chay tren thu muc du lieu TAM - khong dung du lieu that, khong cai plugin,
rem       khong ghi job cho Lightroom, khong doc catalog that.
rem       Ket qua: ket_qua_kiem\<ngay-gio>\tong_ket.txt + file .zip de gui Claude.
rem  3-7. Thu TAY nhung phan can Lightroom / anh RAW that / may chu key that.
rem
rem  Khong dong goi, khong dung ban .exe - chay thang ma nguon trong thu muc nay.
rem ---------------------------------------------------------------------------
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONWARNINGS=ignore"
set "OPENCV_LOG_LEVEL=ERROR"

rem --- tim Python co du numpy / opencv / Pillow / tkinter -------------------
set "PY="
if not exist "%~dp0ket_qua_kiem" mkdir "%~dp0ket_qua_kiem"
call :thu_py "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY call :thu_py py -3.12
if not defined PY call :thu_py py -3
if not defined PY call :thu_py python
if not defined PY (
  echo.
  echo   [!] Khong tim thay Python co du thu vien ^(numpy, opencv, Pillow, tkinter^).
  echo       Cai:  pip install -r "%~dp0requirements.txt"
  echo.
  pause
  exit /b 1
)
rem  dung thang python.exe tim duoc; cac file .bat thu tay goi "python" tran nen dua
rem  thu muc cua no len dau PATH
set /p PY=<"%~dp0ket_qua_kiem\python.txt"
del "%~dp0ket_qua_kiem\python.txt" >nul 2>&1
for %%f in ("%PY%") do set "PATH=%%~dpf;%PATH%"
set PY="%PY%"

:menu
echo.
echo  ================= KIEM TOAN BO AutoTone =================
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "NHANH=%%b"
for /f "delims=" %%c in ('git log -1 "--format=%%h %%cd %%s" "--date=format:%%d/%%m %%H:%%M" 2^>nul') do set "COMMIT=%%c"
echo   Ma nguon: %NHANH%  -  %COMMIT%
echo   Python  : %PY%
echo.
echo   1. Chay TOAN BO bai kiem tu dong   (~30 phut)
echo   2. Chay NHANH  (bo bai Retouch giao dien ~12 phut)
echo   3. Mo app tu ma nguon de thu bang tay  (+ DANH_SACH_THU_TAY.txt)
echo   4. Kiem RAW that tren mot thu muc anh  (KIEM_RAW_THAT.bat)
echo   5. Kiem curve tren Lightroom that      (KIEM_CURVE_LR.bat)
echo   6. Cong curve da tren mot buoi          (KIEM_CONG_CURVE.bat)
echo   7. Thu credit + mot key mot may         (THU_CREDIT_2_MAY.bat - can may chu moi)
echo   8. Lay code moi nhat tu GitHub          (git pull)
echo   0. Thoat
echo.
set "CHON="
set /p "CHON=  Chon so roi Enter: "
if "%CHON%"=="1" goto tu_dong
if "%CHON%"=="2" goto nhanh
if "%CHON%"=="3" goto mo_app
if "%CHON%"=="4" goto raw
if "%CHON%"=="5" goto curve_lr
if "%CHON%"=="6" goto cong_curve
if "%CHON%"=="7" goto credit
if "%CHON%"=="8" goto keo
if "%CHON%"=="0" goto :eof
goto menu

:tu_dong
%PY% kiem_toan_bo.py
goto xong_tu_dong

:nhanh
%PY% kiem_toan_bo.py --nhanh
goto xong_tu_dong

:xong_tu_dong
for /f "delims=" %%d in ('dir /b /ad /o-n "%~dp0ket_qua_kiem" 2^>nul') do (
  set "MOI=%%d"
  goto mo_ket_qua
)
goto menu
:mo_ket_qua
if exist "%~dp0ket_qua_kiem\%MOI%\tong_ket.txt" start "" notepad "%~dp0ket_qua_kiem\%MOI%\tong_ket.txt"
echo.
echo   Gui file nay cho Claude:  ket_qua_kiem\%MOI%.zip
start "" explorer /select,"%~dp0ket_qua_kiem\%MOI%.zip"
pause
goto menu

:mo_app
if exist "%~dp0DANH_SACH_THU_TAY.txt" start "" notepad "%~dp0DANH_SACH_THU_TAY.txt"
echo.
echo   Thu cung Lightroom (Xu ly anh, Denoise, danh sach anh...) can plugin MOI trong
echo   Lightroom, tro ve thu muc job cua ma nguon. Mo lai ban da cai (Tone^&Retouch)
echo   thi no tu chep lai plugin cua no.
choice /c CK /n /m "  Chep plugin moi vao Lightroom? [C = co / K = khong]: "
if errorlevel 2 goto mo_app_chay
%PY% kiem_toan_bo.py --cai-plugin-lr
:mo_app_chay
rem  ma nguon dung du lieu canh file .py (gu.json, trang_thai, phan_tich...) nhu truoc nay
start "AutoTone - ma nguon" %PY% autotone_gui.py
goto menu

:raw
set "TM="
set /p "TM=  Thu muc anh RAW (Enter = G:\TestThacCao\test): "
call "%~dp0KIEM_RAW_THAT.bat" %TM%
goto menu

:curve_lr
call "%~dp0KIEM_CURVE_LR.bat"
goto menu

:cong_curve
set "BUOI="
set /p "BUOI=  Ten buoi (bo trong = 'mo' de mo app che do giu anh): "
if "%BUOI%"=="" set "BUOI=mo"
call "%~dp0KIEM_CONG_CURVE.bat" %BUOI%
goto menu

:credit
call "%~dp0THU_CREDIT_2_MAY.bat"
goto menu

:keo
git pull --ff-only
pause
goto menu

rem --- :thu_py <lenh python...>  dat PY neu lenh do import duoc du thu vien ---
:thu_py
%* -c "import numpy, cv2, PIL, tkinter, sys; print(sys.executable)" >"%~dp0ket_qua_kiem\python.txt" 2>nul && set "PY=%*"
exit /b 0
