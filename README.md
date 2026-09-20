# autotone — cân bằng tone tự động cho RAW Sony qua sidecar `.xmp`

| File | |
|---|---|
| `AUTOTONE.bat` | **bấm đúp để mở giao diện** |
| `autotone_gui.py` | giao diện (Tkinter) |
| `autotone.py` | nhân xử lý, dùng được như lệnh dòng lệnh |
| `AutoTone.lrplugin/` | plugin Lightroom — cài 1 lần, khỏi bấm Read Metadata |
| `models/` | model nhận diện mặt YuNet (232KB) |
| `make_testdata.py` | sinh ảnh giả lập để thử |


Đo độ sáng từ **JPEG preview nhúng sẵn trong file `.ARW`**, tính delta, rồi ghi vào đúng
mấy trường tone trong `.xmp` — giữ nguyên toàn bộ phần preset SAY Media.

Không cần cài `exiftool`, không cần `rawpy`. Chỉ dùng `numpy` + `Pillow` (máy bạn đã có sẵn).

---

## Quy trình

### Cách A — qua plugin *(khuyên dùng, không đụng tới `.xmp`)*

```
Lightroom: apply preset → Ctrl+A →
           Library > Plug-in Extras > "AutoTone: xuất thông số cho autotone"
        ↓
AUTOTONE.bat  →  nguồn "Lightroom catalog" → Phân tích → Ghi
        ↓
Lightroom tự cập nhật trong ~5 giây
```

Không cần `Ctrl+S`, không cần *Read Metadata from File*, không sinh file `.xmp` nào.

### Cách B — qua sidecar `.xmp`

```
Lightroom: apply preset → Ctrl+A → Ctrl+S      (ghi .xmp cho TOÀN BỘ ảnh)
        ↓
AUTOTONE.bat  →  nguồn "Sidecar .xmp" → Phân tích → Ghi vào .xmp
        ↓
Lightroom: chọn ảnh → Metadata > Read Metadata from File
```

> **`Ctrl+S` trên thư mục lớn rất lâu.** Nó phải ghi từng ấy file `.xmp` ra đĩa —
> 1884 ảnh thì thanh *Saving Metadata* chạy hàng chục phút và trông y như treo
> (thật ra vẫn đang chạy). Đây chính là lý do nên dùng **Cách A**.

> ⚠️ **`Read Metadata from File` GHI ĐÈ** mọi chỉnh sửa đang có trong catalog của
> những ảnh được chọn. Chạy trước khi retouch tay, và backup catalog trước lần đầu.
> Cách A không dính vấn đề này — plugin chỉ sửa đúng 5 trường tone.

---

## Giao diện — bấm đúp `AUTOTONE.bat`

Cách dùng thường ngày. Không cần gõ lệnh.

```
┌─ Thư mục ảnh ──────────────────────────────────────────────┐
│ [F:\Source RAWs\Cuoi Minh & Ha]              [Chọn thư mục] │
│ ☐ Gồm cả thư mục con                                        │
│ 428 ảnh RAW, đủ sidecar .xmp.                               │
├─ Cách cân tone ────────────────────────────────────────────┤
│ Chế độ: [Cân trong từng cảnh ▾]  Đo sáng: [Giữa khung ▾]    │
│ Cân bằng trắng: [Không đụng tới ▾]                          │
│ Tách cảnh khi cách nhau [5] phút   Chỉnh tối đa ±[1.00] EV  │
│ Mức độ can thiệp [1.00]                                     │
│ ☑ Tự kéo Highlights khi cháy sáng  ☑ Tự kéo Shadows         │
├────────────────────────────────────────────────────────────┤
│ [1 · Phân tích] [2 · Ghi vào .xmp] [Hoàn tác...] [Xuất CSV] │
│ ▓▓▓▓▓▓▓▓▓░░░░░░░░  Đang đo 214/428 ảnh...          [Dừng]  │
├────────────────────────────────────────────────────────────┤
│ File          Cảnh  Giờ chụp   ΔEV  Exposure  Highl. ...   │
│ DSC00841.ARW    0   14:02:11 +0.83    +0.83      +16       │
│ DSC00842.ARW    0   14:02:36 -0.91    -0.91      -29       │
└────────────────────────────────────────────────────────────┘
```

