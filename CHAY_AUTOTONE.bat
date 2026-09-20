@echo off
rem ---------------------------------------------------------------------------
rem  CHAY_AUTOTONE.bat - mo ban .exe da dong goi, TRO DUNG THU MUC PLUGIN.
rem
rem  VAN DE NO GIAI QUYET
rem      Lightroom ghi ban xuat vao thu muc plugin ma NO da cai:
rem          F:\Claude AI\AutoToneImages\AutoTone.lrplugin\jobs\
rem      Con ban .exe lai doc thu muc plugin cua RIENG NO:
rem          %LOCALAPPDATA%\AutoTone\AutoTone.lrplugin\jobs\
rem      Hai cho khac nhau, nen .exe khong bao gio thay ban xuat moi.
rem
rem      AUTOTONE_DATA bao cho app biet thu muc du lieu nam o dau. Dat no ve
rem      thu muc du an thi app dung DUNG cai plugin ma Lightroom dang ghi vao,
rem      va dung chung gu.json / trang_thai voi ban chay tu ma nguon.
rem
rem  DAY LA CACH CHUA TAM, KHONG PHAI BAN SUA.
rem      Ban sua that nam trong dong_goi.py (khong dong thu muc jobs vao goi) va
rem      trong duong_dan.py. Sau khi dong goi lai thi file .bat nay khong con
rem      can nua - nhung giu lai cung khong hai gi.
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "EXE=%~dp0dist\AutoTone\AutoTone.exe"
if not exist "%EXE%" (
  echo.
  echo   [!] Khong thay %EXE%
  echo       Chay dong_goi.py truoc, hoac sua duong dan trong file .bat nay.
  echo.
  pause
  exit /b 1
)

rem Bo dau \ o cuoi neu co - app noi chuoi duong dan nen thua mot dau la lech.
set "DATA=%~dp0"
if "%DATA:~-1%"=="\" set "DATA=%DATA:~0,-1%"
set "AUTOTONE_DATA=%DATA%"

echo.
echo   Thu muc du lieu: %AUTOTONE_DATA%
echo   Plugin Lightroom: %AUTOTONE_DATA%\AutoTone.lrplugin
echo.
echo   Dang mo AutoTone...
start "" "%EXE%"
