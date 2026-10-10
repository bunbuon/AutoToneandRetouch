# Khâu 5 · Export — hai đường, chọn đường nào cũng được

Trước đây khâu 5 phải hỏi tay "anh Export ra đâu?". Lý do thật, không phải làm
biếng: **Lightroom không phát sự kiện Export nào và không để lại dấu vết nào
trên đĩa**, nên đứng ngoài thì không có cách gì biết. Giờ có hai đường, và
chúng độc lập — hỏng đường này thì đường kia vẫn chạy.

---

## Đường 1 · Anh vẫn Export bằng Lightroom, app tự biết thư mục

Plugin cắm một **Export Filter** vào chính luồng Export, nên nó đọc được thư
mục đích từ bảng thông số anh vừa chọn.

### Làm một lần duy nhất

1. Lightroom → **Plug-in Manager → Reload** (bản plugin mới).
2. Chọn ảnh → **File → Export…**
3. Cột trái hộp thoại, kéo xuống mục **Post-Process Actions**.
4. Chọn **"AutoTone: ghi lại thư mục Export"** → bấm **Insert**.
5. Bấm **Add** để lưu thành preset (hoặc **Update** preset đang dùng).

Xong. Từ đó mọi lần Export bằng preset ấy — kể cả **Export with Previous** —
app tự biết ảnh ra đâu. Ở khâu 5 sẽ hiện một dòng:

- *"Lightroom vừa Export ra F:\Giao\2705 (08/09 14:22)"* → bấm **Dùng đường dẫn này**
- *"Khớp với lần Export gần nhất"* → không phải làm gì
- *"Lightroom Export gần nhất ra một chỗ KHÁC…"* → xem lại, có thể anh gõ nhầm

App **không bao giờ tự thay** đường dẫn anh đã gõ. Nó chỉ gợi ý.

### Filter đó có động vào ảnh không

Không. Nó chỉ khai `shouldRenderPhoto` — hàm Lightroom hỏi *trước* khi render,
đại ý "ảnh này có xuất không". Plugin luôn trả lời **có**, cho mọi ảnh, và nhân
tiện chép lại đường dẫn.

Cách còn lại (`postProcessRenderedPhotos`) thì plugin **nằm chắn ngang** đường
ảnh đi ra: Lightroom render vào thư mục tạm rồi giao cho plugin tự chuyển từng
file về đích. Buổi 2000 ảnh mà thư mục tạm khác ổ là 2000 lần chép thật, và một
lỗi ở đó là hỏng cả buổi giao khách. Không đáng, chỉ để biết một đường dẫn.

Bài kiểm `kiem_batduongdan.lua` canh đúng chuyện này: nó ép cho phần ghi file
hỏng thật rồi kiểm rằng ảnh **vẫn ra đủ**.

---

## Đường 2 · Bấm nút trong app, Lightroom xuất

Ở khâu 5, phần **"Hoặc để app Export luôn"**. Không mở hộp thoại nào. Thư mục
đích là ô **Thư mục Export** ở ngay trên.

### Thông số lấy ở đâu

App **không** dựng lại hộp thoại Export (gần bốn chục ô — quên một ô là ảnh
giao khách khác với ảnh anh vẫn giao), và **không** tự nghĩ ra thông số. Nó đọc
đúng thông số Lightroom đang dùng:

```
%APPDATA%\Adobe\Lightroom\Preferences\Lightroom Classic CC 7 Preferences.agprefs
```

Mọi khoá `AgExport_*` trong đó chính là thông số lần Export gần nhất của anh.
Máy này hiện đang là:

> JPEG · chất lượng 70 · nguyên cỡ · sRGB · đổi tên `{{custom_token}}-{{image_filename_number_suffix}}` (custom = `SAY-Media`)

Dòng chữ trong app hiện đúng bảng này kèm **thời điểm đọc được** — vì Lightroom
ghi file cấu hình theo nhịp của nó, không ghi ngay lúc bấm OK, nên bảng có thể
cũ hơn lần Export gần nhất. Liếc con số ngày giờ trước khi bấm.

Đọc không được thì **nút bị khoá**. Cố tình: bịa thông số cho ảnh giao khách là
kiểu sai tệ nhất — ảnh vẫn ra, nhìn qua vẫn đẹp, nhưng khác hẳn thứ anh vẫn giao.

### Ba thứ app luôn đặt đè, và vì sao

