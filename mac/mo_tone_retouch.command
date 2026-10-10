#!/bin/bash
# Mở Tone&Retouch trên macOS — double-click file này.
#
# 6/10: bản cũ chạy app ngầm với mọi đầu ra vào /dev/null rồi thoát ngay, nên
# app hỏng / bị macOS chặn thì cửa sổ chỉ báo "Quá trình đã hoàn thành" và
# không ai biết vì sao không thấy app. Bản này:
#   - gỡ cờ cách ly (com.apple.quarantine) macOS gắn cho file tải từ Internet —
#     app chưa ký số, còn cờ thì macOS chặn lặng lẽ thư viện bên trong
#   - chạy app tách khỏi Terminal (nohup: đóng cửa sổ Terminal app vẫn chạy)
#   - ghi nhật ký vào ~/Library/Logs/Tone-Retouch.log
#   - app thoát ngay trong 20 giây đầu thì in nhật ký ra đây và giữ cửa sổ

DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$DIR/AutoTone"
LOG="$HOME/Library/Logs/Tone-Retouch.log"
mkdir -p "$HOME/Library/Logs"

if [ ! -x "$APP" ]; then
  chmod +x "$APP" 2>/dev/null
fi
if [ ! -f "$APP" ]; then
  echo "Không thấy $APP"
  echo "Hãy để file này nằm CÙNG thư mục với AutoTone (kéo cả thư mục Tone&Retouch vào Applications)."
  read -r -p "Nhấn Enter để đóng…" _
  exit 1
fi

xattr -dr com.apple.quarantine "$DIR" 2>/dev/null

#  10/10: tải nhầm bản (Apple Silicon chạy trên Mac Intel -> "Bad CPU type in
#  executable") — nói rõ phải tải bản nào thay vì để macOS báo câu khó hiểu.
MAY="$(uname -m)"
LOAI="$(file "$APP" 2>/dev/null)"
if [ "$MAY" = "x86_64" ] && echo "$LOAI" | grep -q "arm64" && ! echo "$LOAI" | grep -q "x86_64"; then
  if [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" != "1" ]; then
    echo "Máy Mac này dùng CHIP INTEL, còn bản Tone&Retouch này dành cho Mac chip Apple"
    echo "(M1 / M2 / M3 / M4). Hãy tải bản \"Intel\" (Tone-Retouch-macOS-Intel.dmg)."
    read -r -p "Nhấn Enter để đóng…" _
    exit 1
  fi
fi
if [ "$MAY" = "arm64" ] && echo "$LOAI" | grep -q "x86_64" && ! echo "$LOAI" | grep -q "arm64"; then
  if ! /usr/bin/pgrep -q oahd 2>/dev/null; then
    echo "Bản này dành cho Mac chip Intel. Trên Mac chip Apple, nên tải bản \"AppleSilicon\""
    echo "(chạy nhanh hơn). Hoặc cài Rosetta để chạy bản này:  softwareupdate --install-rosetta"
    read -r -p "Nhấn Enter để đóng…" _
    exit 1
  fi
fi

echo "Đang mở Tone&Retouch… (lần đầu có thể mất 30–60 giây)"
echo "Nhật ký: $LOG"
nohup "$APP" >"$LOG" 2>&1 </dev/null &
PID=$!

for _i in $(seq 1 20); do
  sleep 1
  if ! kill -0 "$PID" 2>/dev/null; then
    echo
    echo "Tone&Retouch đã thoát ngay sau khi mở. Nhật ký:"
    echo "------------------------------------------------------------"
    tail -n 60 "$LOG"
    echo "------------------------------------------------------------"
    echo "Chụp màn hình phần trên gửi người hỗ trợ."
    read -r -p "Nhấn Enter để đóng…" _
    exit 1
  fi
done
echo "Đã mở. Có thể đóng cửa sổ Terminal này."
exit 0
