# Phát triển thẳng trên máy Mac

Bỏ hẳn vòng "sửa trên Windows → chép sang Mac → thử → báo lại". Trên Mac anh
sửa, chạy, thử ngay tại chỗ.

## Một lần duy nhất

### 1. Đưa kho lên GitHub (làm trên máy Windows)

Theo `HUONG_DAN_GITHUB.md`, phần A. Tóm tắt: GitHub Desktop → *Add local
repository* → `F:\Claude AI\AutoToneImages` → *create a repository* →
*Publish repository* → **tick `Keep this code private`**.

Rồi mở kho trên github.com và **tìm `tao_ma.py`. Phải không thấy nó.** File đó
dùng chung khoá bí mật với `khoa.py`; ai có nó thì tự sinh được mã gia hạn. Kho
riêng tư vẫn là một bản sao nằm trên máy người khác. Lỡ thấy thì xoá cả kho rồi
làm lại — xoá mỗi file không đủ, lịch sử vẫn giữ.

### 2. Trên Mac

```bash
# Công cụ dòng lệnh của Apple (có sẵn git)
xcode-select --install

# Lấy kho về
cd ~
git clone https://github.com/<tài-khoản>/AutoToneImages.git
cd AutoToneImages
```

### 3. Python cho Mac

**Đừng dùng `/usr/bin/python3` của macOS** — nó đi kèm Tk 8.5, và trên macOS
đời mới Tk 8.5 vẽ giao diện vỡ chữ, ô nhập không ăn chuột. Lỗi này không báo gì
lúc chạy, chỉ nhìn mới thấy.

Cách gọn nhất: mượn luôn bản Python riêng mà `CAI_DAT_MAC.command` tải về.

```bash
./CAI_DAT_MAC.command      # lần đầu: tải Python riêng + đóng gói thử
PY=./.python_rieng/python/bin/python3
$PY -c 'import tkinter; print("Tk", tkinter.TkVersion)'   # phải là 8.6 trở lên
```

Từ đó trở đi dùng `$PY` thay cho `python3`.

### 4. Cài Claude Code trên Mac

```bash
npm install -g @anthropic-ai/claude-code
cd ~/AutoToneImages
claude
```

Kho có sẵn `CLAUDE.md` ở thư mục gốc — Claude tự đọc nó khi mở, nên nó biết
ngay luật của dự án (không dựng lại logic trong bài kiểm, không nới ngưỡng,
`tao_ma.py` không đi đâu cả…) mà không phải kể lại.

## Vòng làm việc hằng ngày

```bash
$PY kiem_cu_phap.py        # 1 giây, chạy trước tiên
$PY autotone_gui.py        # chạy thẳng từ mã nguồn, không cần đóng gói
$PY kiem_man_hinh.py       # soi giao diện bằng Tk thật
```

Chạy từ mã nguồn thì **thư mục plugin là bản nằm ngay trong kho**
(`AutoToneImages/AutoTone.lrplugin`) — chứ không phải bản ở Application Support.
Add đúng bản đó vào Lightroom khi thử. Không chắc thì:

```bash
$PY chan_doan.py --plugin
```

Đóng gói `.app` chỉ làm khi muốn bản giao, không cần cho việc sửa hằng ngày.

## Đồng bộ hai máy

```bash
git pull        # lấy thay đổi từ máy kia
git push        # đẩy thay đổi của mình lên
```

Sửa cùng một file ở hai máy cùng lúc thì sẽ phải gộp tay. Cách tránh: mỗi lúc
chỉ sửa ở một máy, và `git pull` trước khi bắt đầu.

Thư mục `ChuyenSangMac/` đã bị `.gitignore` chặn — nó là bản chép để bung sang
Mac, không phải mã nguồn. Clone về là có đủ rồi.

## Thứ KHÔNG theo git, phải tự mang

Mấy thứ này nằm trong thư mục dữ liệu người dùng, mỗi máy một khác:

- `gu.json` — tham số đã học. **Đây là nghi phạm số một của vụ ΔEV lệch giữa
  hai máy**: Windows đã học cả tháng, Mac trắng tinh.
- `trang_thai/` — trạng thái từng buổi chụp
- `AutoTone.lrplugin/jobs/` — bản xuất từ Lightroom, nhật ký plugin
- `khoa.json` — giấy phép của riêng một máy

Muốn hai máy đo giống nhau thì phải chép `gu.json` sang. Xem `CLAUDE.md`, mục
"Đang treo".
