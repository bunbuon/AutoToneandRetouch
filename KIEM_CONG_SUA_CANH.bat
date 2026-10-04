@echo off
rem ---------------------------------------------------------------------------
rem  KIEM_CONG_SUA_CANH.bat - chay CONG cho hai ban sua ngay 29/9 (dang TAT).
rem
rem    1. mat_lech_khung_ev = 0.5     phep do mat lech khoi khung (NDT09826)
rem    2. trong_ngoai_min_shots = 3   nhan ngay/den nhap nhay mot tam
rem
rem  Hai cong dat TRUOC khi chay, khong noi sau (xem kiem_gu.py):
rem    A. anh nguoi dung da sua tay: keo LAI GAN >= day RA XA
rem    B. anh da duyet, khong sua: duoi 2% bi xe dich qua 0.30 EV
rem
rem  TRUOC KHI CHAY: mo AutoTone, chon thu muc buoi (mac dinh G:\1308), bam
rem  "1 - Phan tich" mot lan de Lightroom xuat ban catalog MOI cua buoi do.
rem  kiem_gu.py lay ban xuat moi nhat trong thu muc jobs.
rem
rem  Cach dung:  keo tha thu muc buoi len file nay, hoac nhap dup (= G:\1308)
rem  Ket qua ghi vao ket_qua_cong_29-9.txt canh file nay.
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set "BUOI=%~1"
if "%BUOI%"=="" set "BUOI=G:\1308"
set "OUT=%~dp0ket_qua_cong_29-9.txt"

echo Buoi: %BUOI% > "%OUT%"
echo. >> "%OUT%"
echo ===== 1/2  mat_lech_khung_ev = 0.5  (cham cong A tren nhom do-nham-mat) ===== >> "%OUT%"
python kiem_gu.py "%BUOI%" --de-xuat de_xuat_mat_lech_khung.json --nhom do-nham-mat >> "%OUT%" 2>&1
echo. >> "%OUT%"
echo ===== 2/2  trong_ngoai_min_shots = 3 ===== >> "%OUT%"
python kiem_gu.py "%BUOI%" --de-xuat de_xuat_trong_ngoai.json >> "%OUT%" 2>&1

type "%OUT%"
echo.
echo Da ghi: %OUT%
pause
