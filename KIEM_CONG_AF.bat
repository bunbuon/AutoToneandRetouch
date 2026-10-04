@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_CONG_AF.bat - chay CONG cho hai viec ve diem lay net (AF):
rem
rem    1. Xoay diem AF theo anh doc (Sony)  - DA BAT tu 29/9, cong nay do lai:
rem       luot goc = hanh vi CU (khong xoay), luot de xuat = co xoay.
rem    2. Doc vung AF cua Nikon dong Z       - DANG TAT, cho cong nay.
rem
rem  Luat "AF gan -> lay mat gan nhat" (af_gan_mat) da TRUOT cong B ngay 29/9
rem  (2.05%%, cho phep duoi 2%%) nen da bo, khong chay lai.
rem
rem  Hai cong dat TRUOC khi chay (kiem_gu.py), khong noi sau:
rem    A. anh ban da sua tay: keo LAI GAN >= day RA XA
rem    B. anh da duyet, khong sua: duoi 2%% bi xe dich qua 0.30 EV
rem
rem  KHONG can bam Phan tich truoc: dung ban xuat catalog moi nhat trong jobs.
rem  Chi can ban xuat do la CUA DUNG BUOI nay (file export_*.tsv moi nhat).
rem  Dong cua so AutoTone khi chay cho nhanh - may dung ca 8 nhan.
rem
rem  Cach dung: keo tha thu muc buoi len file nay, hoac nhap dup (= G:\2609).
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "BUOI=%~1"
if "%BUOI%"=="" set "BUOI=G:\2609"
set "OUT=%~dp0ket_qua_cong_af.txt"
set "PYTHONWARNINGS=ignore"
set "OPENCV_LOG_LEVEL=ERROR"

echo Buoi: %BUOI% > "%OUT%"
echo. >> "%OUT%"
echo ===== 1/2  XOAY DIEM AF THEO ANH DOC (doi chung voi hanh vi cu) ===== >> "%OUT%"
python kiem_gu.py "%BUOI%" --goc goc_af_cu.json --de-xuat de_xuat_af_xoay.json >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo ===== 2/2  VUNG AF NIKON (af_nikon) ===== >> "%OUT%"
python kiem_gu.py "%BUOI%" --de-xuat de_xuat_af_nikon.json >> "%OUT%" 2>&1

type "%OUT%"
echo.
echo Da ghi: %OUT%
pause
