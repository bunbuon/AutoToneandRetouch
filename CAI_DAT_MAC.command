#!/bin/bash
# ---------------------------------------------------------------------------
#  CAI_DAT_MAC.command — bam dup MOT LAN, ra AutoTone.app va AutoTone.dmg.
#
#  KHONG can cai Python. KHONG can Homebrew. KHONG can go lenh.
#  Script tu tai mot ban Python rieng (~15 MB, co san Tk 8.6), dung no de dong
#  goi, roi tu xoa dau vet — khong dong vao Python hay Tk cua may.
#
#  Neu macOS bao "khong mo duoc vi chua duoc xac minh":
#      chuot phai vao file nay -> Open -> Open.
# ---------------------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

BAN_PY="3.12.11"
MOC="20250723"
KHO=".python_rieng"

dung_lai() {                      # in loi roi cho bam Enter, de bam dup thay duoc
  echo
  echo "  [!] $1"
  [ -n "${2:-}" ] && { echo; echo "$2"; }
  echo
  read -r -p "  Enter de dong..." _
  exit 1
}

echo
echo "  ================================================"
echo "     Cai dat AutoTone cho macOS  (ban KHONG kem Retouch)"
echo "  ================================================"
echo

#[[ 1 — KIEN TRUC MAY.
#
#   PyInstaller ra ban theo dung kien truc may dang chay. Khong lam ban
#   universal2 duoc vi torch khong co ban universal.
#]]
may=$(uname -m)
case "$may" in
  arm64)
    KT="aarch64"
    SHA="141272e6c6ae945b61fcf4073b7419451f8227187b3667b01ea9ec8993e0d7e9"
    TEN_MAY="Apple Silicon" ;;
  x86_64)
    KT="x86_64"
    SHA="1f152ee0dcc6ac5db93e39d74f0c50e319863d65fea0aab04e2e1b3f49b87f5f"
    TEN_MAY="Intel" ;;
  *)
    dung_lai "Khong nhan ra kien truc may: $may" ;;
esac
echo "  May      : $TEN_MAY ($may)"

PY="$PWD/$KHO/python/bin/python3"

#[[ 2 — TAI BAN PYTHON RIENG.
#
#   VI SAO KHONG DUNG PYTHON CUA MAY
#     /usr/bin/python3 cua macOS di kem Tk 8.5. PyInstaller dong theo dung ban
#     Tk cua Python dung de build, nen goi se mang Tk 8.5 — va tren macOS doi
#     moi, Tk 8.5 ve giao dien vo chu, o nhap khong an chuot. Luc build KHONG
#     bao loi gi; chi mo app ra moi thay.
#
#     Ban python-build-standalone mang san Tcl/Tk 8.6 ben trong, nam gon trong
#     thu muc du an, khong cai gi vao he thong, go thi chi viec xoa thu muc.
#]]
if [ ! -x "$PY" ]; then
  echo "  Python   : chua co — dang tai ban rieng 15 MB..."
  echo
  mkdir -p "$KHO" || dung_lai "Khong tao duoc thu muc $KHO"
  URL="https://github.com/astral-sh/python-build-standalone/releases/download/${MOC}/cpython-${BAN_PY}+${MOC}-${KT}-apple-darwin-install_only.tar.gz"
  GOI="$KHO/python.tar.gz"

  ok=0
  for lan in 1 2; do
    if curl -fL --progress-bar -o "$GOI" "$URL"; then ok=1; break; fi
    echo "  [!] Tai hong (lan $lan). Thu lai..."
    sleep 2
  done
  [ "$ok" = 1 ] || dung_lai "Khong tai duoc Python." \
    "      Kiem lai mang, roi bam dup file nay lan nua."

  #[[ Doi chieu SHA256. Tai thieu vai byte thi file van giai nen duoc mot phan,
  #   roi hong o mot buoc nao do rat xa sau nay va khong ai doan ra vi sao.
  #]]
  echo "  Doi chieu ma bam..."
  that=$(shasum -a 256 "$GOI" | cut -d' ' -f1)
  if [ "$that" != "$SHA" ]; then
    rm -f "$GOI"
    dung_lai "File tai ve khong khop ma bam — da xoa." \
"      Cho    : $SHA
      Nhan   : $that
      Thuong la mang dut giua chung. Bam dup lai file nay."
  fi

  tar xzf "$GOI" -C "$KHO" || dung_lai "Giai nen that bai."
  rm -f "$GOI"
  [ -x "$PY" ] || dung_lai "Giai nen xong nhung khong thay $PY"
fi

#[[ 3 — Kiem lai Tk NGAY TREN ban vua tai. Khong tin suong.
#]]
tk=$("$PY" -c 'import tkinter;print(tkinter.TkVersion)' 2>/dev/null)
case "$tk" in
  8.6|8.7|9.*) ;;
  *) dung_lai "Ban Python vua tai bao Tk='$tk', khong phai 8.6 tro len." ;;
esac
echo "  Python   : $("$PY" -c 'import sys;print(sys.version.split()[0])') · Tk $tk  (rieng, trong thu muc du an)"
echo

