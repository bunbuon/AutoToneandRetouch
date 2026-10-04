@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Dong goi ban FINAL co bao mat
set "PY=%~dp0venv_build\Scripts\python.exe"
set "TOOL=%~dp0..\ToolCloneEvoto"
set "LOG=%~dp0build\dong_goi_bao_mat.log"

echo ================================================================
echo   DONG GOI BAN FINAL (Windows) - CO BAO MAT
echo     Loi AutoTone + saytool : ma may .pyd, khong con ma nguon .py
echo     Mo hinh tu hoc         : ma hoa, chi giai trong RAM luc chay
echo   Mat 10-30 phut. Buoc nao hong la DUNG, khong ra goi do.
echo ================================================================
echo.

if not exist "%PY%" goto thieu_py
if not exist "%TOOL%\dong_goi_bao_mat.py" goto thieu_tool

rem ---- 1. Trinh dich C++ cua Microsoft: Cython can no de dich ra .pyd ----
set "VC="
set "VSW=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSW%" goto thieu_vc
for /f "usebackq delims=" %%i in (`"%VSW%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VC=%%i"
if not defined VC goto thieu_vc
echo [ok] Trinh dich C++: %VC%

rem ---- 2. Cython trong venv_build (chi cai neu chua co) ----
"%PY%" -c "import Cython" 2>nul
if errorlevel 1 "%PY%" -m pip install cython
"%PY%" -c "import Cython; print('[ok] Cython', Cython.__version__)"
if errorlevel 1 goto loi

rem ---- 3. Dong goi: ma hoa loi + retouch, chay THAT 7 buoc tren 2 anh bo_thuc de so voi tool goc ----
if not exist "%~dp0build" mkdir "%~dp0build"
set PYTHONUNBUFFERED=1
echo.
echo Dang dong goi... (mo %LOG% de xem tien do)
"%PY%" dong_goi.py --bao-mat --tool-retouch "%TOOL%" --so-anh "%TOOL%\bo_thuc" > "%LOG%" 2>&1
set "RC=%errorlevel%"
echo.
echo ---------------- 40 dong cuoi nhat ky ----------------
powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 40 -Encoding UTF8"
if not "%RC%"=="0" goto loi

echo.
echo ================================================================
echo   DAT. Goi o: %~dp0dist\
echo   Nhat ky day du: %LOG%
echo ================================================================
pause
exit /b 0

:thieu_py
echo [!] Khong thay %PY%
echo     Moi truong dong goi venv_build chua co - xem HUONG_DAN_DONG_GOI.md.
goto loi

:thieu_tool
echo [!] Khong thay %TOOL%\dong_goi_bao_mat.py
echo     Thu muc ToolCloneEvoto phai nam canh AutoToneImages.
goto loi

:thieu_vc
echo [!] May chua co trinh dich C++ cua Microsoft.
echo     1. Tai "Build Tools for Visual Studio 2022":
echo        https://visualstudio.microsoft.com/visual-cpp-build-tools/
echo     2. Mo file vua tai, tick o "Desktop development with C++", bam Install.
echo     3. Cai xong (khoang 5-8 GB) chay lai file nay.
goto loi

:loi
echo.
echo [!] DUNG - xem thong bao o tren. KHONG co goi nao duoc tao.
echo     Nhat ky: %LOG%
pause
exit /b 1
