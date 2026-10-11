@echo off
chcp 65001 >nul
rem Chay may nhan gop y (cong 8100) + duong ham Cloudflare autotone-gopy (de cua so nay mo).
rem Kho goi: xem "kho" trong may_nhan_gop_y.json (mac dinh %USERPROFILE%\AutoTone_GopY — o C:).
cd /d "%~dp0"
start "May nhan gop y - DE NGUYEN" cmd /k "cd /d "%~dp0" && set PYTHONIOENCODING=utf-8 && python may_nhan_gop_y.py"
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run --url http://127.0.0.1:8100 autotone-gopy
