# Đóng gói AutoTone và gửi cho máy khác

Tài liệu này nói ba việc: **build**, **kiểm thử gói**, và **khoá hạn dùng thử**.

---

## 0. Trạng thái hiện tại — cái gì đã chạy thật, cái gì chưa

Đây là phần quan trọng nhất, nên để lên đầu.

| Việc | Đã chạy thật chưa |
|---|---|
| Toàn bộ script build (`dong_goi.py`) | **Rồi** — đã build ra gói thật và gói đó chạy được |
| Bài kiểm gói (`kiem_goi.py`) trên gói thật | **Rồi** — 17/17 mục đạt |
| Đường dẫn tài nguyên sau khi đóng gói (`sys._MEIPASS`) | **Rồi** |
| Khoá hạn dùng, mã gia hạn, mã máy | **Rồi** — cả từ mã nguồn lẫn trong gói đã build |
| Giao diện mở lên từ gói đã build | **Rồi** — đã chụp màn hình |
| Bản **Windows (.exe)** | **CHƯA** — xem lý do ngay dưới |
| Bản **macOS (.app)** | **CHƯA CHẠY LẦN NÀO** — xem mục 4 |
| Gói có kèm **retouch** (torch ~4 GB) | **CHƯA** — bản đã build là bản không retouch |

**Vì sao chưa có bản Windows và macOS.** PyInstaller không build chéo được. Nó
đóng gói bằng cách nhét chính trình thông dịch Python và các thư viện **nhị phân
của máy đang chạy** vào gói. Máy tôi chạy là Linux, nên nó chỉ ra được bản
Linux. Không có đường vòng — kể cả Docker hay Wine cũng không.

Nên bản Linux ở trên **không phải sản phẩm giao cho ai**; nó là bản để chứng minh
script build đúng. Phần còn lại — chạy đúng ba câu lệnh dưới đây trên máy
Windows của mình — là việc anh làm, và `kiem_goi.py` sẽ tự nói gói có đạt không.

---

## 1. Build bản Windows

Mở **PowerShell**, không phải Command Prompt.

```powershell
cd "F:\Claude AI\AutoToneImages"

# lần đầu thôi
python -m pip install pyinstaller

# build — 10–40 phút tuỳ có kèm retouch hay không
python dong_goi.py
```

Xong sẽ có:

```
F:\Claude AI\AutoToneImages\dist\AutoTone\        <- thư mục gói
F:\Claude AI\AutoToneImages\dist\AutoTone-win.zip <- bản nén để gửi đi
```

**Vài cờ hay dùng:**

```powershell
python dong_goi.py --thu              # chỉ in lệnh sẽ chạy, không build
python dong_goi.py --khong-retouch    # gói nhẹ (~400 MB thay vì ~5 GB)
python dong_goi.py --tool-retouch "F:\ToolCloneEvoto"   # chỉ rõ chỗ ToolCloneEvoto
python dong_goi.py --khong-nen        # không tạo file zip
```

Nếu nó báo *"Không tìm thấy ToolCloneEvoto"*: chỉ rõ bằng `--tool-retouch`, hoặc
chấp nhận gói không có retouch bằng `--khong-retouch`. Nó **không** tự lặng lẽ
bỏ phần retouch — vì gửi cho khách một gói thiếu tính năng mà không ai biết là
kiểu hỏng khó phát hiện nhất.

### Vì sao là một thư mục chứ không phải một file .exe

`--onefile` gói tất cả vào một `.exe`, nhưng mỗi lần mở lại **giải nén** ra thư
mục tạm. Với torch + onnxruntime + insightface (~4 GB) thì mỗi lần mở app mất
hàng phút và ngốn thêm 4 GB đĩa tạm. `--onedir` mở tức thì. Đổi lại là một thư
mục — nén zip lại vẫn gửi được như thường.

---

## 2. Kiểm thử gói

**Luôn chạy bước này trước khi gửi gói đi.**

```powershell
cd "F:\Claude AI\AutoToneImages"
python kiem_goi.py
```

Nó kiểm ba lớp, mỗi lớp trả lời một câu khác nhau:

