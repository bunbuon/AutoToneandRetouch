@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_RAW_THAT.bat - chan doan mot thu muc RAW THAT tren may nay (13/10).
rem
rem    1. doc thong tin chup tung file: may, huong, ISO, toc, khau, gio
rem    2. do bang chinh analyze() cua app: anh xem truoc dung/nam, co thay mat
rem    3. plan() voi ban xuat catalog cua DUNG thu muc (neu co): Exposure tung tam
rem    4. cap anh lien nhau cung may + cung thong so ma Exposure lech > 0.30 EV
rem    5. to anh nho: khung DO = mat dem do sang, khung xam = mat bi bo
rem
rem  KHONG ghi gi vao thu muc anh, KHONG dung Lightroom, khong ghi job.
rem  Can ma nguon moi (nhanh claude/pensive-fermat-1dcrys, tu 13/10 toi).
rem
rem  Cach dung: keo tha thu muc len file nay, hoac nhap dup (= G:\TestThacCao\test).
rem  Ket qua canh file nay: ket_qua_kiem_raw.txt + kiem_raw_luoi.jpg
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "BUOI=%~1"
if "%BUOI%"=="" set "BUOI=G:\TestThacCao\test"
set "PYTHONWARNINGS=ignore"
set "OPENCV_LOG_LEVEL=ERROR"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

python kiem_raw_that.py "%BUOI%" --ra "%~dp0ket_qua_kiem_raw.txt" --luoi "%~dp0kiem_raw_luoi.jpg"

echo.
echo Xong. Gui lai 2 file canh file .bat nay:
echo    ket_qua_kiem_raw.txt
echo    kiem_raw_luoi.jpg
if exist "%~dp0kiem_raw_luoi.jpg" start "" "%~dp0kiem_raw_luoi.jpg"
if exist "%~dp0ket_qua_kiem_raw.txt" start "" notepad "%~dp0ket_qua_kiem_raw.txt"
pause