#[[ 4 — Thu vien, cai VAO CHINH ban Python rieng do.
#]]
echo "  Cai thu vien (lan dau 2-5 phut)..."
"$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1
"$PY" -m pip install --quiet pyinstaller pillow numpy opencv-python-headless \
  || dung_lai "Cai thu vien that bai." "      Thuong la do mang. Bam dup lai file nay."

#[[ 5 — Co ToolCloneEvoto tren may nay khong.
#
#   dong_goi.py TU CHOI chay neu khong thay tool retouch ma cung khong duoc
#   bao truoc — de nguoi dung khoi vo tinh ra mot goi thieu tinh nang ma
#   khong biet. O day ta do truoc va noi ro, thay vi de no dung giua chung.
#]]
#[[ BO NAY DA CO Y TACH RIENG PHAN RETOUCH.
#
#   Tool retouch (ToolCloneEvoto) dang duoc toi uu toc do nen tam de ngoai:
#   bo nay KHONG mang retouch.py, khong mang saytool, khong mang mo hinh, va
#   khong keo torch / mediapipe / insightface vao goi. Nho vay bo nhe di hang
#   GB va build nhanh hon nhieu.
#
#   Ep --khong-retouch o day thay vi de script tu do: neu sau nay ai do chep
#   ToolCloneEvoto sang may Mac, ban tu do se lang le dong ca phan retouch vao
#   — ra mot goi khac han thu dinh giao, ma khong ai bao gi. Muon co lai thi
#   xoa hai chu do o dong duoi, co y va nhin thay duoc.
#
#   --khong-khoa: ban nay chay tren may cua chinh anh de thu, khong dat han
#   dung thu. Xem chot_khoa() trong dong_goi.py ve vi sao phai noi ro.
#]]
THEM="--khong-retouch --khong-khoa"
if [ $# -eq 0 ]; then
  echo
  echo "  [ ] Ban nay TACH RIENG phan Retouch (dang toi uu toc do)."
  echo "      -> Dong goi sau khau: nap anh, phan tich, day vao Lightroom,"
  echo "         Export, goi duyet, hoc gu. Khau Retouch se bao la da tach."
fi

#[[ 6 — Dong goi.
#]]
echo
echo "  Bat dau dong goi (10-40 phut). Dung dong cua so nay."
echo
"$PY" dong_goi.py $THEM "$@" || dung_lai "Dong goi that bai (xem dong [!] o tren)."

APP="dist/AutoTone.app"
[ -d "$APP" ] || dung_lai "Dong goi xong nhung khong thay $APP"

#[[ 7 — Ky ad-hoc va go co cach ly.
#
#   Tren Apple Silicon, file thuc thi BUOC PHAI co chu ky, du la chu ky rong.
#   PyInstaller thuong tu ky, nhung ky lai o day thi chac chan hon va khong hai
#   gi. Con com.apple.quarantine la co macOS dan len thu tai tu mang.
#]]
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP" >/dev/null 2>&1 \
    && echo "  Da ky ad-hoc cho $APP"
fi
xattr -dr com.apple.quarantine "$APP" 2>/dev/null

#[[ 8 — Tao .dmg de cai nhu app thuong.
#]]
echo "  Dang tao file cai dat .dmg..."
rm -rf dist/dmg dist/AutoTone.dmg
mkdir -p dist/dmg
ditto "$APP" "dist/dmg/AutoTone.app" || dung_lai "Chep app vao dmg that bai."
ln -s /Applications dist/dmg/Applications
if hdiutil create -volname "AutoTone" -srcfolder dist/dmg -ov -format UDZO \
        dist/AutoTone.dmg >/dev/null 2>&1; then
  rm -rf dist/dmg
  co_dmg=1
else
  echo "  [!] Khong tao duoc .dmg — khong sao, dung thang $APP cung duoc."
  co_dmg=0
fi

#[[ 9 — Kiem goi vua tao. Chay CHINH con app do: do anh that, ghi .xmp that
#   roi hoan tac. Dat o day nghia la app chay duoc that, khong phai chi
#   "build khong bao loi".
#]]
echo
echo "  Dang kiem lai goi vua tao..."
echo
"$PY" kiem_goi.py "$APP"
ma_kiem=$?

echo
echo "  ================================================"
if [ $ma_kiem -eq 0 ]; then
  echo "     XONG"
else
  echo "     XONG — NHUNG BAI KIEM CO LOI (xem cac dong [!] o tren)"
fi
echo "  ================================================"
echo
if [ "$co_dmg" = 1 ]; then
  echo "  File cai dat : $PWD/dist/AutoTone.dmg"
  echo
  echo "  CACH CAI:"
  echo "    1. Bam dup AutoTone.dmg"
  echo "    2. Keo bieu tuong AutoTone vao thu muc Applications ben canh"
  echo "    3. Lan dau mo: chuot phai vao AutoTone -> Open -> Open"
else
  echo "  App : $PWD/$APP"
fi
echo
echo "  Muon dong goi lai sau khi sua code: bam dup lai chinh file nay."
echo "  Ban Python rieng nam trong $KHO — xoa thu muc do la sach hoan toan."
echo
open dist 2>/dev/null
read -r -p "  Enter de dong..." _
