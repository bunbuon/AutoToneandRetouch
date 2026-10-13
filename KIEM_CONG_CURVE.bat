@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_CONG_CURVE.bat - CONG curve da + nen chay tren anh Lightroom that (13/10).
rem
rem  Nguong dat TRUOC khi chay (kiem_cong_curve.py, CLAUDE.md), khong noi sau.
rem  Dung HAI buoi chua dung khi lam tinh nang: mot cuoi co mau da, mot su kien LED.
rem
rem  Cach dung:
rem    1. KIEM_CONG_CURVE.bat mo
rem         -> mo AutoTone o che do cong (giu anh dung luot 2 + ket_qua.json).
rem            Bat hai o Curve trong Thiet lap > Ghim va bao ve, bam Xu ly anh
rem            cho buoi cong, cho toi khi xong.
rem    2. Keo tha thu muc buoi len file nay
rem         -> Lightroom dung lai cac anh SAU curve, tinh cong, ghi cong_curve.txt
rem            + so_sanh_curve.pdf (canh ket_qua.json trong du lieu AutoTone).
rem            Gui PDF cho anh xem tan mat truoc khi bat mac dinh.
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "PYTHONWARNINGS=ignore"
set "OPENCV_LOG_LEVEL=ERROR"
if /i "%~1"=="mo" (
    set "AUTOTONE_CURVE_GIU_ANH=1"
    python autotone_gui.py
    goto :eof
)
if "%~1"=="" (
    echo Keo tha thu muc buoi len file nay, hoac: KIEM_CONG_CURVE.bat mo
    pause
    goto :eof
)
python kiem_cong_curve.py "%~1"
pause
