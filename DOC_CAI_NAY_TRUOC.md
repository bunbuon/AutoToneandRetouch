# AutoTone cho máy Mac — cài thế nào

## Làm đúng một việc

Bấm đúp vào **`CAI_DAT_MAC.command`**.

Xong. Không cần cài Python, không cần Homebrew, không cần gõ lệnh nào.

Nếu macOS chặn với thông báo *"không mở được vì chưa được xác minh"*: **chuột phải**
vào file đó → **Open** → **Open**. Chỉ phải làm lần đầu.

---

## Nó sẽ làm gì trong 20–40 phút đó

| | |
|---|---|
| 1 | Nhận ra máy Apple Silicon hay Intel |
| 2 | Tải một bản Python riêng 15 MB — bản này **tự mang theo Tk 8.6** bên trong |
| 3 | Đối chiếu mã băm SHA256 của file vừa tải |
| 4 | Cài thư viện **vào chính bản Python riêng đó** |
| 5 | Đóng gói ra `dist/AutoTone.app` |
| 6 | Ký ad-hoc, gỡ cờ cách ly của macOS |
| 7 | Tạo `dist/AutoTone.dmg` |
| 8 | Chạy bài tự kiểm trên gói vừa tạo |

Cuối màn hình phải thấy **`XONG`** và đường dẫn tới file `.dmg`.

**Không đóng cửa sổ Terminal trong lúc chạy.** Nó hiện chữ chạy liên tục — đó là
bình thường, không phải lỗi.

## Cài app

1. Bấm đúp `dist/AutoTone.dmg`
2. Kéo biểu tượng **AutoTone** sang thư mục **Applications** bên cạnh
3. Lần đầu mở: **chuột phải** vào AutoTone → **Open** → **Open**

Đúng như cài một app tải từ mạng về.

---

## Vì sao phải tải Python riêng thay vì dùng Python của máy

`/usr/bin/python3` có sẵn trong macOS đi kèm **Tk 8.5**. PyInstaller đóng gói theo
đúng bản Tk của Python dùng để build, nên gói sẽ mang Tk 8.5 — và trên macOS đời
mới, Tk 8.5 vẽ giao diện vỡ chữ, ô nhập không ăn chuột.

Điểm tệ nhất: **lúc build không báo lỗi gì cả**. Mở app ra mới thấy, mà lúc đó đã
mất 40 phút.

Bản Python mà script tải về mang sẵn Tcl/Tk 8.6 bên trong, nằm gọn trong thư mục
`.python_rieng/` của dự án. Nó **không cài gì vào hệ thống**, không đụng tới Python
hay Tk sẵn có. Muốn gỡ sạch thì xoá thư mục đó là xong.

Lần chạy sau nó dùng lại bản đã tải, không tải lại.

---

## Đóng gói lại sau khi tôi sửa code

Chép đè các file `.py` mới vào thư mục này, rồi bấm đúp `CAI_DAT_MAC.command` lần
nữa. Lần này nhanh hơn nhiều vì Python và thư viện đã có sẵn.

---

## Hai thứ CỐ TÌNH không mang sang

**`tao_ma.py`** — file sinh mã gia hạn, dùng chung khoá bí mật với `khoa.py`. Ai có
nó thì tự sinh mã được, tức cơ chế hạn dùng thành vô nghĩa. Nó chỉ nên nằm ở một
chỗ duy nhất là máy Windows gốc.

Máy Mac có **mã máy khác** máy Windows nên cần mã gia hạn riêng. Cách làm không cần
chép `tao_ma.py` đi đâu cả: chạy nó **trên máy Windows**, nhập mã máy mà app trên
Mac hiện ra, rồi gõ mã sinh được vào app trên Mac.

**Dữ liệu đang chạy** — `gu/`, `trang_thai/`, `khoa.json`, `retouch.json`, `jobs/`.
Đây là trạng thái riêng của máy Windows, mang sang chỉ gây lẫn. App trên Mac tự tạo
lại ở `~/Library/Application Support/AutoTone`.

> Muốn giữ **gu đã học** (`gu/gu.json`): chép riêng file đó sang
> `~/Library/Application Support/AutoTone/` **sau khi** đã chạy app trên Mac một
> lần. Chép trước thì lần khởi động đầu ghi đè mất.

---

## Nếu hỏng

| Hiện tượng | Cách xử lý |
|---|---|
| Bấm đúp không có gì xảy ra, hoặc bị chặn | Chuột phải → Open → Open |
| Dừng ở bước tải, báo mạng hỏng | Bấm đúp lại — nó tự thử lại và tự dùng lại phần đã tải |
| Báo *"khong khop ma bam"* | Mạng đứt giữa chừng. File hỏng đã bị xoá, bấm đúp lại là xong |
| Hiện hộp thoại đòi cài *"command line developer tools"* | Bấm **Install**, chờ xong rồi bấm đúp lại |
| Báo *"Khong thay ToolCloneEvoto"* | Bình thường — gói ra sẽ đủ phần cân sáng/cân màu, chỉ thiếu nút Retouch |
| Bài kiểm cuối báo `[!]` | Đọc đúng dòng đó rồi gửi tôi. Đừng đem gói đi dùng |

Chi tiết hơn: `HUONG_DAN_MACOS.md`.

---

## Có cách không phải build gì cả

`HUONG_DAN_GITHUB.md` chỉ cách để GitHub dựng app hộ trên máy Mac của họ — máy anh
chỉ còn việc tải file `.dmg` về và kéo vào Applications. Chuẩn bị một lần ~15 phút,
từ đó về sau mỗi lần lấy app mới chỉ là bấm hai nút.

Hai đường dùng chung một `dong_goi.py` và đều tự kiểm gói vừa tạo, nên kết quả như
nhau — chỉ khác ai làm việc nặng.
