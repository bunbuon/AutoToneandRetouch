#!/bin/bash
# ---------------------------------------------------------------------------
#  MO_PLUGIN_MAC.command — chi ra DUNG thu muc plugin phai Add vao Lightroom,
#  dung no neu chua co, roi mo Finder toi day.
#
#  CHI DOC + tao thu muc plugin. Khong dung vao anh, khong ghi .xmp.
# ---------------------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

PY=""
for ung_vien in "./.python_rieng/python/bin/python3" "python3"; do
  if command -v "$ung_vien" >/dev/null 2>&1 || [ -x "$ung_vien" ]; then
    PY="$ung_vien"; break
  fi
done
[ -z "$PY" ] && { echo "  [!] Khong thay python3."; read -r -p "  Enter..." _; exit 1; }

"$PY" chan_doan.py --plugin

#[[ Mo Finder toi thu muc Application Support. Khong the bam tay toi do vi
#   macOS AN thu muc ~/Library, nen mo ho la viec dang lam nhat o day. ]]
KHO="$HOME/Library/Application Support/AutoTone/AutoTone.lrplugin"
if [ -d "$KHO" ]; then
  echo
  echo "  Dang mo Finder toi:"
  echo "    $KHO"
  open -R "$KHO" 2>/dev/null
fi
echo
echo "  Trong Lightroom: File > Plug-in Manager > Add"
echo "  Bam Cmd+Shift+G roi dan duong dan o tren."
echo
read -r -p "  Enter de dong..." _
