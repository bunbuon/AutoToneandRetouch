# Kiểm thử bản .exe

Hai phần: **máy tự chạy** (một lệnh), và **anh bấm tay** (những gì máy không thay được).

---

## Phần 1 — Máy tự chạy

```powershell
cd "F:\Claude AI\AutoToneImages"

# 1. build lại  — BẮT BUỘC: bản .exe đang có vẫn còn lỗi jobs/
python dong_goi.py

# 2. kiểm gói, kèm ảnh RAW thật của buổi 0608
python kiem_goi.py "" "G:\0608"
```

Kết thúc phải là `GÓI ĐẠT`. Nếu ra `n VẤN ĐỀ` thì các dòng `[HONG]` nói rõ chỗ nào.

**Ảnh gốc chỉ được ĐỌC.** File `.xmp` được chép ra thư mục tạm rồi mới ghi thử — không đụng vào file thật của anh.

### Nó kiểm 21 mục, đáng chú ý là:

| Mục | Trả lời câu gì |
|---|---|
| Dữ liệu tách khỏi gói | App có ghi nhầm vào `Program Files` để rồi bị VirtualStore nuốt không |
| Plugin trong gói sạch | Gói có mang theo `jobs/` với bản xuất cũ không — **đúng lỗi hôm nay** |
| **Đọc RAW thật** | `read_raw()` có moi được preview trong file `.ARW` của Sony không |
| **Đo ảnh RAW thật** | Đo sáng + nhận mặt chạy được trên ảnh thật, không phải ảnh tự sinh |
| **Ghi .xmp rồi hoàn tác** | Bước duy nhất động vào file người dùng — ghi đúng, và **hoàn tác trả lại y nguyên byte** |
| **Job gửi Lightroom** | File `apply_*.tsv` có ghi ra đúng thư mục plugin không |
| Đo ảnh (6 cách đo) | Cả 6 cách đo đều chạy, không chỉ cách mặc định |
| Khoá hạn dùng | Mã máy ổn định, hạn tính đúng |
| tao_ma.py không lọt vào gói | Ai cầm gói không tự sinh được mã gia hạn |

Ba mục in đậm là mới — trước đây chỉ chạy trên một ảnh JPEG nhiễu tự sinh. Ảnh tự sinh không bao giờ lộ ra được chuyện preview nằm ở đâu trong file `.ARW` và to bao nhiêu; và nó cũng không chạm tới bước ghi `.xmp`, tức bước duy nhất có thể làm mất thông số cả buổi.

**Đã chạy thử ở đây trên 3 file `.ARW` thật lấy từ `G:\1308`:** preview 7008×4672, đọc được giờ chụp, nhận 3 khuôn mặt, ghi `Exposure2012` từ `+0.25` → `+1.25` rồi hoàn tác lại đúng bản gốc. Tôi cũng đã cố tình làm hỏng hàm hoàn tác để chắc bài kiểm bắt được — nó báo hỏng đúng như mong đợi.

---

## Phần 2 — Anh bấm tay

Máy không thay được phần này: nó cần Lightroom đang mở với catalog thật, và cần mắt người nhìn ảnh.

Chạy `dist\AutoTone\AutoTone.exe`. Đánh dấu từng dòng.

### Khâu 1 · Nạp ảnh
- [ ] Chọn thư mục `G:\0608` → hiện đúng **96 ảnh RAW**
- [ ] Chọn nguồn **Lightroom catalog qua plugin**
- [ ] Trong Lightroom: `Library → Plug-in Extras → AutoTone: xuất thông số`
- [ ] **Không bấm gì trong app cả**, chờ ~3 giây → dòng chữ tự chuyển sang xanh *"khớp đủ 96 ảnh"*

  Đây là chỗ hỏng hôm nay. Nếu vẫn đỏ, dòng chữ giờ nói rõ **đang đọc file nào, bao nhiêu tuổi, ở thư mục nào** — chụp lại gửi tôi là đủ để tìm ra ngay.

### Khâu 2 · Phân tích
- [ ] Bấm **Phân tích** → bảng hiện đủ 96 dòng
- [ ] Cột `EV` có số, không rỗng hàng loạt
- [ ] Cột `scene` chia ra vài cảnh hợp lý (không phải 96 cảnh, cũng không phải 1 cảnh)
- [ ] Đổi **Cách đo sáng** sang *Trung bình toàn khung* → bảng cập nhật, **không** báo lỗi đọc ảnh hàng loạt

  Mục cuối là lỗi tôi vừa sửa: 4 trong 6 cách đo từng làm mọi ảnh trả về *"không đọc được"*.

### Khâu 3 · Đẩy vào Lightroom
- [ ] Bấm ghi → app báo đã tạo job
- [ ] Trong Lightroom, ảnh **tự đổi thông số** (plugin tự áp)
- [ ] Mở `AutoTone.lrplugin\jobs\plugin.log`, dòng cuối ghi `ap N, ... 0 khong co trong catalog`

  Số `khong co trong catalog` > 0 nghĩa là đường dẫn lệch hoa/thường — báo tôi.

- [ ] Bấm **Hoàn tác** → thông số quay lại như trước

### Khâu 4 · Export
- [ ] Chạy export → ra đủ file JPEG
- [ ] Ảnh 1 sao **không** có trong thư mục xuất

### Khâu 5 · Retouch
- [ ] Bấm Retouch → chạy, không báo *"chưa sẵn sàng"*
- [ ] Mở 2–3 ảnh kết quả: da đã xử lý, **không phải ảnh gốc y nguyên**

  Nếu ra đúng ảnh gốc thì là lỗi cũ quay lại — báo tôi ngay.

### Khâu 6–7 · Vì sao tôi sửa / Gu đã học
- [ ] Sửa tay vài ảnh trong Lightroom → xuất lại → bấm **Vì sao tôi sửa** → ra danh sách đúng những ảnh đã sửa
- [ ] **Gu đã học** mở được, hiện nội dung

### Khoá hạn dùng
- [ ] Góc dưới trái hiện `Bản dùng thử · còn ... · máy XXXXXXXXXXXX`
- [ ] Số ngày còn lại đúng (hết hạn **01:00 ngày 07/09**)

---

## Phần 3 — Máy sạch (nếu định gửi cho người khác)

Máy build luôn có sẵn thư viện Python ở ngoài, nên một gói **thiếu file** vẫn chạy được ở đó mà chết trên máy khách. Chép thư mục gói sang máy chưa từng cài Python, mở PowerShell trong đó:

```powershell
$env:AUTOTONE_TU_KIEM = "$HOME\bao_cao.txt"
.\AutoTone.exe
notepad "$HOME\bao_cao.txt"
```

App chạy bài tự kiểm rồi thoát ngay, không mở cửa sổ. Dòng cuối file phải là `TAT CA DAT`.

---

## Cái tôi KHÔNG kiểm được, và anh nên biết

- **Bản Windows `.exe`.** Tôi build và chạy thử trên Linux, nên chứng minh được script build và toàn bộ đường xử lý là đúng — nhưng phần riêng của Windows (DLL, VirtualStore, tkinter trên Windows) thì chỉ máy anh trả lời được. Đó là việc của `kiem_goi.py`.
- **Bản macOS.** Chưa chạy lần nào.
- **Gói có kèm retouch.** Bản tôi build ở đây là bản không retouch (không có card NVIDIA để cài torch). Mục *"Công cụ retouch"* trong báo cáo sẽ nói rõ có hay không.
- **Chất lượng ảnh ra.** Không bài kiểm nào thay được mắt anh nhìn ảnh.