| Khoá | App đặt | Vì sao |
|---|---|---|
| `collisionHandling` | anh chọn ở ô **Trùng tên** | Của anh đang là `ask` — Lightroom sẽ dựng hộp thoại giữa chừng mà vòng lặp nền không có ai bấm. Nhìn từ ngoài giống hệt "app treo". |
| `export_postProcessing` | `doNothing` | Không mở Explorer sau mỗi lô. |
| `reimportExportedPhoto` | `false` | Không ném ảnh vừa xuất ngược vào catalog. |

Ảnh **1 sao không được xuất** (ô "Bỏ ảnh 1 sao", mặc định bật) — cùng quy ước
với `burst_reject_rating` và với khâu 3.

### Dừng giữa chừng

Nút **Dừng** đặt một file cờ; plugin kiểm **giữa hai lô**. Nên có thể còn chạy
thêm tới 15 ảnh nữa rồi mới dừng — cắt ngang một lô đang render sẽ để lại file
dở trên đĩa. Số ảnh đã ra vẫn dùng được bình thường.

---

## Đường 3 · Nút **3 · Xuất** — một thao tác: Lightroom xuất, app retouch (9/10)

Trên thanh công cụ Cân tone, cạnh "2 · Ghi": **3 · Xuất** (cũng có trong menu ⋯
của Retouch). Bấm là hiện hộp thoại, mọi lựa chọn được nhớ cho lần sau:

1. **Chất lượng JPEG** 1–100 (mặc định lấy số Lightroom đang dùng). Kích thước,
   không gian màu, metadata, quy tắc đặt tên vẫn theo thông số Export của Lightroom.
2. **Thư mục xuất** + Lightroom gặp file trùng tên: ghi đè / bỏ qua / đổi tên; bỏ ảnh 1 sao.
   **Chỉ xuất ảnh chưa gắn sao** (9/10): ảnh có sao (1–5) là ảnh đã lọc — lọc trùng
   khung / nhắm mắt của tool gắn sao, hoặc anh tự gắn — nên không xuất. Buổi đã lọc
   thì công tắc này tự bật và nói số ảnh sẽ bỏ; bật thì ô "bỏ ảnh 1 sao" thừa nên khoá.
3. **Ảnh retouch ghi ở đâu**: thư mục riêng `<xuất>_retouch` (mặc định) hay ghi đè
   lên chính ảnh Lightroom vừa xuất (hỏi lại, không lùi được).
4. **Cache xem trước**: dung lượng (mặc định 2 GB), xem đang dùng bao nhiêu, nút xoá.
   Ảnh xem trước retouch đã tính được giữ lại: mở lại thư mục hay đang chạy mẻ vẫn
   bấm xem được ngay; vượt dung lượng thì tự xoá tấm lâu không xem nhất.
5. **Xuất ảnh đâu retouch đó**: bật = retouch ngay trong lúc Lightroom đang xuất
   (song song); tắt = retouch sau khi xuất xong. Chọn **preset** retouch cho cả lượt.

Hộp thoại **đo máy** (RAM trống, VRAM card NVIDIA, CPU, ổ đích). Vừa xuất vừa
retouch cần ≥ 6 GB RAM trống, card NVIDIA có ≥ 4 GB VRAM — thiếu thì app
**tự đổi sang "retouch sau khi xuất xong"** và nói lý do; muốn ép vẫn có ô "Vẫn
chạy song song". (10/10: xét **dung lượng card**, không xét "VRAM trống" — trên
Windows trình duyệt, Zalo… giữ vài GB VRAM mà Windows dồn ra RAM được, nên số
"trống" luôn thấp và từng chặn oan lượt chạy song song.) Khi chạy song song:
retouch 1 luồng, chế độ tiết kiệm; RAM trống dưới 1,5 GB thì tạm ngưng nhận ảnh
mới tới khi hồi.

## Retouch ngay trong Export của Lightroom (10/10)

Không cần bấm "3 · Xuất" trong app: Export bằng Lightroom như mọi khi, ảnh ra thư mục
đích đã được retouch.

1. Hộp **Export** của Lightroom › cột trái, mục **Post-Process Actions** › **AutoTone
   (SAY Media)** › chọn **"AutoTone: Retouch khi xuất"** › **Insert**.
