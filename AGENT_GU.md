# Agent học gu — quy trình bắt buộc

Đây là hướng dẫn cho Claude (hoặc bất kỳ ai) khi được đưa một thư mục `gu/<buổi>/`.
Đọc hết trước khi kết luận bất cứ điều gì.

---

## Nguyên tắc số một: mẫu này có điểm mù

Mọi thứ trong `gu.csv` đều là ảnh người dùng **đã sửa**. Ảnh tool làm đúng thì
họ không động vào, nên không để lại dấu vết nào — mà đó mới là đa số.

Con số đã đo trên buổi 1308:

| Tính trên | Mốc `face_target_ev` ra |
|---|---|
| 185 ảnh đã sửa | **−1.42** |
| Cả 532 ảnh cùng nhóm | **−1.19** (đúng mốc đang dùng) |

Nghe theo −1.42 là phá 893 ảnh đã duyệt để chiều 185 ảnh bị sửa. Vì vậy:

> **Không đề xuất nào được tin bằng lý lẽ. Chỉ được tin bằng số đo trên chính
> những ảnh người dùng đã duyệt** — tức phải chạy `kiem_gu.py`.

---

## Nguyên tắc số hai: bốn loại sửa, bốn cách chữa

Cột `ly_do` trong `gu.csv` chia ảnh thành các nhóm **không được trộn với nhau**:

| `ly_do` | Nghĩa | Tham số liên quan |
|---|---|---|
| `do-nham-mat` | Tool đo vào phông, gáy, người phụ | `big_low_ratio`, `big_low_floor`, `big_low_gap`, `face_min_ratio`, `subject_keep` |
| `toi-qua` | Đo đúng mặt, muốn sáng hơn | `face_target_ev` |
| `sang-qua` | Đo đúng mặt, muốn tối hơn | `face_target_ev` |
| `nen-chay` | Ghìm chưa đủ, nền cháy | `hl_hard_pct`, `hl_trigger_pct`, `hl_heavy_clip_pct` |
| `chu-the-toi` | Ghìm quá tay, người bị tối | `hl_subject_floor_ev` |
| `lech-anh-ben` | Lệch so với ảnh cùng loạt | `scene_aim_slack_ev`, `scene_level`, gom cảnh |
| `khac` | Đọc cột `giai_thich` | tuỳ |

**Chỉ nhóm `toi-qua` / `sang-qua` mới là tín hiệu về gu.** Ba nhóm còn lại là
lỗi của tool — học từ chúng bằng cách chỉnh mốc sáng là chữa sai bệnh, và làm
hỏng những ảnh vốn đã đúng.

Ảnh có `ly_do` để trống thì **bỏ ra ngoài mọi phép tính**. Không đoán hộ.

---

## Nguyên tắc số ba: không dựng lại logic

Trong dự án này đã **bốn lần** logic chọn chủ thể bị dựng lại ở file phân tích
rồi rút ra kết luận sai, vì bản dựng lại thiếu mất một vòng lọc (điểm bắt nét
AF, lọc theo độ nét, lọc mặt tối hơn hẳn). Có ảnh kết luận "đang đo sáng trên
phông nền" trong khi bản thật đã bỏ khung phông từ lâu.

Mọi khung mặt trong `anh_*.png` và `o/*.jpg` đều do `measure()` **tự báo về**.
Đừng tự tính lại toạ độ, đừng suy ra chủ thể từ kích thước khung.

---

## Quy trình

### 1. Đọc bối cảnh

`boi_canh.json` có `tham_so_hien_tai` — giá trị đang chạy. Mọi đề xuất phải so
với những số này, không so với số trong tài liệu cũ.

### 2. Đọc `gu.csv` và các tấm ảnh

Xem `anh_01.png`, `anh_02.png`... Số trong ô khớp cột `so`.

- **Xanh lá** = mặt tool dùng làm chủ thể chính
- **Xanh dương** = khung cũng được tính vào phép đo
- **Xám gạch chéo** = khung nhận ra nhưng đã loại

Nhìn khung xanh lá là biết ngay `do-nham-mat` hay không, kể cả khi người dùng
chưa gắn lý do.

### 3. Nhóm lại và tìm quy luật

Trong từng nhóm `ly_do`, tìm cái chung — **không phải trung bình của tất cả**:

- Nhóm `toi-qua`: `sua_bao_nhieu` có tập trung quanh một giá trị không? Trung
  vị là bao nhiêu? Có phụ thuộc `clip_before` / `iso` / `faces_n` không?
- Nhóm `do-nham-mat`: `diem_chu_the` (điểm tin cậy khung xanh lá) thấp bao
  nhiêu? `khung_tong` bao nhiêu? Có phải luôn là ảnh nhiều khung không?
- Nhóm `lech-anh-ben`: `scene_size` lớn bất thường không? Cảnh bao nhiêu ảnh?

