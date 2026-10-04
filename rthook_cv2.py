# rthook_cv2.py — runtime hook: cố định đường dẫn cv2 native TRƯỚC khi import cv2.
#
# VÌ SAO (macOS .app, bản Cython): loader cv2 (cv2/__init__.py bootstrap) tính
# LOADER_DIR theo __file__ rồi tìm cv2.abi3.so cạnh đó. Nếu KHÔNG thấy (vì .app
# cross-link Frameworks/Resources, hoặc cv2 nằm trong thư mục con python-3.x),
# importlib nạp lại cv2/__init__ -> cờ sys.OpenCV_LOADER đã set -> ném
# "recursion is detected during loading of cv2 binary extensions".
#
# Hook này chèn thư mục chứa native cv2 (nếu là kiểu python-3.x) lên sys.path
# TRƯỚC sys._MEIPASS, để `import cv2` nạp đúng .so ngay lần đầu -> không tái nạp
# __init__ -> không recursion. Chỉ chạy trong gói đã đóng (frozen); chạy từ mã
# nguồn thì không làm gì. An toàn: chỉ chèn khi THẬT SỰ tìm thấy thư mục đó.
#
# Nguồn: PyInstaller discussion #7493 (runtime hook của user Joooshe, đã xác
# nhận hiệu quả cho cv2 recursion trên macOS .app).
import os
import sys

_meipass = getattr(sys, "_MEIPASS", None)
if _meipass and getattr(sys, "frozen", False):
    _cv2_root = os.path.join(_meipass, "cv2")
    _cv2_py = None
    if os.path.isdir(_cv2_root):
        try:
            for _name in os.listdir(_cv2_root):
                if _name.startswith("python-"):
                    _cand = os.path.join(_cv2_root, _name)
                    if os.path.isdir(_cand):
                        _cv2_py = _cand
                        break
        except OSError:
            _cv2_py = None
    if _cv2_py and _cv2_py not in sys.path:
        try:
            _i = sys.path.index(_meipass)
        except ValueError:
            _i = 0
        sys.path.insert(_i, _cv2_py)
