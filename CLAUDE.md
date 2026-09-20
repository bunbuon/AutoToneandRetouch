# AutoTone — ghi chú cho Claude làm việc trên dự án này

Viết cho phiên Claude nào mở kho này, ở bất kỳ máy nào. Đọc hết trước khi sửa
dòng đầu tiên. Mấy luật dưới đây không phải sở thích — mỗi cái đều đổi bằng một
lần hỏng thật, có ngày tháng.

## Dự án là gì

Tự động cân sáng / cân màu ảnh sự kiện cho Lightroom Classic. Bảy khâu:

1. Nạp ảnh
2. Phân tích — đo sáng, cân màu, tách cảnh, lọc ảnh trùng
3. Đẩy vào Lightroom — qua plugin Lua, kèm Duyệt nhanh và lưới soát màu
4. Export — đọc thư mục Export của Lightroom, hoặc Export thẳng từ app
5. Retouch — gọi tool ngoài (ToolCloneEvoto). Bản mac hiện TÁCH phần này ra.
6. Gói duyệt — "vì sao tôi sửa"
7. Gu đã học

Giao diện: Tkinter (`autotone_gui.py`). Lõi đo đạc: `autotone.py`. Plugin
Lightroom: `AutoTone.lrplugin/*.lua` (Lightroom Classic **chỉ** có SDK Lua —
không CEP, không UXP; Adobe đã nói rõ là không có trong lộ trình).

Người dùng nói tiếng Việt. **Trả lời bằng tiếng Việt.**

## Luật cứng

**Không bao giờ dựng lại logic sản xuất trong công cụ phân tích.** Bài kiểm và
script chẩn đoán phải GỌI chính hàm thật (`at.collect_pairs`, `at.measure`,
`rt.lenh`…). Chép lại logic thì bài kiểm đúng mà app vẫn sai — đã xảy ra.

**Bài kiểm phải được thử ngược.** Viết xong thì cố tình phá code cho nó đỏ, rồi
mới trả lại. Bài kiểm chưa từng đỏ là bài kiểm chưa biết nó canh cái gì.

**Không nới ngưỡng đã đặt.** Ngưỡng đặt TRƯỚC khi chạy. Không đạt thì bỏ phương
án và ghi lại vì sao, không hạ ngưỡng cho vừa kết quả.

**`tao_ma.py` không bao giờ rời máy Windows.** Nó dùng chung khoá bí mật với
`khoa.py`; ai có nó thì tự sinh mã gia hạn. `.gitignore` đã chặn, `dong_goi.py`
cũng loại nó khỏi gói. Đừng gỡ chặn ở bất kỳ đâu.

**ToolCloneEvoto là dự án RIÊNG** (`F:\Claude AI\ToolCloneEvoto` trên máy
Windows). Hỏi trước khi sửa gì bên đó.

**Ảnh 1 sao không xuất, không retouch.** Quy ước dùng chung ở mọi khâu.

## Cách viết chú thích, và một cái bẫy

Chú thích dài viết trong khối `#[[ ... #]]`, đặt trong docstring, giải thích
**vì sao** chứ không phải **làm gì** — kèm ngày tháng và con số đo được khi có.

Cái bẫy: khối đó nằm TRONG docstring, nên rất dễ quên dấu `"""` đóng. Quên thì
docstring nuốt luôn mấy chục dòng mã, và Python báo lỗi ở một dòng hoàn toàn
khác — thường là một chữ tiếng Việt trong docstring của hàm kế tiếp. Đã mắc bốn
lần trong hai ngày.

Chạy `python3 kiem_cu_phap.py` sau mỗi lần sửa. Nó nạp thử mọi file `.py` và
bắt lỗi này trong một giây.

## Bài kiểm

```
python3 kiem_cu_phap.py        # nạp thử mọi file .py — chạy đầu tiên
python3 kiem_mac.py            # mấy chỗ chỉ hỏng trên macOS
python3 kiem_dong_goi.py       # rà trước khi đóng gói
python3 kiem_bo_cuc.py         # bố cục giao diện, đọc mã nguồn
python3 kiem_moc_va_xuat.py    # mốc baseline và bản xuất catalog
python3 kiem_che_do_sang.py    # ngoài trời / trong nhà theo EV100
python3 kiem_xuat_lr.py        # khâu 5 — bắt đường dẫn Export
python3 kiem_tim_tool.py       # tìm tool retouch
python3 kiem_retouch_095.py    # nối với saytool 0.9.5
python3 kiem_duyet_py.py       # Duyệt nhanh, phía Python

# cần màn hình (macOS chạy thẳng; Linux dùng xvfb-run -a)
python3 kiem_man_hinh.py       # mở CẢ app, soi nhãn bị cắt
python3 kiem_ve_that.py        # co cột bằng Tk thật
python3 kiem_retouch_gui.py    # giao diện khâu Retouch

# cần lua5.1
lua5.1 kiem_duyet.lua AutoTone.lrplugin
lua5.1 kiem_batduongdan.lua AutoTone.lrplugin
lua5.1 kiem_xuatanh.lua AutoTone.lrplugin
lua5.1 kiem_dung_preview.lua AutoTone.lrplugin
```

