@echo off
chcp 65001 >nul
rem Tao duong ham Cloudflare RIENG cho may nhan gop y (cong 8100) — KHONG dung chung voi findfaceid.
rem Chay MOT lan. Ten mien MOT cap (gopy-ai.saymedia.com.vn): chung chi mien phi cua Cloudflare
rem chi phu *.saymedia.com.vn — gopy.ai.saymedia.com.vn (hai cap) se loi SSL.
rem Doi ten mien thi sua CA gop_y.DIA_CHI_MAC_DINH trong app roi build lai.
set TEN_MIEN=gopy-ai.saymedia.com.vn
set CF="C:\Program Files (x86)\cloudflared\cloudflared.exe"
%CF% tunnel info autotone-gopy >nul 2>nul
if errorlevel 1 (
  %CF% tunnel create autotone-gopy
) else (
  echo Duong ham autotone-gopy da co san.
)
%CF% tunnel route dns autotone-gopy %TEN_MIEN%
echo.
echo Xong. Dia chi may nhan: https://%TEN_MIEN%
echo Bat may nhan + duong ham: chay_may_nhan.bat (hoac CHAY-TAT-CA.bat o F:\Claude AI).
pause
