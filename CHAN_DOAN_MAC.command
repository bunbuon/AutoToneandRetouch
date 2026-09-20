#!/bin/bash
# ---------------------------------------------------------------------------
#  CHAN_DOAN_MAC.command — bam dup, keo tha thu muc anh vao, ra file bao cao.
#
#  CHI DOC. Khong sua file nao, khong ghi .xmp, khong dong vao anh cua ban.
#
#  Ket qua ghi ra:  chan_doan.txt  (nam canh file nay)
#  Gui file do ve la du de truy loi.
# ---------------------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

echo
echo "  ================================================"
echo "     Chan doan khau Phan tich"
echo "  ================================================"
echo

#[[ Uu tien ban Python RIENG ma CAI_DAT_MAC.command da tai ve: no co dung bo
#   thu vien ma app dung (numpy, PIL, opencv). Python cua he thong thuong
#   thieu chung, va luc do bai chan doan se bao "THIEU numpy" — dung nhung
#   khong phai cai dang hoi, va lam nguoi doc di sai huong. ]]
PY=""
for ung_vien in "./.python_rieng/python/bin/python3" "python3"; do
  if command -v "$ung_vien" >/dev/null 2>&1 || [ -x "$ung_vien" ]; then
    PY="$ung_vien"; break
  fi
done
if [ -z "$PY" ]; then
  echo "  [!] Khong thay python3 tren may nay."
  read -r -p "  Enter de dong..." _
  exit 1
fi
echo "  Python: $PY"
echo

TM="$1"
if [ -z "$TM" ]; then
  echo "  KEO THA thu muc anh vao cua so nay roi bam Enter."
  echo "  (keo cai THU MUC, khong phai mot tam anh)"
  echo
  read -r -p "  Thu muc: " TM
fi

#[[ Keo tha vao Terminal se dan duong dan co dau nhay hoac co "\ " thay cho
#   dau cach. Bo chung di, neu khong thi Path() nhan mot duong dan khong ton
#   tai va bai chan doan dung ngay o dong dau. ]]
TM="${TM%\"}"; TM="${TM#\"}"
TM="${TM%\'}"; TM="${TM#\'}"
TM="$(printf '%s' "$TM" | sed 's/\\ / /g')"

echo
"$PY" chan_doan.py "$TM"
ma=$?

echo
if [ -f chan_doan.txt ]; then
  echo "  Da ghi: $PWD/chan_doan.txt"
  echo "  Gui file do ve de truy loi."
  open -R chan_doan.txt 2>/dev/null
fi
echo
read -r -p "  Enter de dong..." _
exit $ma