1. **Nhìn từ ngoài** — gói có đủ file không, có lọt file cấm (`tao_ma.py`) không.
2. **Chạy bên trong** — gọi chính `AutoTone.exe` với lệnh tự kiểm, để app tự
   chạy thật đường đo ảnh → tách cảnh → tính giá trị, tự kiểm đường dẫn mô hình,
   khoá hạn dùng, và bộ nhận mặt, **từ bên trong gói**. Nhìn từ ngoài không thấy
   được mấy thứ đó: một mô hình "có trong gói" vẫn có thể là mô hình app không
   mở được, và một module chỉ được import bên trong hàm thì PyInstaller không
   đóng vào gói, chạy tới đó mới nổ.
3. **So trước/sau** — app có âm thầm ghi vào thư mục gói không. Trên Windows,
   ghi vào `Program Files` bị chuyển hướng sang VirtualStore mà **không báo lỗi**
   — app tưởng đã ghi xong, file thật nằm chỗ khác. Đó là loại mất dữ liệu khó
   truy nhất, và chỉ so trước/sau mới thấy.

Kết quả cuối cùng là `GÓI ĐẠT` hoặc `n VẤN ĐỀ`.

### Kiểm trên máy sạch (nên làm)

Máy build luôn có sẵn thư viện Python ở ngoài, nên một gói **thiếu file** vẫn có
thể chạy được ở đó mà chết trên máy khách. Chép thư mục gói sang một máy chưa
từng cài Python rồi mở PowerShell trong thư mục gói:

```powershell
$env:AUTOTONE_TU_KIEM = "$HOME\bao_cao_autotone.txt"
.\AutoTone.exe
notepad "$HOME\bao_cao_autotone.txt"
```

App sẽ chạy bài tự kiểm rồi thoát ngay (không mở cửa sổ). Mở file báo cáo ra
xem. Dòng cuối phải là `TAT CA DAT`.

### Các bài kiểm khác (chạy trên mã nguồn, trước khi build)

```powershell
python kiem_khoa.py     # khoá hạn dùng, mã gia hạn, mã máy
python kiem_do_mat.py   # measure() chạy được với cả 6 cách đo
python tu_kiem.py       # đúng bài mà gói sẽ tự chạy, nhưng trên mã nguồn
```

---

## 3. Khoá hạn dùng thử

### Mốc

Hết hạn lúc **01:00 ngày 07/09/2026, giờ Việt Nam** — đúng 72 giờ kể từ 01:00
ngày 04/09/2026. Mốc này ghi kèm múi giờ (`+07:00`) trong `khoa.py`, nên máy đặt
múi giờ khác vẫn hiểu ra đúng một thời điểm.

Đổi mốc: sửa `HAN_ISO` ở đầu `khoa.py`, rồi build lại.
Tắt hẳn khoá khi phát triển: `BAT_KHOA = False`.

### Hết hạn thì sao

Một tấm phủ kín cửa sổ, và **10 nút chức năng** đều bị chặn: Chạy hết, Phân
tích, Ghi vào ảnh, Đọc từ Lightroom, Học, Gu, Hoàn tác, Retouch, Theo dõi,
Xuất CSV. Chặn ở đầu mỗi hàm chứ không phải chỉ làm mờ nút — làm mờ thì phím tắt
và cửa sổ đang mở sẵn vẫn lọt qua.

App tự kiểm lại mỗi 60 giây, nên đang mở mà tới giờ là khoá luôn, không cần
khởi động lại.

Góc dưới cột trái luôn hiện: `Bản dùng thử · còn 2 ngày 16 giờ · máy LFEQCHXZIKUG`

### Gia hạn

Người dùng đọc **mã máy** (12 ký tự, ở góc dưới cột trái, hoặc trên tấm phủ khi
đã khoá) rồi gửi cho anh. Trên máy anh:

```powershell
python tao_ma.py LFEQCHXZIKUG --gio 72
```

```
  Máy      : LFEQCHXZIKUG
  Hạn gốc  : 18:00 06/09/2026
  Hạn mới  : 18:00 09/09/2026   (+72 giờ)

  MÃ GIA HẠN:   D65P-R2ZS-SD8D-NA2M-KLCN
```

Gửi mã đó lại; họ gõ vào ô trên tấm phủ và bấm *Gia hạn*. Số giờ dùng được:
**24, 48, 72, 168 (1 tuần), 720 (30 ngày)** — chỉ đúng năm mức này, vì app dò mã
bằng cách thử lần lượt từng mức.

### ⚠️ `tao_ma.py` KHÔNG ĐƯỢC GỬI ĐI

