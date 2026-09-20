# Đóng gói AutoTone cho máy Mac

Tài liệu này viết cho lần đầu dựng bản Mac. Đọc hết một lượt rồi hãy làm —
có vài chỗ không quay lại sửa được nếu làm sai thứ tự.

---

## 0. Điều bắt buộc phải biết trước

**Bản `.app` cho Mac PHẢI được đóng gói TRÊN MÁY MAC.**

PyInstaller không dịch chéo (cross-compile) được. Nó không "dịch" chương trình
sang máy khác — nó gói **chính bản Python và chính các thư viện đang có trên máy
đang chạy nó** vào một thư mục. Trên Windows nó gói `python.exe` và các file
`.dll` của Windows; những thứ đó máy Mac không chạy được, và ngược lại.

Nên quy trình là:

1. Chép cả thư mục dự án sang máy Mac.
2. Trên máy Mac, bấm đúp `CAI_DAT_MAC.command`.
3. Ra `dist/AutoTone.app`.

Không có cách nào rút ngắn bước này. Bản `.exe` trên máy Windows vẫn giữ nguyên,
hai bản độc lập với nhau.

---

## 1. Chuẩn bị máy Mac

**Không phải cài gì cả.** Chỉ chép thư mục dự án sang máy Mac, đặt ở đâu cũng được
miễn **đường dẫn không có dấu tiếng Việt** — ví dụ `~/Desktop/AutoTone-mac`.

macOS đã có sẵn `curl`, `tar`, `shasum`, `hdiutil`, `codesign` — script chỉ dùng
đúng những thứ đó.

## 2. Đóng gói

Bấm đúp **`CAI_DAT_MAC.command`**. Bị chặn thì chuột phải → **Open** → **Open**.

Script tự làm theo thứ tự:

| Bước | Việc |
|------|------|
| 1 | Nhận kiến trúc máy (`arm64` / `x86_64`) |
| 2 | Tải bản Python riêng 15 MB có sẵn Tk 8.6 vào `.python_rieng/` — bỏ qua nếu đã có |
| 3 | Đối chiếu SHA256 file vừa tải, sai thì xoá và báo |
| 4 | Kiểm lại Tk **ngay trên bản vừa tải**, dưới 8.6 thì dừng |
| 5 | Cài `pyinstaller`, `pillow`, `numpy`, `opencv-python-headless` vào bản Python đó |
| 6 | Dò ToolCloneEvoto; không có thì tự chuyển sang bản nhẹ và **nói rõ** |
| 7 | Gọi `dong_goi.py` → `dist/AutoTone.app` |
| 8 | Xoá file không được lọt vào gói (`tao_ma.py`, các file kiểm) |
| 9 | Ký ad-hoc, gỡ `com.apple.quarantine` |
| 10 | Tạo `dist/AutoTone.dmg` (kéo-thả vào Applications) |
| 11 | Gọi `kiem_goi.py` tự kiểm gói vừa tạo |

Mất khoảng **20–40 phút**. Lần sau nhanh hơn nhiều vì Python và thư viện đã có.

### 2.1 Vì sao phải tải Python riêng

`/usr/bin/python3` của macOS đi kèm **Tk 8.5**. PyInstaller đóng gói theo đúng bản
Tk của Python dùng để build, nên gói sẽ mang Tk 8.5 — trên macOS đời mới nó vẽ
giao diện vỡ chữ, ô nhập không ăn chuột, và **lúc build không báo lỗi gì**.

Homebrew cũng không giải quyết gọn: `brew install python` **không** kèm tkinter,
phải thêm `brew install python-tk`; mà cài Homebrew là kéo về cả một hệ quản lý gói
vài trăm MB chỉ để làm một việc.

Bản `python-build-standalone` mang sẵn Tcl/Tk 8.6 dạng gắn tĩnh trong
`libpython`, nằm gọn trong thư mục dự án, **không cài gì vào hệ thống**. Xoá
`.python_rieng/` là sạch hoàn toàn.

