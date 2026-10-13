@echo off
REM  THU_CREDIT_2_MAY.bat - thu credit + "mot key mot may mot luc" voi HAI cua so app.
REM
REM  Cua so 1 = may nay (du lieu that). Cua so 2 = "may thu hai" gia (du lieu rieng
REM  trong %%TEMP%%\AutoTone_may_thu_hai, ma may THUMAYHAI001). Nhap CUNG mot key o ca
REM  hai: cua so mo sau phai hoi "Key dang dung tren may khac". Bam "Van truy cap"
REM  thi cua so kia dung moi viec va hien hop "May nay da bi day ra" trong <= 5 giay
REM  (dang chay viec) / <= 30 giay (ranh). Dong app KHONG nha key.
REM
REM  Can: Worker da deploy ban co credit (KeyActiveAutoTone\HUONG_DAN.md).
setlocal
cd /d "%~dp0"
git pull --ff-only
set PY=python
where py >nul 2>nul && set PY=py -3
start "AutoTone - may nay" %PY% autotone_gui.py
timeout /t 8 >nul
start "AutoTone - may thu hai" %PY% thu_may_thu_hai.py
echo.
echo Da mo 2 cua so. Xem so credit: menu ... ^> Credit ^& thiet bi...
endlocal