Nó dùng chung khoá bí mật với `khoa.py`. Ai có nó thì tự sinh mã gia hạn cho máy
mình, tức cơ chế hạn dùng thành vô nghĩa.

Việc này được chặn ở **ba** chỗ, cố ý chồng lên nhau:

1. `dong_goi.py` truyền `--exclude-module tao_ma` cho PyInstaller (chặn đường
   import);
2. sau khi build, `don_goi()` xoá mọi file `tao_ma.*` lọt vào gói (chặn đường
   chép thẳng);
3. `kiem_goi.py` và bài tự kiểm bên trong app đều kiểm lại trên **gói đã build
   thật**, và báo hỏng nếu thấy nó.

### Khoá này chặn được gì, không chặn được gì

**Chặn được:** quên mất đã hết hạn; vặn đồng hồ máy lùi lại; chép thư mục dữ
liệu sang máy khác; sửa file giấy phép bằng tay (file có chữ ký HMAC gắn với mã
máy).

**Không chặn được:** người biết đọc mã nguồn hoặc dịch ngược file `.exe`. Khoá bí
mật nằm ngay trong gói — mà thật ra người đó cũng gỡ luôn được đoạn kiểm tra.
Muốn chặn thật thì phải kiểm qua máy chủ; ở đây cố tình không làm, vì máy studio
hay mất mạng lúc đang chạy job, và một cái khoá chặn người dùng hợp lệ vì rớt
mạng thì hại hơn lợi.

### Mã máy — chỗ này đã phải sửa

Bản đầu lấy địa chỉ MAC qua `uuid.getnode()`. Nhưng `getnode()` **không** bảo
đảm trả về MAC: khi không đọc được card mạng (máy ảo, container, máy tắt Wi-Fi,
máy chỉ có adapter ảo) thì Python **bịa ra một số ngẫu nhiên mới mỗi lần chạy** —
hành vi có tài liệu, không phải lỗi.

Hậu quả nếu để nguyên: người dùng gửi mã máy, anh cấp mã gia hạn, họ nhập vào
chạy được — đến **lần mở app tiếp theo** mã máy đã khác, chữ ký không khớp, app
báo *"giấy phép không khớp với máy này"* và khoá lại. Đúng người dùng hợp lệ bị
chặn, còn người muốn gian lận thì chẳng liên quan.

Bắt được ngay trong container đang chạy: ba lần chạy liên tiếp ra ba mã máy khác
nhau. Bài kiểm cũ không bắt được vì nó gọi `ma_may()` hai lần **trong một tiến
trình**, mà `getnode()` nhớ kết quả trong biến module.

Giờ mã máy lấy theo thứ tự: **mã định danh máy do hệ điều hành cấp**
(Windows `MachineGuid` / macOS `IOPlatformUUID` / Linux `machine-id`) → MAC thật
(chỉ khi chắc chắn là MAC thật) → số ngẫu nhiên sinh một lần rồi lưu lại. Và bài
kiểm giờ gọi qua **tiến trình con**, ba lần, so kết quả.

---

## 4. Bản macOS — **CHƯA CHẠY LẦN NÀO**

Anh trả lời là chưa có máy Mac, nên phần này viết sẵn để dùng sau. **Tôi chưa
chạy được một dòng nào trong đây**, và những chỗ dễ vấp thì tôi ghi rõ ở dưới
chứ không hứa là sẽ trơn tru.

Trên máy Mac:

```bash
cd /đường/dẫn/tới/AutoToneImages
python3 -m pip install pyinstaller
python3 dong_goi.py
python3 kiem_goi.py
```

Ra `dist/AutoTone.app` và `dist/AutoTone-mac.zip`.

**Ba chỗ nhiều khả năng phải xử lý thêm:**

1. **Gatekeeper.** `.app` chưa ký sẽ bị macOS chặn ở lần mở đầu. Người dùng phải
   bấm chuột phải → *Open* → *Open*, hoặc vào *System Settings → Privacy &
   Security* bấm *Open Anyway*. Muốn hết hẳn thì phải có tài khoản Apple
   Developer (99 USD/năm) để ký và notarize.
2. **Kiến trúc.** Không làm universal2 được vì torch không có bản universal. Máy
   Apple Silicon build ra bản arm64, máy Intel ra bản x86_64 — **không dùng chéo
   được**. Cần cả hai thì phải build trên cả hai loại máy.