> Đã kiểm thật, không phải suy đoán: bản này gắn `_tkinter` **tĩnh** vào
> `libpython` chứ không để file `.so` rời, nên có nguy cơ PyInstaller không tìm ra
> Tcl/Tk. Đã chạy thử trọn vẹn bằng bản Linux dựng y hệt cách đó — PyInstaller vẫn
> đóng được `_tcl_data` và `_tk_data` vào gói, và app đóng ra báo
> `Tk 8.6.14 · GÓI ĐẠT`.

### 2.2 Muốn chạy tay

```
./CAI_DAT_MAC.command --khong-retouch
```

Mọi tham số đều được chuyển thẳng cho `dong_goi.py`.

## 3. Đọc kết quả tự kiểm

Cuối cùng phải thấy:

```
GÓI ĐẠT
```

Nếu thấy `GÓI KHÔNG ĐẠT` thì đọc từng dòng `[!]` — mỗi dòng nói rõ thiếu gì.
**Đừng bỏ qua và cứ đem gói đi dùng.** Bài kiểm chạy chính con app vừa đóng, đo
ảnh thật, ghi `.xmp` thật rồi hoàn tác; nó đạt nghĩa là app chạy được thật, chứ
không phải chỉ "build không báo lỗi".

Muốn kiểm kỹ hơn bằng ảnh RAW thật của mình:

```bash
.python_rieng/python/bin/python3 kiem_goi.py dist/AutoTone.app ~/Pictures/mot_buoi_chup
```

Ảnh JPEG do bài kiểm tự sinh không bao giờ lộ ra được chuyện preview trong file
`.ARW` nằm ở đâu và to bao nhiêu — chỉ ảnh máy ảnh thật mới kiểm được phần đó.

---

## 4. Cài lên máy Mac khác

1. Chép `dist/AutoTone.dmg` sang.
2. Bấm đúp file `.dmg`.
3. Kéo `AutoTone` sang thư mục `Applications` hiện ngay bên cạnh.
4. **Lần đầu mở:** chuột phải → **Open** → **Open**.

Bước 4 bắt buộc, vì gói chưa được ký chứng chỉ Apple (Apple Developer ID tốn
99 USD/năm). Bấm đúp bình thường thì macOS chặn thẳng và **không** hiện nút cho
mở. Cách khác, chạy một lần trong Terminal:

```bash
xattr -dr com.apple.quarantine /Applications/AutoTone.app
```

---

## 5. Cài plugin cho Lightroom trên Mac

App tự chép plugin ra thư mục dữ liệu riêng khi chạy lần đầu:

```
~/Library/Application Support/AutoTone/AutoTone.lrplugin
```

Trong Lightroom Classic: **File → Plug-in Manager → Add**, trỏ tới đúng đường
dẫn trên. `~/Library` bị macOS ẩn — trong hộp thoại chọn file bấm
`Cmd + Shift + G` rồi dán đường dẫn vào.

**Không** trỏ vào bản plugin nằm trong `AutoTone.app`. Bên trong gói là vùng chỉ
đọc, plugin cần ghi thư mục `jobs/` nên sẽ hỏng.

---

## 6. Khác biệt so với bản Windows

| | Windows | macOS |
|---|---|---|
| Kết quả | `dist/AutoTone/AutoTone.exe` | `dist/AutoTone.app` |
| Thư mục dữ liệu | `%LOCALAPPDATA%\AutoTone` | `~/Library/Application Support/AutoTone` |
| Kiến trúc | x86_64 | arm64 (Apple Silicon) **hoặc** x86_64 (Intel) — theo máy build |
| Card đồ hoạ cho retouch | CUDA nếu có NVIDIA | **không có CUDA** — chạy CPU, chậm hơn nhiều |
| Lần đầu mở | Defender có thể cảnh báo | Gatekeeper chặn, phải chuột phải → Open |

### 6.1 Chuyện kiến trúc — đọc kỹ nếu có nhiều máy Mac

PyInstaller ra bản đúng theo **kiến trúc của máy đóng gói**:

- Đóng trên Mac Apple Silicon (M1/M2/M3/M4) → bản **arm64**. Máy Mac Intel
  **không chạy được**.
- Đóng trên Mac Intel → bản **x86_64**. Máy Apple Silicon chạy được qua lớp dịch
  Rosetta 2, nhưng chậm hơn.

