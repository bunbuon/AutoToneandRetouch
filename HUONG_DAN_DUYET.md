# Duyệt nhanh — soát màu mà không cần Smart Preview

## Vấn đề đang chữa

Sau khi bấm **Ghi và đẩy sang Lightroom** (khâu 3), thông số mới đã vào catalog
đủ 100% — plugin đọc ngược lại `getDevelopSettings()` của TỪNG ảnh và đối chiếu,
dòng `kiem chung DU` trong `plugin.log` là bằng chứng.

Nhưng còn một việc bắt buộc trước khi Export: **soát lại một lượt** xem tấm nào
chưa ổn rồi sửa. Soát trong Lightroom thì phải chờ nó dựng preview:

- Bật **Smart Preview** lúc Import → Import chậm hẳn, phải ngồi chờ.
- Không bật → cuộn tới đâu Lightroom dựng tới đó, mỗi tấm một nhịp chờ.

## Vì sao không làm "extension" để can thiệp sâu hơn

Lightroom Classic **chỉ có một cơ chế mở rộng duy nhất là Lua SDK** — chính là
plugin `AutoTone.lrplugin` đang chạy. Adobe đã nói rõ trên blog developer là
Lightroom và Lightroom Classic **không hỗ trợ CEP và không có kế hoạch hỗ trợ
UXP**. Nên không có tầng nào sâu hơn để chuyển sang.

Và SDK Lua **không có API nào cho preview**: không dựng được, không đọc được,
không xoá cache được. Ngày 6/9 đã thử `requestJpegThumbnail` — callback không
bao giờ nổ: 0/39 ảnh, 126 lô hết giờ, 950 ảnh bị bỏ. Đã gỡ hẳn khỏi đường ghi
màu và có bài kiểm canh không cho ai đặt lại (`kiem_dung_preview.lua`).

## Cách làm thay thế

SDK **có** `LrExportSession` — bộ render thật của Lightroom, có tài liệu, gọi
được từ plugin mà không cần mở hộp thoại, và **dùng GPU** khi bật *Use Graphics
Processor for Export*.

Nên thay vì xin Lightroom "dựng preview" (không có cửa), plugin bảo nó **xuất
ảnh JPEG nhỏ** (mặc định cạnh 1600 px) ra `<thư mục buổi chụp>/_duyet`. App mở
mấy ảnh JPEG đó lên thành một lưới để soát — mở tức thì, không dính preview
cache của Lightroom chút nào.

**Import lúc này để `Minimal` preview và KHÔNG bật Smart Preview.**

## Các bước

1. Trong Lightroom: **File → Plug-in Manager → Reload** plugin AutoTone
   (bản mới có thêm `DuyetCore.lua` và `DuyetNhanh.lua`).
2. Chạy khâu 1 → 2 → 3 như thường, tới khi khâu 3 báo `kiem chung DU`.
3. Vẫn ở khâu 3, kéo xuống khối **Duyệt nhanh trước khi Export**:
   - **Lần đầu bấm “Thử 50 ảnh”.** Nó báo số giây thật và số giây một ảnh.
     Có số đo rồi mới quyết cho chạy cả buổi.
   - Sau đó bấm **Dựng ảnh duyệt** cho cả buổi.
   - Lỡ bấm nhầm cả buổi thì bấm **Dừng**. Plugin dừng sau khi xong lô đang
     chạy (nhiều nhất 25 ảnh nữa) — không cắt ngang giữa một lô vì như vậy để
     lại file dở trên đĩa. Số ảnh đã dựng vẫn soát được bình thường.
4. Plugin dựng theo lô 25 ảnh và ghi bảng sau **mỗi lô**, nên bấm **Mở lưới
   soát** được ngay khi lô đầu xong — không phải chờ hết.
5. Trong lưới soát:
   - Bấm vào ảnh = **đánh dấu cần sửa** (viền đỏ), bấm lần nữa = bỏ.
   - `Enter` xem to · `← →` đi tiếp · `phím cách` đánh dấu · `Esc` đóng.
   - Lựa chọn được nhớ vào `_duyet/da_soat.tsv`, đóng giữa chừng mở lại vẫn còn.
6. Soát xong bấm **Gom vào Lightroom để sửa**. Plugin làm ba việc cho đúng
   mấy tấm đó:
   - gắn **nhãn đỏ**
   - gắn **3 sao** (không phải 1 — 1 sao là ảnh loại, xem `SAO_CAN_SUA`)
   - gom vào **bộ sưu tập** `AutoTone cần sửa · <tên buổi>`
