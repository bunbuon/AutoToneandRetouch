@echo off
rem ---------------------------------------------------------------------------
rem  LUU_BO_DA_SUA.bat - chup NGUYEN TRANG thong so develop cua mot buoi da sua
rem  tay xong, ghi vao chinh thu muc anh: _autotone_da_sua_<ngay gio>.tsv
rem
rem  CHI DOC catalog, khong ghi gi vao anh. Lay ca anh 1 sao. Khong xoa ban cu.
rem
rem  Can: Lightroom dang mo, plugin AutoTone da nap ban co ChupCore.lua
rem       (File > Plug-in Manager > AutoTone > Reload Plug-in).
rem
rem  Cach dung: keo tha thu muc buoi len file nay, hoac nhap dup (= G:\2609).
rem ---------------------------------------------------------------------------
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "BUOI=%~1"
if "%BUOI%"=="" set "BUOI=G:\2609"
if "%BUOI:~-1%"=="\" set "BUOI=%BUOI:~0,-1%"
set "JOBS=%~dp0AutoTone.lrplugin\jobs"
set "REQ=%JOBS%\request_chup.txt"
set "XONG=%JOBS%\chup_xong.txt"

if not exist "%BUOI%\" (
  echo [!] Khong thay thu muc %BUOI%
  pause & exit /b 1
)
if exist "%XONG%" del "%XONG%"
> "%REQ%.part" echo %BUOI%
move /y "%REQ%.part" "%REQ%" >nul

echo Da gui yeu cau chup: %BUOI%
echo Dang cho Lightroom (toi da 10 phut)...
set /a DEM=0
:cho
timeout /t 5 /nobreak >nul
set /a DEM+=1
if exist "%XONG%" goto xong
if !DEM! EQU 6 if exist "%REQ%" (
  echo.
  echo [!] Sau 30 giay plugin van chua nhan yeu cau.
  echo     - Lightroom co dang mo khong?
  echo     - Da Reload plugin AutoTone chua? Ban cu khong biet request_chup.txt.
  echo     Cu de cua so nay, lam xong hai viec tren la no tu chay tiep.
)
if !DEM! GEQ 120 (
  echo [!] Qua 10 phut chua xong. Xem AutoTone.lrplugin\jobs\plugin.log
  pause & exit /b 1
)
goto cho

:xong
echo.
type "%XONG%"
findstr /b "LOI" "%XONG%" >nul && ( pause & exit /b 1 )
echo.
python xem_ban_chup.py "%BUOI%"
echo.
pause