Không làm bản universal2 (chạy cả hai) được, vì `torch` không có bản universal.

Nếu studio có cả hai loại máy: đóng trên máy **Intel** thì một gói dùng được cả
hai; đổi lại máy Apple Silicon chạy chậm hơn bản arm64.

### 6.2 Retouch trên Mac chạy CPU

Apple không dùng NVIDIA nên không có CUDA. Phần retouch vẫn chạy đúng, chỉ là
bằng CPU nên lâu hơn đáng kể. Bước đo ảnh và cân màu thì không ảnh hưởng — phần
đó vốn chạy CPU trên cả hai hệ.

---

## 7. Hỏng thì tra ở đây

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Mở app ra **nhiều cửa sổ chồng nhau, càng lúc càng nhiều** | Thiếu `multiprocessing.freeze_support()` | Đã sửa. Kiểm lại bằng `.python_rieng/python/bin/python3 kiem_da_tien_trinh.py` |
| Giao diện vỡ chữ, ô nhập không ăn chuột | Gói mang Tk 8.5 | Xoá `.python_rieng/` rồi bấm đúp `CAI_DAT_MAC.command` lại |
| *"AutoTone không thể mở vì chưa được xác minh"* | Gatekeeper | Chuột phải → Open → Open (mục 4) |
| Bấm đúp `CAI_DAT_MAC.command` không có gì xảy ra | Gatekeeper chặn hoặc mất bit chạy | Chuột phải → Open → Open |
| Báo *"khong khop ma bam"* | Mạng đứt giữa chừng khi tải Python | Bấm đúp lại — file hỏng đã bị xoá |
| Hộp thoại đòi *"command line developer tools"* | macOS cần bộ công cụ nền | Bấm **Install**, chờ xong rồi bấm đúp lại |
| Lightroom báo *"plugin không hợp lệ"* | Trỏ vào bản trong `.app` | Trỏ vào `~/Library/Application Support/AutoTone/…` (mục 5) |
| `.app` giải nén xong chạy sai / phình to gấp đôi | Nén bằng zip thường làm hỏng symlink trong `.app` | Nén lại bằng `ditto` — script đã làm sẵn |
| Đo ảnh xong không ra gì | Sai đường dẫn có dấu | Để dự án ở đường dẫn không dấu |

---

## 8. Vì sao có bài kiểm `kiem_da_tien_trinh.py`

Bước đo ảnh chạy tới 8 tiến trình song song. Ba hệ điều hành khởi động tiến trình
con theo hai kiểu:

- **Linux → `fork`:** tiến trình con là bản sao của tiến trình mẹ. Gần như không
  bao giờ hỏng.
- **macOS và Windows → `spawn`:** **chạy lại file thực thi từ đầu**, rồi nạp lại
  module.

Với bản đóng gói, "chạy lại file thực thi từ đầu" nghĩa là **mở lại chính app** —
tức là mở thêm một cửa sổ AutoTone nữa, mà cửa sổ đó lại mở tiếp 8 cửa sổ nữa.
Một dòng `multiprocessing.freeze_support()` ở đầu `main()` chặn chuyện này: nó
nhận ra tiến trình đang chạy là tiến trình con, làm việc của worker rồi thoát.

Lỗi này **không bao giờ lộ ra trên Linux** — nên `kiem_da_tien_trinh.py` ép dùng
`spawn` để lỗi của macOS hiện ra ngay lúc phát triển. Bài kiểm làm hai việc: đọc
cây cú pháp xem `freeze_support()` có thật sự nằm ở đầu `main()` không (viết
trong dòng chú thích thì không tính), và chạy thật một `Pool` kiểu `spawn` gọi
đúng hàm đo ảnh mà app dùng.

---

## 9. Trình tự rút gọn

```
# trên máy Mac — chép thư mục sang rồi:
#   bấm đúp CAI_DAT_MAC.command
#   (bị chặn thì chuột phải -> Open -> Open)

# muốn kiểm kỹ bằng ảnh RAW thật, sau khi đã đóng gói xong:
.python_rieng/python/bin/python3 kiem_goi.py dist/AutoTone.app ~/Pictures/mot_buoi_chup
```