Dưới **8 ca** trong một nhóm thì **không đề xuất gì** cho nhóm đó. Nói thẳng
là chưa đủ dữ liệu, đừng nói cho có.

### 4. Viết đề xuất ra JSON

Một file, chỉ chứa khoá muốn đổi:

```json
{"face_target_ev": -1.24}
```

**Mỗi lần chỉ đổi MỘT nhóm nguyên nhân.** Đổi hai thứ cùng lúc mà cổng không
đạt thì không biết thứ nào có lỗi.

### 5. Chạy cổng — bước này KHÔNG được bỏ

```
python kiem_gu.py G:\1308 --de-xuat de_xuat.json --nhom <ly_do liên quan>
```

Hai cổng, đặt trước khi chạy, **không nới sau**:

- **Cổng A** — ảnh có đích đúng: kéo lại gần phải nhiều hơn đẩy ra xa
- **Cổng B** — ảnh đã duyệt: dưới 2% xê dịch quá 0.30 EV

**Luôn dùng `--nhom`.** Cổng A phải chấm trên đúng nhóm lý do mà đề xuất nhắm
tới, không phải trên tất cả. Đây là bài học trả giá thật ngày 2/9: đề xuất sửa
mốc cảnh (`scene_aim_free_min`) bị chấm trượt 0–10 trên 185 ảnh của buổi 1308,
nhưng phần lớn 185 ảnh đó người dùng sửa vì **tool đo nhầm mặt** — chuyện chẳng
liên quan gì tới mốc cảnh. Cổng vừa không đo được cái cần đo, vừa phạt oan một
đề xuất chỉ vì nó chạm nhẹ vào mấy tấm không liên quan.

Cổng in sẵn bảng chia theo từng lý do — đọc bảng đó trước khi kết luận. Nhóm
dưới 8 ca thì cổng trả về **"chưa kết luận được"**, không phải "đạt": vài ảnh
không nói lên điều gì, và một cổng "đạt" dựa trên 3 ảnh còn nguy hiểm hơn không
có cổng, vì nó cho phép đổi tham số mà vẫn thấy mình đang cẩn thận.

Không đạt thì **bỏ đề xuất và ghi lý do**. Tuyệt đối không chỉnh tham số cho
vừa cổng — làm thế là biến cổng thành đồ trang trí. Nếu thấy mình đang thử con
số thứ ba cho cùng một tham số, dừng lại: dữ liệu đang nói là không có mốc nào
tốt hơn.

### 6. Trình cho người dùng

Chỉ trình đề xuất **đã đạt cổng**, kèm đủ ba thứ:

- đổi gì, từ bao nhiêu sang bao nhiêu
- dựa trên bao nhiêu ảnh, thuộc nhóm lý do nào
- kết quả cổng: bao nhiêu ảnh đã duyệt bị xê dịch, sai trung bình giảm bao nhiêu

Rồi **dừng lại và chờ**. Người dùng bấm duyệt thì mới ghi:

```
python kiem_gu.py G:\1308 --de-xuat de_xuat.json --ghi-gu
```

Lệnh đó ghi vào `gu.json`; `autotone.py` nạp file này vào `DEFAULTS` lúc khởi
động nên mọi công cụ — dòng lệnh, giao diện, các script kiểm — đều dùng chung.

---

## Những điều KHÔNG được làm

- Không tự chạy `--ghi-gu` khi chưa có người duyệt.
- Không gộp ảnh `do-nham-mat` vào phép tính `face_target_ev`.
- Không dùng ảnh chưa gắn `ly_do`.
- Không đề xuất khi nhóm dưới 8 ca — nói là chưa đủ dữ liệu.
- Không nới cổng, không chạy lại với ngưỡng dễ hơn.
- Không chấm cổng A trên toàn bộ ảnh khi đề xuất chỉ nhắm một nhóm — dùng `--nhom`.
- Không kết luận "tool đo sai" từ việc nhìn ảnh mà không nhìn khung `measure()`
  báo về.


---

## Sổ ghi những đề xuất ĐÃ BỊ BÁC BỎ

Đọc trước khi đề xuất, để không thử lại thứ đã trượt.

| Đề xuất | Ngày | Cổng A | Cổng B | Vì sao trượt |
|---|---|---|---|---|
| `scene_aim_slack_ev = 0` — san phẳng không được đẩy ảnh ra xa đích | 2/9, buổi 1308 | kéo gần 3 / đẩy xa 11 | 2.42% (cổng 2%) | Chốt phát biểu "bám đích luôn hơn sự đồng đều". Nhưng san phẳng sinh ra chính vì đôi khi đồng đều đáng giá hơn. Đụng 149 ảnh, tất cả đều bị kéo lên, cá biệt 1.85 EV. Lỗi của **ý tưởng**, không phải tham số. |
| `scene_aim_free_min = 2` — mốc cảnh chỉ tính trên ảnh không bị ghìm | 2/9, buổi 1308 | kéo gần 0 / đẩy xa 10 | 1.56% ✓ | Chỉ đụng 10/185 ảnh nhưng cả 10 đều tệ đi. Loại ảnh bị ghìm ra khỏi mốc là vứt luôn thông tin "cảnh này sáng, coi chừng cháy" — mốc trôi lên, cảnh sáng càng sáng, đúng thứ người dùng đang sửa tay. |

