@echo off
rem ---------------------------------------------------------------------------
rem  DON_O_C.bat - bam dup vao file nay de chay don_o_c.ps1
rem
rem  VI SAO CAN FILE NAY
rem      Windows chan chay file .ps1 theo mac dinh (Execution Policy = Restricted).
rem      Do la thiet lap cua may, khong phai loi cua script. File .bat nay goi
rem      PowerShell kem -ExecutionPolicy Bypass, tuc chi bo qua cho DUNG MOT lan
rem      chay nay - khong doi thiet lap cua may, khong can quyen admin.
rem
rem      Cach nay con tranh mot cai bay nua: khi chep lenh tu chat/web vao
rem      PowerShell, dau gach ngang "-" hay bi doi thanh dau gach dai "-" va
rem      PowerShell khong nhan ra tham so. O day khong phai go gi nen khong dinh.
rem
rem  KHONG DAT DAU TIENG VIET TRONG FILE NAY
rem      File .bat chay o code page cua console; co dau tieng viet la ra chu
rem      loan xi. Moi chu tieng viet deu do don_o_c.ps1 in ra, khong phai file nay.
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if not exist "%~dp0don_o_c.ps1" (
  echo.
  echo   [!] Khong thay don_o_c.ps1 canh file nay.
  echo       Hai file phai nam chung mot thu muc.
  echo.
  pause
  exit /b 1
)

:menu
echo.
echo   ============================================
echo    Don du lieu hai du an khoi o C
echo   ============================================
echo.
echo    -- Phan A: mo hinh nhan mat (724 MB) --
echo    1 = CHI XEM        (do dung luong, khong dung gi ca)
echo    2 = CHUYEN THAT    (chuyen sang F va xoa file zip thua)
echo.
echo    -- Phan B: torch 3 GB. Lam DUNG THU TU 4 -^> 5 -^> 6 --
echo    4 = Buoc 1  Cai torch vao .venv tren F
echo    5 = Buoc 2  KIEM retouch chay duoc bang .venv chua
echo    6 = Buoc 3  Go torch khoi o C  (chi chay duoc khi buoc 2 da dat)
echo    7 = Xem dang o buoc nao
echo.
echo    -- Van day o C ma khong biet vi sao --
echo    8 = QUET CA O C, xep hang thu muc chiem nhieu nhat
echo.
echo    3 = Thoat
echo.
set "chon="
set /p chon="   Go so roi bam Enter: "

if "%chon%"=="1" goto xem
if "%chon%"=="2" goto chay
if "%chon%"=="3" exit /b 0
if "%chon%"=="4" goto t1
if "%chon%"=="5" goto t2
if "%chon%"=="6" goto t3
if "%chon%"=="7" goto t0
if "%chon%"=="8" goto quet
echo   Chua hieu. Go dung mot trong cac so tren.
goto menu

:xem
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0don_o_c.ps1"
goto xong

:chay
echo.
echo   Truoc khi chuyen: DONG AutoTone va moi cua so Python lai.
echo   Chuyen luc file dang mo se de lai nua tren F nua tren C.
echo.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0don_o_c.ps1" -Chay -XoaZipThua
goto xong

rem --- Quet ca o C. Chi DOC, khong sua gi. ---
:quet
echo.
echo   Quet mat 1-4 phut. Chi doc, khong xoa gi ca.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0quet_o_c.ps1"
goto xong

rem --- Phan B: torch. chuyen_torch.ps1 tu chan thu tu, khong the nhay coc. ---
:t0
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chuyen_torch.ps1"
goto xong

:t1
echo.
echo   Buoc 1 se tai ve khoang 2.5 GB torch. Tuy mang, co the mat 10-40 phut.
echo   DONG AutoTone va moi cua so Python lai truoc da.
echo.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chuyen_torch.ps1" -Buoc1
goto xong

:t2
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chuyen_torch.ps1" -Buoc2
goto xong

:t3
echo.
echo   Buoc 3 go torch khoi Python tren o C. Khong lui lai duoc neu chua chac.
echo   Chi chay sau khi buoc 2 da DAT - script tu tu choi neu chua.
echo.
pause
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chuyen_torch.ps1" -Buoc3
goto xong

:xong
echo.
pause
