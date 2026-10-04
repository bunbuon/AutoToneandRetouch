@echo off
rem ---------------------------------------------------------------------------
rem  DO_BUOI.bat - do CA BUOI bang dung analyze() cua tool, luu so do ra
rem  Claude outputs\do\<buoi>\ de chay cong kiem cho 5 phan sua (2/10/2026).
rem
rem  CHI DOC anh. Khong ghi gi vao thu muc anh, khong dung catalog Lightroom.
rem  Mac dinh do 3 buoi: G:\TrainTool, G:\2609, G:\1308 (buoi nao khong co
rem  thi bo qua). Mat khoang 5 phut. Dong cua so AutoTone cho nhanh hon.
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "PYTHONWARNINGS=ignore"
set "OPENCV_LOG_LEVEL=ERROR"
set "PYTHONUTF8=1"
if "%~1"=="" (
  python do_buoi.py "G:\TrainTool" "G:\2609" "G:\1308"
) else (
  python do_buoi.py %*
)
echo.
echo Xong. Bao lai cho Claude.
pause
