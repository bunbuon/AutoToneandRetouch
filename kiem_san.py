#!/usr/bin/env python3
"""ĐÃ GỘP VÀO kiem_gu.py — file này chỉ còn để chỉ đường.

VÌ SAO GỘP
    kiem_san.py và kiem_gu.py làm y hệt một việc: chạy analyze()+plan() hai
    lượt rồi chấm hai cổng. Khác nhau đúng chỗ kiem_san chỉ đổi được một tham
    số cứng (scene_aim_slack_ev), còn kiem_gu nhận file JSON đổi tham số bất kỳ.

    Hai bản sao của cùng một cổng là thứ chắc chắn trôi khỏi nhau: sửa cổng ở
    một bên rồi quên bên kia, và từ đó hai file cho hai kết luận khác nhau về
    cùng một đề xuất — không ai biết bên nào đúng. Nên chỉ giữ một.

CHUYỂN LỆNH THẾ NÀO
    cũ:  python kiem_san.py G:\\0306 --ti-le 3.0
    mới: viết đề xuất ra JSON rồi
         python kiem_gu.py G:\\0306 --de-xuat de_xuat.json

    Các cờ --cap và --chuan đã được chuyển nguyên sang kiem_gu.py.
"""
import sys

print(__doc__)
sys.exit(2)
