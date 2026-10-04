@echo off
rem ---------------------------------------------------------------------------
rem  XOA_BAN_XUAT.bat - xoa MOI ban xuat catalog cu trong jobs (3/10/2026)
rem
rem  Xoa trong AutoTone.lrplugin\jobs:
rem    export_*.tsv, export_*.tsv.part   ban xuat thong so tu catalog Lightroom
rem    ketqua_xuat.txt                   ket qua lan app nho xuat gan nhat
rem    request_export.txt                yeu cau xuat con treo (neu co)
rem
rem  KHONG dong toi:
rem    _autotone_baseline.tsv trong thu muc anh (moc goc - xoa thi lan sau
rem        lay so tool da ghi lam nen va CONG DON, Exposure +0.71 thanh +1.42)
rem    apply_*.done (lan tool ghi - de nhan ra anh ban da sua tay), verify_*.tsv,
rem    plugin.log, export_lr_duongdan.txt (thu muc Export, khong phai ban xuat).
rem
rem  Ban xuat chi la ban chup thong so trong catalog: xoa khong mat gi. Chon thu
rem  muc trong app la app tu nho Lightroom xuat lai dung thu muc do.
rem
rem  DONG app AutoTone truoc khi chay.
rem ---------------------------------------------------------------------------
setlocal
set "JOBS=%~dp0AutoTone.lrplugin\jobs"
if exist "%JOBS%\" goto co_jobs
echo Khong thay thu muc:
echo   %JOBS%
echo De file nay nam canh thu muc AutoTone.lrplugin roi chay lai.
echo.
pause
exit /b 1

:co_jobs
set /a N=0
echo Ban xuat catalog se xoa:
for %%F in ("%JOBS%\export_*.tsv") do (
  echo   %%~nxF
  set /a N+=1
)

del /f /q "%JOBS%\export_*.tsv" >nul 2>&1
del /f /q "%JOBS%\export_*.tsv.part" >nul 2>&1
del /f /q "%JOBS%\ketqua_xuat.txt" >nul 2>&1
del /f /q "%JOBS%\request_export.txt" >nul 2>&1

set /a CON=0
for %%F in ("%JOBS%\export_*.tsv") do set /a CON+=1

echo.
echo Da xoa %N% ban xuat catalog cu.
if %CON% GTR 0 echo [!] Con %CON% file export_*.tsv chua xoa duoc - dong AutoTone roi chay lai.
echo.
echo Buoc tiep theo:
echo   1. Lightroom: File ^> Plug-in Manager ^> AutoTone ^> Reload Plug-in
echo   2. Mo lai AutoTone, chon thu muc anh - app tu nho Lightroom xuat lai.
echo.
pause
