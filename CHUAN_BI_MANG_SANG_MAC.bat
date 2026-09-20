@echo off
chcp 65001 >nul
setlocal

rem ==========================================================================
rem  CHUAN_BI_MANG_SANG_MAC.bat
rem
rem  Gom moi thu can thiet vao MOT thu muc de chep sang may Mac.
rem
rem  VI SAO KHONG CHEP CA ToolCloneEvoto
rem      Thu muc do co ca tram GB anh thi nghiem, ket qua do dac va .venv cua
rem      Windows (khong dung duoc tren Mac). Ban dong goi chi can dung bon thu:
rem          saytool\        goi chinh
rem          mo_hinh\        vet.pt, nong_cam.pt, liquify\
rem          blem_net3.py    blemish_apply.py goi toi, nam o thu muc goc
rem          blem_gpu.py     kien truc cua vet.pt (UNetGate)
rem
rem      Hai file .py cuoi la cho de sai lam: chung KHONG nam trong goi saytool.
rem      Thieu chung thi retouch van chay, van ra anh, chi la buoc "Xoa khuyet
rem      diem" bi tat lang le kem mot dong "! BO QUA" troi qua trong nhat ky.
rem ==========================================================================

cd /d "%~dp0"

rem ==========================================================================
rem  TU 10/09: MAC DINH KHONG CHEP ToolCloneEvoto SANG NUA.
rem
rem  Tool retouch dang duoc toi uu toc do nen tam tach khoi ban giao. Bo
rem  AutoTone-mac.zip da la ban --khong-retouch: khong co retouch.py, khong keo
rem  torch/mediapipe/insightface, nhe di vai GB.
rem
rem  Van muon kem retouch thi goi kem duong dan tool:
rem      CHUAN_BI_MANG_SANG_MAC.bat "F:\Claude AI\ToolCloneEvoto"
rem  Luc do phai sua CAI_DAT_MAC.command bo hai chu --khong-retouch, neu khong
rem  thi chep sang cung khong duoc dung toi.
rem ==========================================================================
set "TOOL="
if not "%~1"=="" set "TOOL=%~1"

echo.
echo   ============================================
echo    Chuan bi bo mang sang may Mac
echo   ============================================
echo.

if "%TOOL%"=="" goto :bo_qua_tool
if not exist "%TOOL%\saytool\cli.py" (
  echo   [!] Khong thay tool retouch o: %TOOL%
  echo       Chay lai va chi ro:  CHUAN_BI_MANG_SANG_MAC.bat "D:\duong\dan\ToolCloneEvoto"
  echo.
  pause
  exit /b 1
)

set "RA=%~dp0ChuyenSangMac"
if exist "%RA%" rmdir /s /q "%RA%"
mkdir "%RA%" 2>nul

:bo_qua_tool
echo   [1/3] Giai nen bo AutoTone...
if not exist "%~dp0AutoTone-mac.zip" (
  echo   [!] Khong thay AutoTone-mac.zip canh file nay.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -LiteralPath '%~dp0AutoTone-mac.zip' -DestinationPath '%RA%' -Force"
if errorlevel 1 ( echo   [!] Giai nen that bai. & pause & exit /b 1 )

if "%TOOL%"=="" (
  echo   [2/3] Bo qua phan retouch ^(ban nay tach rieng^).
  goto :xong_tool
)
echo   [2/3] Chep phan can thiet cua tool retouch...
set "TD=%RA%\AutoTone-mac\ToolCloneEvoto"
mkdir "%TD%" 2>nul
robocopy "%TOOL%\saytool" "%TD%\saytool" /E /XD __pycache__ /NFL /NDL /NJH /NJS /NP >nul
robocopy "%TOOL%\mo_hinh" "%TD%\mo_hinh" /E /NFL /NDL /NJH /NJS /NP >nul
copy /y "%TOOL%\blem_net3.py" "%TD%\" >nul
copy /y "%TOOL%\blem_gpu.py"  "%TD%\" >nul

set "THIEU="
if not exist "%TD%\saytool\cli.py"     set "THIEU=%THIEU% saytool\cli.py"
if not exist "%TD%\mo_hinh\vet.pt"     set "THIEU=%THIEU% mo_hinh\vet.pt"
if not exist "%TD%\blem_net3.py"        set "THIEU=%THIEU% blem_net3.py"
if not exist "%TD%\blem_gpu.py"         set "THIEU=%THIEU% blem_gpu.py"
if not "%THIEU%"=="" (
  echo   [!] Chep thieu:%THIEU%
  echo       Kiem lai thu muc %TOOL%
  pause
  exit /b 1
)

:xong_tool
echo   [3/3] Xong.
echo.
for /f "usebackq" %%A in (`powershell -NoProfile -Command ^
  "'{0:N0}' -f ((Get-ChildItem -LiteralPath '%RA%' -Recurse -File | Measure-Object Length -Sum).Sum/1MB)"`) do set "CO=%%A"
echo   Thu muc can chep sang Mac:
echo       %RA%\AutoTone-mac        (khoang %CO% MB)
echo.
echo   TREN MAY MAC:
echo       1. Chep ca thu muc AutoTone-mac sang (USB, AirDrop, o mang deu duoc)
echo       2. Bam dup  CAI_DAT_MAC.command  ben trong no
echo       3. Bi chan thi chuot phai -^> Open -^> Open
echo.
echo   Dat o duong dan KHONG CO DAU tieng Viet.
echo.
explorer "%RA%"
pause
