@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_CURVE_LR.bat - V0: do curve diem cua LIGHTROOM THAT (13/10).
rem
rem  Curve da + nen chay (curve_da.py) dung mo hinh curve_lr viet khi CHUA co
rem  Lightroom: mien curve, spline, thu tu curve tong / kenh. V0 do that de chot
rem  TRUOC khi chay cong (luat du an: so chot truoc).
rem
rem  Can: Lightroom Classic DANG MO, plugin AutoTone BAN MOI (cai lai AutoTone ban
rem  day du roi khoi dong lai Lightroom - cap nhat OTA khong mang plugin).
rem
rem  Cach dung:
rem    1. Nhap dup file nay -> tao bang thu trong thu muc  %USERPROFILE%\curve_v0
rem    2. Import thu muc do vao Lightroom, Develop Settings = None (KHONG preset)
rem    3. Nhap dup file nay LAN NUA -> chay 9 ca (~2-4 phut), in ket qua,
rem       ghi curve_lr_hieu_chinh.json trong thu muc do. Gui file do cho Claude.
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "TM=%~1"
if "%TM%"=="" set "TM=%USERPROFILE%\curve_v0"
set "PYTHONWARNINGS=ignore"
set "OPENCV_LOG_LEVEL=ERROR"
if not exist "%TM%\curve_v0_bang_thu.tif" (
    python kiem_curve_lr.py tao "%TM%"
) else (
    python kiem_curve_lr.py chay "%TM%"
)
pause