3. **Retouch trên Mac.** ToolCloneEvoto dùng CUDA, mà Mac không có CUDA. Phần
   retouch trên Mac hoặc phải chạy CPU (rất chậm) hoặc phải chuyển sang MPS —
   chưa ai làm, chưa ai đo. Trước mắt nên build Mac với `--khong-retouch`.

---

## 5. Máy khách cần gì, và app để dữ liệu ở đâu

**Cần:** Windows 10/11 64-bit. **Không** cần cài Python — trình thông dịch nằm
sẵn trong gói. Lightroom Classic thì vẫn cần như thường.

**Cài:** giải nén zip vào đâu cũng được, ví dụ `C:\AutoTone\`, rồi bấm
`AutoTone.exe`. Nên tạo lối tắt ra Desktop.

**Dữ liệu người dùng** nằm ở `%LOCALAPPDATA%\AutoTone\` — gu đã học (`gu.json`),
trạng thái buổi chụp, cấu hình retouch, giấy phép (`khoa.json`), và **bản dùng
thật của plugin Lightroom** (chép ra từ gói ở lần chạy đầu).

Tách ra như vậy vì gói có thể nằm trong `Program Files` (không ghi được), và vì
trên macOS ghi vào trong `.app` là phá chữ ký. Đổi chỗ này được bằng biến môi
trường `AUTOTONE_DATA` — đó cũng là cách các bài kiểm chạy mà không đụng vào dữ
liệu thật.

**Cài plugin vào Lightroom:** *File → Plug-in Manager → Add*, trỏ vào
`%LOCALAPPDATA%\AutoTone\AutoTone.lrplugin`. Trỏ vào bản trong thư mục gói thì
sai — thư mục `jobs` bên trong nó phải ghi được.

---

## 6. Những gì đã sửa trong lúc đóng gói

Ba lỗi thật, tìm ra khi viết bài kiểm chứ không phải khi đọc lại mã:

1. **`measure()` hỏng với 4 trong 6 cách đo.** `face_stats`, `best_eye`,
   `best_sharp`, `fw_`, `fh_` chỉ được gán bên trong `if want_faces`, trong khi
   đoạn dưới đọc chúng vô điều kiện. Chọn cách đo *Trung bình / Trung vị / Ưu
   tiên giữa khung / Ưu tiên chủ thể* **cộng với** WB khác "Da trắng hồng" là
   `UnboundLocalError` — mà `measure()` bọc `try/except` toàn thân nên nó không
   nổ ra màn hình, chỉ biến thành *"không đọc được ảnh"* cho **cả thư mục**. Cấu
   hình mặc định (mặt + WB da) che kín lỗi này.
   → `kiem_do_mat.py` giờ chạy đủ 6 cách đo × 2 giá trị, **và** quét cây cú pháp
   để tìm tên nào "chỉ gán trong khối `if` mà vẫn đọc sau khối" — bắt cả loại lỗi
   này sẽ thêm vào sau, ở nhánh mà bài kiểm chưa nghĩ ra tổ hợp để chạm tới.

2. **Mã máy đổi mỗi lần chạy** — xem mục 3 ở trên.

3. **Giấy phép và dữ liệu app nằm hai nơi khác nhau.** `khoa.py` tự tính lấy chỗ
   lưu riêng thay vì hỏi `duong_dan.py`. Hai chỗ cùng quyết định "dữ liệu người
   dùng nằm đâu" thì sớm muộn cũng lệch, và lúc lệch thì chép thư mục dữ liệu
   sang máy mới là mất giấy phép mà không hiểu vì sao.

---

## 7. File nào làm gì

| File | Việc |
|---|---|
| `dong_goi.py` | Build gói. `--thu` để xem lệnh trước. |
| `kiem_goi.py` | Kiểm **gói đã build**. Chạy trước khi gửi đi. |
| `tu_kiem.py` | Bài tự kiểm app chạy **từ bên trong** gói. |
| `duong_dan.py` | Chỗ nào chỉ đọc, chỗ nào ghi được. |
| `khoa.py` | Hạn dùng thử, mã máy, mã gia hạn. |
| `tao_ma.py` | Sinh mã gia hạn. **⚠️ Không bao giờ gửi đi.** |
| `kiem_khoa.py` | Kiểm khoá: 13 nhóm phép kiểm. |
| `kiem_do_mat.py` | Kiểm `measure()` với mọi cách đo. |