| `hl_thu_hoi_nguong = 0.08` — kéo xuống 0.42 EV khi khung bão hoà ≥ 8% | 2/9, buổi 1308 | kéo gần **35** / đẩy xa **1**, sai t.b 0.486 → 0.287 | **32.65%** (cổng 2%) | Hướng ĐÚNG, ngưỡng SAI. Bắn trúng 36 ảnh đúng và 417 ảnh sai. Tôi đo "94% chính xác" chỉ trong tập ảnh đã sửa mà **không đối chiếu tỉ lệ nền**: 44% ảnh của cả buổi cũng trên ngưỡng đó. Một đặc trưng có mặt ở 44% mọi ảnh thì không phân biệt được gì. |

**Hướng "kéo xuống theo mức cháy" đã ĐÓNG — đo trên cả 1464 ảnh, 3/9.**

Sau khi có đặc trưng của cả ảnh đã duyệt, mọi điểm vận hành đều thế này:

| Điều kiện | Ảnh đã duyệt bị bắn | Trúng đích | Chính xác |
|---|---|---|---|
| bão hoà ≥ 0.20 | 301 (24%) | 34/63 | 10% |
| bão hoà ≥ 0.40 | 90 (7%) | 18/63 | 17% |
| bão hoà ≥ 0.60 | 13 (1%) | 8/63 | 38% |
| bão hoà ≥ 0.50 **và** chốt chống cháy chưa hề chạy | 19 (1.5%) | 12/63 | 39% |
| thêm "mặt đã gần đích" | *tệ hơn ở mọi mức* | | |

Điểm tốt nhất lọt cổng B bắt được **12/63** trong khi vẫn đụng 19 ảnh người
dùng thấy ổn. Không có ngưỡng nào dùng được.

**Vì sao — và đây mới là điều đáng ghi.** Trong buổi 1308 có **265 ảnh bão hoà
≥30%, người dùng duyệt thẳng 234 ảnh**. Vùng cháy lớn là chuyện *bình thường*
ở ảnh sự kiện: màn LED, phông trắng, cửa sổ. Đọc lại chính lời người dùng —
*"giảm sáng để giữ lại nội dung standee"*, *"để thấy được cả background phía
sau"* — họ đang phán xét **cái gì nằm trong vùng cháy**: có nội dung đáng giữ
(standee, chữ, logo) hay chỉ là mảng tường trắng. Histogram độ sáng không phân
biệt được hai thứ đó. Tiêu chí của người dùng là **ngữ nghĩa**, không phải
trắc quang — nằm ngoài tầm mọi con số tool đang đo.

Đừng thử ngưỡng thứ tư trên trục này. Muốn đi tiếp thì phải có thứ nhìn được
NỘI DUNG vùng cháy, không phải diện tích của nó.

**Phát hiện phụ, hướng ngược lại và là tin tốt:** chốt chống cháy hiện tại
CHẠY ĐÚNG. Trong nhóm bão hoà ≥30%, ảnh người dùng duyệt có cờ `ha-vi-chay-sang`
59%, còn ảnh họ phải sửa chỉ 12%. Tool sai đúng ở những tấm chốt không kích
hoạt — mà nó không kích hoạt vì chỉ chạy khi `delta > 0`, và bản chất nó chỉ
ngăn *thêm* cháy, không bao giờ *gỡ* phần đã cháy.

**Bài học từ ca thứ ba — luôn tính TỈ LỆ NỀN.** Trước khi tin bất kỳ ngưỡng
nào: bao nhiêu phần trăm ảnh ĐÃ DUYỆT cũng vượt ngưỡng đó? Không trả lời được
câu này thì "độ chính xác" đo trên tập ảnh đã sửa là con số vô nghĩa — tập đó
theo định nghĩa chỉ gồm ảnh tool làm sai. `kiem_gu.csv` giờ ghi kèm đặc trưng
của mọi ảnh (`vung_bao_hoa`, `clip_before`, `metered_ev`, `faces_n`...) đúng để
so hai phân bố.

**Nhận định còn treo:** cả hai lần đều nhắm vào bước san phẳng. Bằng chứng nghi
lỗi thật nằm ở **cách gom cảnh**: buổi 0306 có một cảnh gộp 105 ảnh với biên độ
2.44 EV, và SAY09787/SAY09788 (cùng khung hình, chụp liền nhau) rơi vào hai cảnh
khác nhau. San phẳng chỉ đang làm đúng việc của nó trên một cách gom cảnh sai.
Chưa điều tra — cần dữ liệu có lý do trước.
