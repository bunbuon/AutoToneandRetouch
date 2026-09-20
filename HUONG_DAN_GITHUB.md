# Để GitHub build hộ — máy mình chỉ tải app về

Cách này bỏ hẳn bước đóng gói khỏi máy anh. GitHub có sẵn máy Mac và máy Windows;
mình gửi mã nguồn lên, bấm một nút, 20 phút sau tải file `.dmg` về cài.

Phải làm **một lần duy nhất** phần chuẩn bị. Từ lần thứ hai trở đi chỉ còn hai
động tác: bấm Push, rồi bấm Run.

---

## Phần A — chuẩn bị (làm một lần, khoảng 15 phút)

### A1. Tạo tài khoản GitHub

Vào <https://github.com> → **Sign up**. Miễn phí.

### A2. Cài GitHub Desktop

Tải ở <https://desktop.github.com> rồi cài như phần mềm thường. Đăng nhập bằng tài
khoản vừa tạo.

> Dùng GitHub Desktop chứ không dùng dòng lệnh `git` — vì nó là giao diện bấm nút,
> và phần việc ở đây chỉ có "gửi thay đổi lên" chứ không cần gì phức tạp hơn.

### A3. Đưa dự án lên

Trong GitHub Desktop:

1. **File → Add local repository…**
2. Chọn `F:\Claude AI\AutoToneImages`
3. Nó sẽ báo *"this directory does not appear to be a Git repository"* → bấm
   **create a repository**
4. Bấm **Create repository**
5. Bấm **Publish repository** ở thanh trên
6. **QUAN TRỌNG: tick ô `Keep this code private`** rồi mới bấm Publish

### A4. Kiểm lại thứ không được lên

Sau khi publish, mở kho trên github.com và tìm file `tao_ma.py`. **Phải không thấy
nó.**

File `.gitignore` trong dự án đã chặn sẵn `tao_ma.py` và `khoa.json`. Nhưng đây là
thứ đáng bỏ 30 giây kiểm bằng mắt: `tao_ma.py` dùng chung khoá bí mật với
`khoa.py`, ai có nó thì tự sinh được mã gia hạn. Kho riêng tư vẫn là một bản sao
nằm ở máy người khác.

Nếu lỡ thấy nó trên đó: xoá kho đi, làm lại từ A3. Đừng chỉ xoá file — lịch sử vẫn
còn giữ.

---

## Phần B — build (mỗi lần muốn app mới)

### B1. Biết máy Mac của mình là loại nào

 → **About This Mac**

- Dòng **Chip** ghi `Apple M1/M2/M3/M4` → chọn **`mac-arm64`**
- Dòng ghi `Intel` → chọn **`mac-intel`**

Chọn sai thì app tải về không chạy được.

### B2. Bấm nút

1. Mở kho trên github.com
2. Tab **Actions**
3. Cột trái chọn **Dong goi AutoTone**
4. Bên phải bấm **Run workflow**
5. Ô **Dong goi cho may nao** chọn đúng loại máy ở B1
6. Bấm **Run workflow** màu xanh

Chờ khoảng **15–20 phút**. Trang tự cập nhật, dấu tick xanh là xong.

### B3. Tải về và cài

1. Bấm vào lần chạy vừa xong
2. Kéo xuống mục **Artifacts**
3. Bấm `AutoTone-macOS-arm64` (hoặc `-x86_64`) để tải
4. GitHub luôn gói artifact trong file `.zip` → giải nén sẽ ra `AutoTone-arm64.dmg`
5. Bấm đúp file `.dmg`, kéo **AutoTone** sang **Applications**
6. **Lần đầu mở: chuột phải vào AutoTone → Open → Open**

Bước 6 bắt buộc. File tải qua trình duyệt bị macOS dán cờ cách ly, mà gói lại chưa
được ký chứng chỉ Apple (99 USD/năm), nên bấm đúp bình thường sẽ bị chặn thẳng.

---

## Phần C — sau khi tôi sửa code

1. Tôi ghi file mới vào `F:\Claude AI\AutoToneImages`
2. Anh mở GitHub Desktop → thấy danh sách file đã đổi → gõ vài chữ mô tả →
   **Commit to main** → **Push origin**
3. Làm lại phần B

---

## Về quota — đọc kỹ chỗ này

GitHub Free cho **2.000 phút/tháng** với kho riêng tư. Nhưng **máy Mac tính giá gấp
khoảng 10 lần** máy Linux ($0,062 so với $0,006 mỗi phút), nên thực chất chỉ còn
khoảng **200 phút Mac mỗi tháng**.

Một lần build Mac mất 15–20 phút → khoảng **10 lần build Mac/tháng**.

Vì vậy tôi cố ý làm ba việc:

| Việc | Lý do |
|---|---|
| Chỉ chạy khi **bấm tay**, không tự chạy mỗi lần đẩy mã | Phần lớn lần sửa code chưa cần gói mới |
| Mặc định chỉ dựng **một kiến trúc** | Dựng cả hai là tốn gấp đôi mà máy anh chỉ dùng một |
| Bấm nhầm hai lần thì **huỷ lần trước** | Khỏi đốt quota gấp đôi |

Muốn xem đã dùng bao nhiêu: ảnh đại diện góc phải → **Settings → Billing**.

Nếu có tháng nào hết quota: dùng `CAI_DAT_MAC.command` trên máy Mac — nó không tốn
gì cả, chỉ tốn thời gian chờ.

---

## Hai đường này khác nhau chỗ nào

| | `CAI_DAT_MAC.command` | GitHub build hộ |
|---|---|---|
| Chuẩn bị ban đầu | Không có | ~15 phút, làm một lần |
| Mỗi lần lấy app mới | Chép file sang Mac, bấm đúp, chờ 20–40 phút | Bấm Push, bấm Run, chờ 15–20 phút, tải về |
| Máy Mac phải làm gì | Chạy build | Không gì cả |
| Giới hạn | Không | ~10 lần Mac/tháng |
| Ra bản Windows luôn | Không | Có |
| Cần mạng | Lần đầu | Luôn |

Cả hai đều dùng chung `dong_goi.py` và đều chạy `kiem_goi.py` trên gói vừa tạo, nên
kết quả giống nhau — chỉ khác chỗ ai làm việc nặng.

---

## Nguồn

- [GitHub Actions billing — số phút đi kèm từng gói](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Actions runner pricing — giá từng loại máy](https://docs.github.com/en/billing/reference/actions-runner-pricing)