2. Ở phần "AutoTone — Retouch khi xuất" bên phải: để tích **Retouch ảnh xuất ra**;
   **Mức retouch** = "Theo app" (mức / preset đã đặt cho buổi trong màn Retouch — đúng
   như preview) hoặc chọn hẳn một preset retouch.
3. **Lưu vào Export preset** (Add ở cột trái) — từ đó Export bằng preset này (kể cả
   Export with Previous) là có retouch, không phải tích lại.

Mô hình nạp TRƯỚC khi bấm Export: kéo thanh / chọn preset trong màn Retouch là app giữ
engine 30 phút (kể cả khi rời màn Retouch); app đang tắt thì mở hộp Export là plugin tự
mở trạm retouch chạy ngầm và nạp mô hình (dòng trạng thái trong hộp báo "Sẵn sàng").
Ảnh nào lỗi / quá giờ / không phải JPEG-TIFF-PNG vẫn ra đủ (chưa retouch) — xem
plugin.log. Bấm ✕ ở thanh "AutoTone: retouch khi xuất" = các ảnh còn lại ra không
retouch, lượt Export vẫn chạy tiếp. Chỉ dùng cho Export (không cho Publish Services).

**Hàng đợi từng ảnh** (10/10, học từ NEXUS AI Retouch): plugin ghi mỗi ảnh vào
`jobs/xuatanh_hangdoi.tsv` NGAY khi Lightroom xuất xong ảnh đó (dòng cuối `#het`).
Retouch đọc tiếp hàng đợi mỗi 0,7 giây và làm ngay — không còn quét thư mục rồi chờ
file đứng yên qua hai lần quét; hết mẻ là làm mẻ kế liền. Plugin bản cũ không có
hàng đợi thì vẫn quét thư mục như trước.

Lightroom xuất **một lần cho cả lượt** (một phiên Export, không chia lô — 9/10), tiến
độ đếm từng ảnh. Ảnh nào xuất xong là màn Retouch hiện ngay trên dải ảnh; tấm đầu
tiên tự lên ảnh lớn kèm **xem trước theo preset** của lượt (chế độ song song: đợi xem
trước tấm đầu rồi mới chạy mẻ; xong tấm nào thì ảnh lớn đổi sang bản retouch thật).

Bấm **Bắt đầu xuất**: app chuyển sang màn Retouch, thanh đáy hiện
*"Lightroom xuất 120/760 · Retouch 85/760 · 12 phút"*. **Dừng** = xin Lightroom dừng
sau lô đang chạy và thôi retouch ảnh mới. Xong có câu tổng kết ở thanh đáy và Nhật ký.

**6 · An toàn máy** (9/10): bật thì trong lúc xuất, Lightroom và retouch chỉ chạy
trên **nhân E** của CPU; xuất xong trả lại như cũ. Mặc định BẬT trên Intel thế hệ
13/14 có nhân E. Lý do: lần Xuất đầu tiên máy i9-13900KS (BIOS 0904 03/2023,
microcode 0x113) **sập màn hình xanh** (0x101 CLOCK_WATCHDOG_TIMEOUT) ngay khi
Lightroom bắt đầu xuất cỡ gốc — dòng CPU này có lỗi điện áp trên nhân P mà Intel
đã vá bằng microcode 0x12B trở lên. Ghim nhân E chậm hơn nhưng tránh nhân P lỗi.
**Sửa tận gốc: cập nhật BIOS mainboard** (ASUS ROG STRIX Z790-F: bản mới nhất,
chọn cấu hình "Intel Default Settings").

Thư mục xuất chọn ở hộp thoại được nhớ, và Retouch mặc định mở thư mục đó (mở app
lần sau là thấy ảnh ngay, không phải chọn lại).

**Preset retouch** (nhóm "Mức áp dụng"): chọn preset = áp cho ảnh đang xem (chưa có
ảnh thì làm mức chung); **Lưu** = ghi bảng đang hiện thành preset (gồm cả mức riêng
theo nhóm mặt); bảng khác preset thì hộp chọn ghi "(đã sửa)".

## Nếu không thấy gì xảy ra

Cả hai đường đều đi qua vòng lặp nền của plugin (5 giây một nhịp). Quá 60 giây
mà app vẫn báo "chưa nhận yêu cầu" thì gần như chắc chắn là một trong hai:

1. Lightroom không mở.
2. Plugin chưa nạp lại bản mới → **Plug-in Manager → Reload**.

Xem `AutoTone.lrplugin/jobs/plugin.log` để biết chắc.
