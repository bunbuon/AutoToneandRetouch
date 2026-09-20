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

## Nếu không thấy gì xảy ra

Cả hai đường đều đi qua vòng lặp nền của plugin (5 giây một nhịp). Quá 60 giây
mà app vẫn báo "chưa nhận yêu cầu" thì gần như chắc chắn là một trong hai:

1. Lightroom không mở.
2. Plugin chưa nạp lại bản mới → **Plug-in Manager → Reload**.

Xem `AutoTone.lrplugin/jobs/plugin.log` để biết chắc.