7. Trong Lightroom, tìm lại chúng bằng một trong hai cách:
   - **Collections** ở cột trái → bấm đúng bộ sưu tập đó. Không phải mò thanh lọc.
   - hoặc **Library Filter Bar** (phím `\` để hiện) → tab **Attribute** → bấm
     ô màu đỏ. Nhớ tắt lọc sau khi xong.

   Sửa xong thì bỏ nhãn / đặt lại sao, hoặc xoá bộ sưu tập.

   *Lưu ý:* đặt sao là **ghi đè** sao cũ. Ảnh đang 5 sao mà bị đánh dấu cần sửa
   sẽ tụt về 3. Không muốn đụng tới sao thì đặt `SAO_CAN_SUA = None` trong
   `duyet.py`; không muốn đụng nhãn thì gọi `danh_dau(..., nhan="none")`.
8. Sửa hết mới **Export** (khâu 4). Sau Export mới tới Retouch.

Xoá ảnh duyệt bằng nút **Xoá ảnh duyệt** — chỉ xoá JPEG dựng để soát, không
đụng ảnh gốc và không đụng thông số trong Lightroom.

## Cũng chạy được từ menu Lightroom

`Library → Plug-in Extras → AutoTone: dựng ảnh duyệt nhanh` — hỏi chạy thử 50
ảnh hay chạy cả vùng chọn, có thanh tiến trình, và báo **số giây một ảnh** cùng
ước tính cho 1000 ảnh. Dùng khi muốn đo mà không cần mở app.

## Những chỗ đã cố ý làm cho chắc

- **Tách hẳn khỏi đường ghi màu.** `DuyetCore.lua` là file riêng;
  `AutoToneCore.lua` không `require` nó và `applyJob` không gọi gì của nó. Bài
  học 6/9: một tính năng phụ hỏng không được kéo sập việc ghi màu. Có hai phép
  kiểm tự động canh chuyện này (`kiem_duyet.lua`, `kiem_gui_duyet.py`).
- **Tên khoá export không đoán.** Lấy nguyên từ preset export thật của Lightroom
  trên máy (`For Email (Hard Drive).lrtemplate`). Đáng chú ý:
  `exportServiceProvider` của "ghi ra ổ cứng" là `com.adobe.ag.export.file` —
  không phải cái tên đoán ban đầu; sai khoá này thì export không ra file nào.
- **Không đưa ảnh duyệt ngược vào catalog** (`LR_reimportExportedPhoto = false`),
  không mở Explorer sau mỗi lô, không hỏi khi trùng tên.
- **Lưới soát vẽ trên Canvas và chỉ giữ ảnh của vùng đang nhìn.** Mỗi ảnh một
  widget thì nghìn tấm là ~300 MB bộ nhớ; cách này bộ nhớ theo màn hình chứ
  không theo số ảnh.

## Chạy các bài kiểm

```
lua5.1 kiem_duyet.lua AutoTone.lrplugin
lua5.1 kiem_dung_preview.lua AutoTone.lrplugin
python kiem_duyet_py.py
python kiem_gui_duyet.py
```

## Đã sửa sau lần chạy thật đầu tiên (7/9)

- **Lưới soát ra “không mở được” ở mọi ô.** `tk.PhotoImage` chỉ đọc GIF / PGM /
  PPM / PNG — nó **không đọc JPEG**, mà ảnh duyệt chính là JPEG. Nay đọc qua
  `PIL.ImageTk`. Máy dựng gói không mở được cửa sổ nào nên lỗi này không lộ ra
  lúc kiểm; đã thêm phép kiểm đọc mã nguồn (`kiem_gui_duyet.py`) để lần sau
  không tái diễn.
- **Không có đường dừng.** Thư mục 2000 ảnh mà lỡ bấm chạy cả buổi thì không
  thoát được. Nay có nút **Dừng**.
- Lượt chạy thử đổi từ 20 lên **50 ảnh**.
- **Ảnh cần sửa giờ được gom vào một bộ sưu tập Lightroom**, không chỉ gắn nhãn.
  Nhãn màu lọc được thật, nhưng thanh lọc hay bị ẩn hoặc đang ở "Filters Off"
  nên nhìn như không có. Bộ sưu tập nằm sẵn ở cột trái, bấm một cái là ra.
  Kèm theo **3 sao** để thấy ngay trong lưới.

## Số đo thật trên máy SAY Media (7/9/2026)

**50 ảnh trong 22 giây — 0,44 giây một ảnh.** Máy Windows, RAW Sony, cạnh 1600 px,
GPU bật cho Export.

Suy ra:

| Số ảnh | Thời gian render |
|---|---|
| 50 | 22 giây |
| 1 000 | ~7,5 phút |
| 2 000 | ~15 phút |

**Nhưng con số đáng nhìn không phải mấy số trên.** Plugin chia lô 25 ảnh và ghi
bảng sau mỗi lô, nên **lô đầu xong sau ~11 giây** là đã mở lưới soát được. Phần
render còn lại chạy nền trong lúc đang soát. Soát 2000 ảnh dù nhanh cỡ nào cũng
lâu hơn 15 phút, nên thực tế **không phải chờ render lần nào**.

So với đường cũ: Smart Preview cho 2000 ảnh phải chờ xong mới làm được gì, và
làm chậm cả khâu Import. Đường này chờ 11 giây rồi làm việc luôn.

Kết luận: **giữ hướng này.**

Lưu ý khi đọc số: nút **Thử 50 ảnh** chạy đúng 50 ảnh đầu. Nếu thanh trạng thái
hiện tổng lớn hơn 50 thì tức là đã bấm nhầm nút **Dựng ảnh duyệt** (chạy cả
buổi) — bấm **Dừng** rồi chạy lại bằng đúng nút chạy thử.