**Điểm tiện nhất:** phép đo ảnh chỉ phụ thuộc thư mục và **Đo sáng**. Mọi ô còn lại
(chế độ, tách cảnh, ±EV, mức độ, WB, highlights/shadows) chỉ tác động ở bước tính —
đổi là bảng cập nhật **ngay lập tức**, không phải quét lại ảnh. Cứ chỉnh tới lui đến
khi ưng cột ΔEV rồi mới bấm ghi. Riêng ô **Đo sáng** đổi thì phải bấm Phân tích lại,
UI sẽ tự nhắc.

Trong bảng:

- **Bấm đúp một dòng** → xem chi tiết trước/sau của ảnh đó (Exposure, Highlights,
  Shadows, Temperature, Tint, độ sáng đo được, mức cháy trước/sau).
- **Bấm tiêu đề cột** → sắp xếp; bấm lại để đảo chiều. Sắp theo ΔEV để soi nhanh
  mấy ảnh bị chỉnh mạnh nhất.
- Màu nền: **cam** = chỉnh ≥ 0.5 EV · **đỏ nhạt** = cháy sáng ≥ 3% · **xám** = không đổi gì.

Nút **Dừng** cắt giữa chừng và vẫn giữ phần đã đo — ghi được cho riêng phần đó.
Nút **Hoàn tác** liệt kê mọi bản backup theo thời gian để chọn khôi phục.

---

## Dòng lệnh (khi cần chạy hàng loạt / tự động)

```bash
python autotone.py "F:\Source RAWs\Buoi chup 2026-08-25"
```

Mặc định là **chạy thử** — chỉ in bảng kết quả, không đụng file. Ưng thì thêm `--apply`:

```bash
python autotone.py "F:\Source RAWs\Buoi chup 2026-08-25" --apply --report bao-cao.csv
```

