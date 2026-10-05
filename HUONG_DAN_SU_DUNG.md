# Tone&Retouch — Hướng dẫn sử dụng

Tự động cân sáng, cân màu và retouch ảnh sự kiện cho **Lightroom Classic**.

---

## 1. Cài đặt

### Windows
1. Chạy file **`Tone-Retouch-Setup.exe`**.
2. Nếu Windows hiện cảnh báo xanh **"Windows protected your PC"** → bấm **More info** → **Run anyway**. (App chưa mua chứng chỉ ký số nên Windows cảnh báo lần đầu; đây là bình thường.)
3. Bấm **Next** → **Install** → **Finish**. App cài vào `C:\Program Files\Tone-Retouch`, tạo lối tắt ngoài Desktop và trong Start Menu.

### macOS
1. Mở file **`Tone-Retouch-macOS.dmg`**.
2. Kéo **Tone&Retouch** vào thư mục **Applications**.
3. Lần đầu mở: chuột phải vào app → **Open** → **Open** (vì chưa ký số). Những lần sau mở bình thường.

> **Dùng được ngay, không phải tải thêm.** Bản cài đã gồm **đầy đủ**: cân sáng, mô hình retouch, và thư viện xử lý AI (torch). Mở Retouch là thấy **đủ 8 tính năng** và chạy được luôn — không cần mạng, không phải tải gì. (Máy có card NVIDIA muốn chạy nhanh hơn trên card có thể tải thêm bản tăng tốc GPU — tuỳ chọn.)

---

## 2. Cài plugin vào Lightroom (chỉ làm 1 lần)

Để app đẩy thông số thẳng vào Lightroom, cần thêm plugin **một lần duy nhất**.

**Đường dẫn plugin sau khi cài (Windows):**
```
C:\Users\<tên-máy-của-bạn>\AppData\Local\AutoTone\AutoTone.lrplugin
```
(Thay `<tên-máy-của-bạn>` bằng tên tài khoản Windows. Thư mục `AppData` là thư mục ẩn — gõ thẳng đường dẫn trên vào thanh địa chỉ Explorer là tới.)

**Đường dẫn plugin trên macOS:**
```
~/Library/Application Support/AutoTone/AutoTone.lrplugin
```

**Cách thêm vào Lightroom:**
1. Mở **Lightroom Classic**.
2. **File → Plug-in Manager…**
3. Bấm **Add** (góc dưới bên trái).
4. Trỏ tới thư mục `AutoTone.lrplugin` ở đường dẫn trên.
5. Bấm **Done**.

> **Mẹo:** Không cần nhớ đường dẫn. Mở app → bấm nút **⋯** (góc trên) → **"Cài plugin…"**. App sẽ **hiện sẵn đường dẫn plugin của máy bạn** và cho bấm mở thẳng thư mục đó trong Explorer để copy.

> **Lưu ý:** thư mục plugin chỉ xuất hiện **sau khi bạn mở app lần đầu** (app tự chép plugin ra chỗ ghi được lúc chạy lần đầu). Nên hãy mở app một lần trước khi vào Lightroom tìm plugin.

Plugin chỉ sửa đúng **5 trường tone** (Exposure, Highlights, Shadows, Temperature, Tint) và giữ nguyên mọi chỉnh sửa khác của ảnh — an toàn hơn "Read Metadata from File" (vốn ghi đè toàn bộ).

---

## 3. Quy trình dùng cơ bản

Giao diện gồm: **thanh công cụ** trên cùng, **lưới ảnh** cả buổi ở giữa, **bảng điều khiển Cân tone / Retouch** bên phải.

1. **Chọn buổi chụp:** bấm nút **buổi ▾** (góc trái thanh công cụ) → **"Chọn thư mục buổi chụp…"** → trỏ tới thư mục ảnh RAW của buổi.

2. **Phân tích:** bấm **"1 · Phân tích"**. App đo sáng, cân màu, tách cảnh và lọc ảnh trùng cho cả buổi. Kết quả hiện trên lưới ảnh.

3. **Ghi và đẩy vào Lightroom:** bấm **"2 · Ghi và đẩy"**. Nếu đã cài plugin + Lightroom đang mở, thông số tone tự áp vào ảnh trong Lightroom sau vài giây.

4. **Export:** Export thẳng từ Lightroom như bình thường, hoặc dùng nút Export trong app.

5. **Retouch (xoá mụn, mịn da, dodge/burn…):** mở mô-đun **Retouch** (cột phải). Đủ 8 tính năng sẵn sàng ngay, không phải tải gì. Ảnh lớn ở trên để xem chi tiết + zoom, dải ảnh ở dưới để chọn ảnh.

**Các tính năng khác** (Duyệt nhanh, xuất báo cáo, hoàn tác, nhật ký plugin…) nằm trong menu **⋯** trên thanh công cụ.

---

## 4. Bản quyền

App dùng **key bản quyền**: nhập key một lần để kích hoạt. Khi chưa có key hoặc key hết hạn, app sẽ hiện ô **nhập key** — dán key vào đó và bấm kích hoạt. Liên hệ nơi bán để lấy key.

> Khi chưa kích hoạt, app chạy **thử 72 giờ** để bạn dùng thử.

---

## 5. Cập nhật app (không cần cài lại)

App tự kiểm bản mới khi mở. Có bản mới → app hỏi **"Có bản cập nhật, tải ngay?"** → bấm đồng ý, app tải về và **lần mở sau tự dùng bản mới** — **không phải cài lại**.

Muốn tự kiểm: menu **⋯** → **"Kiểm tra cập nhật…"**.

---

## 6. Xử lý nhanh vài trục trặc

| Hiện tượng | Cách xử lý |
|---|---|
| Không thấy thư mục plugin | Mở app lần đầu đã, rồi mới tìm (plugin chép ra lúc chạy lần đầu). Hoặc dùng ⋯ → "Cài plugin…" để app chỉ đường. |
| Bấm "2 · Ghi và đẩy" mà Lightroom không đổi | Mở Lightroom; **File → Plug-in Manager → AutoTone → Reload Plug-in**; chắc chắn đã Add đúng thư mục ở mục 2. |
| Retouch thiếu tính năng | Bản cài đầy đủ hiện sẵn 8 tính năng. Nếu chỉ thấy vài thanh kéo, bấm "Đọc lại tính năng" trong khung Retouch; vẫn thiếu thì báo lại để dựng bản mới. |
| Windows/macOS cảnh báo "nhà phát triển không xác định" | Bình thường (chưa ký số). Windows: More info → Run anyway. macOS: chuột phải → Open. |
| App mở báo hết hạn dùng thử | Nhập key bản quyền vào ô hiện trên màn hình. |

---

*Tone&Retouch — SAY MEDIA. Mã nguồn đã được bảo vệ (biên dịch sang mã máy). Không sao chép, dịch ngược.*