## Chạy và đóng gói

```
python3 autotone_gui.py                    # chạy từ mã nguồn
python3 dong_goi.py --khong-retouch --khong-khoa   # đóng .app trên Mac
./CAI_DAT_MAC.command                      # tự tải Python riêng rồi đóng gói
python3 chan_doan.py "/thu/muc/anh"        # chẩn đoán khâu Phân tích
python3 chan_doan.py --anh "ANH.ARW"       # số đo thô một tấm, để so hai máy
python3 chan_doan.py --plugin              # thư mục plugin phải Add
```

## Chuyện đã học về macOS

- **File `._TÊN.ARW`** — rác resource fork macOS để lại khi chép qua exFAT/NTFS.
  Có đúng đuôi `.ARW` nên lọt bộ lọc; Finder không hiện. `collect_pairs` đã bỏ.
- **`os.path.normcase()` chỉ viết thường trên Windows.** Ổ mặc định của macOS
  (APFS, HFS+) lại KHÔNG phân biệt hoa thường. Dùng `at.khoa_duong_dan()`.
- **Thư mục plugin khác nhau tuỳ cách chạy**: chạy từ mã nguồn thì plugin nằm
  cạnh file `.py`; chạy từ `.app` thì ở
  `~/Library/Application Support/AutoTone/AutoTone.lrplugin`. Add nhầm bản thì
  Lightroom ghi một nơi, app đọc một nơi, không bên nào báo lỗi.
- **stdout của tiến trình con** lấy mã trang hệ thống (cp1252 trên Windows) và
  đệm theo khối 8 KB. Ép `PYTHONIOENCODING`, `PYTHONUTF8`, `PYTHONUNBUFFERED`,
  và để JSON ở dạng thuần ASCII.
- **Không build chéo được.** `.app` phải build trên Mac, `.exe` trên Windows.

## Đang treo: ΔEV lệch giữa Windows và Mac

Cùng một tấm (ví dụ `03142`), cùng một bộ 64 ảnh: Windows ra **−0.26**, Mac ra
**+1.20**. Lệch ~1.46 EV.

Đã loại trừ: số ảnh trong mẻ (người dùng đã chạy cùng bộ).

Đã loại trừ: số ảnh trong mẻ; và **`gu.json` không hề tồn tại trên máy
Windows** (đã kiểm cả `%LOCALAPPDATA%\AutoTone` lẫn thư mục dự án) — tức hai
máy cùng chạy bằng DEFAULTS, không phải chuyện tham số đã học.

Còn lại, theo thứ tự khả năng:

1. **Bộ nhận diện mặt không chạy trên một trong hai máy.** Đây là nghi phạm
   hàng đầu. Ở chế độ đo `face`, ảnh thấy mặt đo theo thang MẶT, ảnh không thấy
   mặt lùi về thang CHỦ THỂ, và `decide()` bù chênh bằng trung vị của những ảnh
   có CẢ HAI. Không máy nào thấy mặt thì không còn gì để bù, bù thành 0, trong
   khi mục đích vẫn lấy theo `face_target_ev` — lệch cả mẻ một khoảng gần như
   cố định. Đúng hình dạng của 1,46 EV. Và `face_detector()` **nuốt mọi lỗi**
   rồi trả None, nên nhìn từ ngoài không có dấu hiệu gì.
   `chan_doan.py --anh` giờ in thẳng: có `metered_face_ev` hay không.
2. **Tuỳ chọn trên giao diện khác nhau** — mức đích, chế độ, cách đo, luật tách
   cảnh. Chúng KHÔNG được lưu giữa các lần chạy, nên mỗi máy khởi động bằng
   DEFAULTS; nhưng nếu người dùng đã chỉnh trên Windows trong phiên đang mở thì
   hai bên khác nhau thật.
3. **Bản xuất catalog** — cho biết ảnh đang có sẵn Exposure bao nhiêu.
4. **Thư viện giải nén** (numpy / Pillow) đọc preview ra khác nhau.

Cách phân biệt: chạy `chan_doan.py --anh` trên CẢ HAI máy rồi so. Số đo thô
giống nhau → lỗi ở (1) hoặc (2). Số đo thô đã khác → lỗi ở (3).