Hoàn tác (mỗi lần `--apply` đều tự backup vào `_xmp_backup\<thời gian>\`):

```bash
python autotone.py "F:\Source RAWs\Buoi chup 2026-08-25" --undo "F:\Source RAWs\Buoi chup 2026-08-25\_xmp_backup\20260825_143000"
```

---

## Đẩy thẳng vào Lightroom (plugin)

Mặc định autotone ghi vào `.xmp`, rồi bạn phải vào Lightroom bấm *Read Metadata from
File*. Thao tác đó vừa thủ công vừa nguy hiểm — nó **ghi đè toàn bộ** chỉnh sửa đang có
trong catalog của mấy ảnh đó.

Plugin `AutoTone.lrplugin` bỏ được cả hai vấn đề. Nó đọc thông số autotone vừa tính rồi
gọi thẳng API của Lightroom, **chỉ sửa đúng 5 trường tone** và giữ nguyên mọi thứ khác
(crop, mask, tone curve, retouch đã làm).

Plugin làm **hai chiều**:

| Chiều | Menu | Thay cho |
|---|---|---|
| Catalog → autotone | *AutoTone: xuất thông số cho autotone* | `Ctrl+S` (Save Metadata to File) |
| autotone → Catalog | tự động, hoặc *AutoTone: áp thông số mới nhất* | *Read Metadata from File* |

**Cài một lần:**

1. Mở Lightroom Classic
2. `File → Plug-in Manager...`
3. Bấm **Add** (góc dưới bên trái)
4. Trỏ tới thư mục `AutoTone.lrplugin` nằm cạnh file này
5. **Done**

Xong. Từ đó mỗi lần bấm *2 · Ghi vào .xmp*, Lightroom tự cập nhật trong ~5 giây.

**Điều khiển plugin** — `Library → Plug-in Extras`:

- *AutoTone: xuất thông số cho autotone* — chiều catalog → autotone
- *AutoTone: áp thông số mới nhất* — áp ngay, không chờ
- *AutoTone: bật/tắt tự động áp* — tắt chế độ tự động nếu muốn tự bấm
- *AutoTone: chẩn đoán* — thử đọc 1 ảnh bằng mọi cách và báo cáo chính xác chỗ hỏng.
  Chạy cái này đầu tiên khi có trục trặc, rồi xem `jobs/plugin.log`.

### Hai cái bẫy khi sửa plugin

**1. Không được dùng `pcall` quanh lời gọi SDK.** Lua của Lightroom là 5.1, `pcall` là
hàm C và không `yield` xuyên qua được. Gần như mọi hàm SDK đụng tới catalog
(`getDevelopSettings`, `applyDevelopSettings`, `getRawMetadata`...) đều yield bên trong,
nên bọc `pcall` sẽ hỏng ngay với thông báo:

```
Yielding is not allowed within a C or metamethod call
```

Cần bắt lỗi thì dùng `Core.try()` trong `AutoToneCore.lua` — nó bọc
`LrFunctionContext.pcallWithContext`, đúng bản `pcall` dành cho code có yield.

**2. Đọc theo lô, đừng bọc cả nghìn ảnh trong một khối read-access.** Plugin tự dò một
ảnh xem bản Lightroom của bạn có bắt buộc `catalog:withReadAccessDo()` không, rồi đọc
theo lô 200 ảnh — mỗi lô một khối ngắn, giữa các lô có `yield` để giao diện không đứng.

Tắt phía autotone thì bỏ tick *Đẩy thẳng vào Lightroom* trong UI, hoặc `--no-lr-push`
ở dòng lệnh.

**Cách hoạt động:** hai bên trao đổi qua `AutoTone.lrplugin/jobs/`.
Plugin ghi `export_*.tsv` (thông số hiện tại trong catalog), autotone ghi `apply_*.tsv`
(thông số mới). Plugin dò thư mục 5 giây/lần, áp xong đổi đuôi thành `.done`.
Nhật ký ở `AutoTone.lrplugin/jobs/plugin.log` — xem đó đầu tiên khi Lightroom không cập nhật.

**Mốc preset ở chế độ catalog:** không có sidecar để cắm marker `atn:`, nên autotone lưu
giá trị preset gốc vào `_autotone_baseline.tsv` ngay trong thư mục ảnh. Nhờ đó chạy lại
lần 2, 3 vẫn tính từ preset chứ không cộng dồn. Đổi preset trong Lightroom rồi muốn
autotone lấy mốc mới thì xoá file đó đi.

---

## Worker — tự chạy sau mỗi buổi chụp

Nút **Tự động theo dõi...** trong UI, hoặc `--watch` ở dòng lệnh.

Worker canh một thư mục gốc và tự xử lý khi buổi chụp đã import xong. Nó **không** xử lý
ngay lúc ảnh vừa xuất hiện — cân theo cảnh cần thấy đủ ảnh của cảnh đó, mà Lightroom thì
ghi `.xmp` dần dần. Nên worker chỉ chạy khi thư mục đã "yên" suốt một khoảng
(mặc định 120 giây) không có file nào thêm hay đổi.

```bash
python autotone.py "F:\Source RAWs" --watch --subfolders --apply --wb asshot
```

- `--subfolders` — mỗi thư mục con là một buổi chụp riêng, xử lý độc lập
- `--interval 20` — bao lâu kiểm tra một lần
- `--settle 120` — thư mục phải yên bao nhiêu giây mới xử lý
- bỏ `--apply` để chạy thử, chỉ ghi nhật ký

Thêm ảnh vào một buổi đã xử lý thì worker tính lại **cả thư mục** để cảnh được cân đúng
trên bộ ảnh đầy đủ — nhờ marker `atn:` nên không cộng dồn. Trạng thái đã-xử-lý-hay-chưa
đọc thẳng từ marker trong `.xmp`, nên tắt máy bật lại vẫn đúng, không cần file trạng thái.

---

## Bốn chế độ cân sáng

| `--mode`   | Mốc quy chiếu | Dùng khi |
|------------|---------------|----------|
| `absolute` *(mặc định)* | `face_target_ev` cố định | Đưa **mọi khuôn mặt** về cùng một mức sáng chuẩn. Vì mốc là độ sáng da mặt nên nó vừa đúng sáng vừa tự động đồng đều cả buổi. |
| `scene`    | Trung vị của **từng cảnh** | Chỉ san phẳng dao động trong một cảnh, không đụng tới mức sáng chung. |
| `batch`    | Trung vị của **cả buổi** | Muốn cả buổi về một mức sáng chung. |
| `hybrid`   | Trộn scene + absolute theo `--blend` | Vừa san phẳng trong cảnh, vừa kéo nhẹ cả cảnh về chuẩn. |

Trước đây mặc định là `scene`, nhưng khi đã đo theo khuôn mặt thì `absolute` tốt hơn hẳn:
mọi ảnh đều nhắm về cùng một mức sáng da mặt, nên vừa đúng sáng vừa đồng đều — `scene`
chỉ làm được vế thứ hai. `--gap` vẫn dùng để gom cảnh cho phần cân bằng trắng.

---

## Tham số hay dùng

```
--mode scene|batch|absolute|hybrid   cách chọn mốc sáng
--gap 5                              phút giữa 2 shot để tách cảnh mới
--max-ev 1.0                         trần |ΔEV|; hạ xuống 0.5 nếu muốn dè dặt
--gain 1.0                           0.7 = chỉ chỉnh 70% mức tính được
--meter face|focus|subject|center|average|median   face = mặt + điểm bắt nét
--no-highlights / --no-shadows       không đụng Highlights2012 / Shadows2012
--wb skin|asshot|off|grey|scene      xem phần dưới
--recursive                          quét cả thư mục con
--jobs 8                             số tiến trình
--report bao-cao.csv                 xuất chi tiết từng ảnh
--config cfg.json                    chỉnh mấy tham số không có cờ CLI
--limit 20                           chỉ xử lý 20 ảnh đầu, để thử
--calibrate "anh.ARW=+0.35"          tính mốc sáng hợp gu bạn
--watch --subfolders                 chế độ worker (xem phần trên)
--no-lr-push                         không đẩy sang Lightroom, chỉ ghi .xmp
```

Thứ tự ưu tiên: **cờ dòng lệnh > `--config` > mặc định**.

---

## Hiệu chỉnh mốc sáng theo gu của bạn

Mốc mặc định `face_target_ev = -1.19` được suy ra từ một ví dụ thật: ảnh có da mặt đo
được `-1.54 EV` và người dùng muốn `Exposure +0.35`. Gu mỗi người mỗi khác — muốn đổi
thì chỉ ra một ảnh bạn biết rõ nó nên bao nhiêu:

```bash
python autotone.py "F:\Buoi chup" --calibrate "SAY07021.ARW=+0.35"
```

```
SAY07021.ARW: đo được -1.54 EV trên khuôn mặt (1 mặt)
Bạn muốn Exposure +0.35  ->  mốc phù hợp: -1.186
    {"face_target_ev": -1.186}
```

Bỏ dòng đó vào file `--config` là xong. Nên hiệu chỉnh bằng 2-3 ảnh khác nhau rồi lấy
trung bình, đừng tin một ảnh duy nhất.

---

## Đo sáng ưu tiên khuôn mặt

Mặc định `--meter face`. Dùng **YuNet** (OpenCV) nhận diện mặt, rồi đo độ sáng **ngay
trong ô mặt** — lấy 55% giữa khung mặt (bỏ tóc, nền, cổ áo), bỏ 30% tối nhất và 10% sáng
nhất trong đó (bỏ bóng đổ và điểm loá).

**Điểm bắt nét cũng là một tiêu chí.** autotone dựng bản đồ độ nét cục bộ (năng lượng
cạnh chia cho độ sáng), dùng vào hai việc:

- Mặt nào nằm đúng chỗ bắt nét thì tính nặng ký hơn — ảnh có cả người nói lẫn khán giả
  phía sau thì người nói quyết định độ sáng, không phải đám đông.
- Không tìm thấy mặt nào thì đo ngay tại vùng nét nhất (`--meter focus`), rồi mới lùi
  tiếp về `subject`.

Bước chia cho độ sáng là mấu chốt: không có nó thì màn LED đầy chữ tương phản cao luôn
thắng và máy tưởng cái màn hình mới là chỗ bắt nét. Đã thử trên ảnh sự kiện thật — vùng
nét rơi đúng vào người nói, kể cả khi slide phía sau đầy chữ.

Lý do: chụp sự kiện thường có **màn LED, cửa sổ, đèn sân khấu** chiếm mảng lớn và rất
sáng. Đo cả khung thì mấy mảng đó kéo con số lên, script tưởng ảnh thừa sáng và **dìm mặt
người xuống** — ngược hẳn ý muốn.

`--meter subject` là phương án không cần model: bỏ 15% pixel sáng nhất rồi mới đo
center-weighted. Chỉnh ngưỡng bằng `meter_highlight_cut` trong `--config`
(0.85 = bỏ 15% sáng nhất; 0.95 = chỉ bỏ 5%).

**Model** nằm ở `models/face_detection_yunet_2023mar.onnx` (232KB, tải từ kho chính thức
`opencv/opencv_zoo`). Thiếu model hoặc thiếu `opencv-python` thì autotone vẫn chạy bình
thường, chỉ tự lùi về `subject` và ghi chú trong báo cáo.

**Xoay ảnh theo EXIF là bắt buộc.** Preview nhúng trong RAW lưu nguyên chiều cảm biến,
ảnh dọc sẽ nằm ngang. YuNet chỉ nhận mặt thẳng đứng, nên nếu bỏ qua bước xoay thì ảnh dọc
gần như không tìm ra mặt nào — và còn bắt nhầm cầu thang, đèn trần thành mặt người.
autotone đọc tag Orientation rồi xoay trước khi nhận diện.

---

## Về white balance

Preset SAY Media của bạn dùng `WhiteBalance="Custom"` với `Temperature=5300`, `Tint=+9`
cố định cho mọi ảnh. Mặc định script **không đụng vào WB** (`--wb off`) — đó là lựa chọn
đúng cho phần lớn trường hợp.

- **`--wb skin`** *(mặc định — "da trắng hồng")* — **lấy mẫu màu da thật** trong khung
  mặt YuNet tìm được, rồi kéo về phía màu da đích. Cách lấy mẫu: thu khung mặt còn 55%
  (tránh tóc, nền, cổ áo), chỉ giữ khoảng sáng giữa (bỏ bóng đổ và điểm loá), lấy trung
  vị cả cảnh cho ổn định.

  Chỉnh trong `--config`:
  `skin_ref_rgb` — màu da đích, mặc định `[244, 212, 202]` (sáng, ngả hồng);
  `skin_gain` — kéo bao nhiêu phần về phía đích, mặc định 0.6 (1.0 = kéo hết);
  `wb_temp_max` — trần lệch nhiệt độ, mặc định ±400K.

  Đo trên ảnh thật: phòng đèn vàng cho da `R168 G130 B115` → kéo mát lại 0.57 stop;
  ảnh sáng chuẩn cho da `R249 G218 B202`, gần như trùng đích → gần như không đổi.

  Cảnh nào không tìm ra mặt thì lùi về độ ngả hồng cố định
  (`wb_skin_temp_bias` +120K, `wb_skin_tint_bias` +4) và ghi chú trong báo cáo.

Các lựa chọn khác:

- **`--wb asshot`** — kéo nhiệt độ preset về phía **nhiệt độ máy Sony
  thật sự đo được** cho cảnh đó, đọc từ `crs:AsShotTemperature` trong sidecar. Ví dụ tiệc
  đèn vàng, máy đo 3200K, preset để 5300K → script kéo xuống một phần (`wb_asshot_pull`,
  mặc định 0.35, chặn ở ±400K). Giữ được tính cách của preset mà vẫn thích ứng địa điểm.
- **`--wb grey`** — grey-world trên preview. Chỉ đúng khi cảnh có phân bố màu trung tính;
  ảnh cưới nhiều da người/váy trắng/đèn màu thì dễ sai. Dùng có cân nhắc.
- **`--wb scene`** — như `grey` nhưng chỉ san phẳng chênh lệch **trong cùng một cảnh**,
  không đổi tông chung của cảnh.

---

## Chạy lại nhiều lần

Script ghi thêm marker riêng vào sidecar:

```xml
xmlns:atn="http://saymedia.vn/ns/autotone/1.0/"
atn:BaseExposure="0.00"  atn:BaseHighlights="+16"  ...
```

Nhờ đó **chạy lại lần 2, 3 luôn tính từ giá trị preset gốc, không cộng dồn**. Đổi tham số
rồi chạy lại thì kết quả được tính lại từ đầu; tắt một tính năng (ví dụ `--no-highlights`)
thì trường đó tự trả về giá trị preset. Marker là namespace riêng, Lightroom bỏ qua.

Nếu Lightroom ghi đè sidecar (bạn sửa tay rồi `Ctrl+S`), marker sẽ mất — khi đó giá trị
hiện tại trở thành baseline mới. Nên chạy autotone **trước** khi retouch tay.

---

## Giới hạn cần biết

Đây là phần quan trọng nhất, đọc kỹ trước khi tin số liệu:

1. **Preview JPEG không phải ảnh sau preset.** Preview nhúng trong `.ARW` được máy render
   theo Creative Style / DRO của máy, chưa qua preset Lightroom. Nên số đo phản ánh
   *tương quan sáng tối giữa các ảnh* rất tốt, nhưng **mức sáng tuyệt đối** thì chỉ gần đúng.
   → Vì vậy `--mode scene` (so tương đối) đáng tin hơn `--mode absolute`.

2. **Vùng đã cháy trong preview không đo lại được.** Pixel bị cắt ở 255 thì thông tin đã mất;
   RAW còn giữ thêm khoảng 1 stop mà preview không thấy. Script xử lý bằng cách theo dõi
   riêng tỉ lệ pixel bão hoà và chiết khấu (`hl_discount`, `hl_recover_ev`), nhưng con số
   `cháy%` vẫn là **ước lượng**, không phải đo chính xác trên RAW.

3. **Nhận diện mặt không phải lúc nào cũng ra.** Mặt quá nhỏ, quay nghiêng, che khuất
   hoặc ngược sáng nặng thì YuNet bỏ sót. Cột **Mặt** trong bảng cho biết mỗi ảnh tìm
   được mấy mặt — bằng 0 nghĩa là ảnh đó đã lùi về đo theo chủ thể. Hạ `face_score`
   trong `--config` (mặc định 0.5) sẽ bắt được nhiều mặt hơn nhưng cũng nhiều nhầm hơn.

   Trước khi dùng YuNet tôi có thử nhận diện vùng da bằng ngưỡng màu YCbCr (không cần
   thư viện ngoài) và **kết quả không dùng được** trên ảnh sự kiện: bắt nhầm rèm gỗ, sàn
   sân khấu, đèn màu, trang phục hồng, đồng thời bỏ sót phần lớn khuôn mặt. Đừng quay
   lại hướng đó.

4. **`Read Metadata from File` ghi đè catalog.** Nhắc lại vì đây là rủi ro mất việc thật sự.

5. Nếu preset dùng `WhiteBalance="As Shot"` (không có `crs:Temperature`), phần WB sẽ tự bỏ
   qua và ghi chú `bo-qua-WB-preset-dung-As-Shot`.

---

## Trường được ghi

Chỉ 5 trường, mọi thứ khác trong preset giữ nguyên byte-for-byte (kể cả line ending):

`crs:Exposure2012` · `crs:Highlights2012` · `crs:Shadows2012` · `crs:Temperature` · `crs:Tint`

(cộng `xmp:MetadataDate` và marker `atn:*`)

---

## Tinh chỉnh sâu bằng `--config`

Những tham số không có cờ CLI, đặt trong file JSON:

```json
{
  "hl_discount":    0.60,
  "hl_recover_ev":  1.5,
  "hl_trigger_pct": 0.30,
  "hl_gain":        14.0,
  "hl_max":         45,
  "hl_hard_pct":    3.0,
  "sh_discount":    0.50,
  "sh_trigger_pct": 2.0,
  "sh_gain":        3.0,
  "sh_max":         40,
  "deadband_ev":    0.05,
  "wb_asshot_pull": 0.35,
  "wb_temp_max":    400.0
}
```

- `hl_gain` — mỗi 1% pixel cháy thì kéo Highlights xuống bao nhiêu điểm.
- `hl_hard_pct` — cháy quá mức này thì script tự ghìm bớt exposure dương
  (báo cáo ghi `ghim-exposure-vi-chay-sang`).
- `deadband_ev` — lệch nhỏ hơn mức này thì để yên, tránh sửa vặt vô nghĩa.

Khoá lạ trong config sẽ bị cảnh báo chứ không im lặng bỏ qua.

---

## Đọc bảng kết quả

```
file                       cảnh     ΔEV     Exp    HL    SH   cháy%   tối%  ghi chú
DSC0104.ARW                   0   -0.91   -0.91   -29    16    6.49   0.00
```

- `cảnh` — nhóm theo thời gian chụp
- `ΔEV` — mức chỉnh so với preset
- `Exp` / `HL` / `SH` — giá trị **cuối cùng** ghi vào `.xmp`
- `cháy%` / `tối%` — ước lượng sau khi đã chỉnh

File CSV `--report` có đầy đủ hơn: giá trị cũ/mới từng trường, `metered_ev`, `target_ev`,
`clip_before_pct`, ISO, model, thời gian chụp.
