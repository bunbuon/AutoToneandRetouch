# AutoTone — ghi chú cho Claude làm việc trên dự án này

Viết cho phiên Claude nào mở kho này, ở bất kỳ máy nào. Đọc hết trước khi sửa
dòng đầu tiên. Mấy luật dưới đây không phải sở thích — mỗi cái đều đổi bằng một
lần hỏng thật, có ngày tháng.

## Dự án là gì

Tự động cân sáng / cân màu ảnh sự kiện cho Lightroom Classic. Bảy khâu:

1. Nạp ảnh
2. Phân tích — đo sáng, cân màu, tách cảnh, lọc ảnh trùng
3. Đẩy vào Lightroom — qua plugin Lua, kèm Duyệt nhanh và lưới soát màu
4. Export — đọc thư mục Export của Lightroom, hoặc Export thẳng từ app
5. Retouch — gọi tool ngoài (ToolCloneEvoto). Bản mac hiện TÁCH phần này ra.
6. Gói duyệt — "vì sao tôi sửa"
7. Gu đã học

Giao diện: Tkinter (`autotone_gui.py`). Lõi đo đạc: `autotone.py`. Plugin
Lightroom: `AutoTone.lrplugin/*.lua` (Lightroom Classic **chỉ** có SDK Lua —
không CEP, không UXP; Adobe đã nói rõ là không có trong lộ trình).

Từ tối 3/10 giao diện dựng theo **Evoto**: KHÔNG còn cột trái. Thanh công cụ
(buổi ▾ · lần gửi · "1 · Phân tích" · "2 · Ghi và đẩy" · ⋯), giữa là LƯỚI ẢNH cả
buổi (bảng số là chế độ xem phụ), bên phải bảng điều khiển Cân tone, sát mép phải
cột mô-đun Cân tone / Retouch. Các khâu khác vẫn dựng đủ trong mã nhưng KHÔNG còn
lối vào (trừ Duyệt nhanh, qua menu ⋯) — xem hai mục "Giao diện gọn" và "Giao diện
kiểu Evoto" cuối file. Mô-đun Retouch: MỘT ẢNH LỚN ở trên (zoom, giữ xem gốc,
xem trước tính ngay trên đó), dải ảnh ở dưới — mục "Retouch: ảnh lớn + dải ảnh".

Người dùng nói tiếng Việt. **Trả lời bằng tiếng Việt.**

## Luật cứng

**Không bao giờ dựng lại logic sản xuất trong công cụ phân tích.** Bài kiểm và
script chẩn đoán phải GỌI chính hàm thật (`at.collect_pairs`, `at.measure`,
`rt.lenh`…). Chép lại logic thì bài kiểm đúng mà app vẫn sai — đã xảy ra.

**Bài kiểm phải được thử ngược.** Viết xong thì cố tình phá code cho nó đỏ, rồi
mới trả lại. Bài kiểm chưa từng đỏ là bài kiểm chưa biết nó canh cái gì.

**Không nới ngưỡng đã đặt.** Ngưỡng đặt TRƯỚC khi chạy. Không đạt thì bỏ phương
án và ghi lại vì sao, không hạ ngưỡng cho vừa kết quả.

**`tao_ma.py` không bao giờ rời máy Windows.** Nó dùng chung khoá bí mật với
`khoa.py`; ai có nó thì tự sinh mã gia hạn. `.gitignore` đã chặn, `dong_goi.py`
cũng loại nó khỏi gói. Đừng gỡ chặn ở bất kỳ đâu.

**ToolCloneEvoto là dự án RIÊNG** (`F:\Claude AI\ToolCloneEvoto` trên máy
Windows). Hỏi trước khi sửa gì bên đó.

**Ảnh 1 sao không xuất, không retouch.** Quy ước dùng chung ở mọi khâu.

## Cách viết chú thích, và một cái bẫy

Chú thích dài viết trong khối `#[[ ... #]]`, đặt trong docstring, giải thích
**vì sao** chứ không phải **làm gì** — kèm ngày tháng và con số đo được khi có.

Cái bẫy: khối đó nằm TRONG docstring, nên rất dễ quên dấu `"""` đóng. Quên thì
docstring nuốt luôn mấy chục dòng mã, và Python báo lỗi ở một dòng hoàn toàn
khác — thường là một chữ tiếng Việt trong docstring của hàm kế tiếp. Đã mắc bốn
lần trong hai ngày.

Chạy `python3 kiem_cu_phap.py` sau mỗi lần sửa. Nó nạp thử mọi file `.py` và
bắt lỗi này trong một giây.

## Bài kiểm

```
python3 kiem_cu_phap.py        # nạp thử mọi file .py — chạy đầu tiên
python3 kiem_tham_chieu.py     # mọi at.X / self.x() phải có thật (3/10)
python3 kiem_mac.py            # mấy chỗ chỉ hỏng trên macOS
python3 kiem_dong_goi.py       # rà trước khi đóng gói
python3 kiem_bo_cuc.py         # bố cục giao diện, đọc mã nguồn
python3 kiem_moc_va_xuat.py    # mốc baseline và bản xuất catalog
python3 kiem_che_do_sang.py    # ngoài trời / trong nhà theo EV100
python3 test_preset_khong_wb_tone.py  # preset bỏ trống WB/Tone (3/10)
python3 test_mat_ao_to.py      # bỏ khung mặt vừa điểm thấp vừa to (3/10)
python3 test_dung_lai_buoi.py  # dùng lại buổi đã chạy: bản xuất theo thư mục (3/10)
python3 test_bu_sang.py        # bù sáng cả buổi / loại buổi (3/10; phần GUI cần màn hình)
python3 test_dong_bo_loat.py   # cùng khung + cùng thông số -> cùng một mức (3/10)
python3 test_wb_asshot.py      # preset bỏ trống WB: kéo Temp về As Shot (3/10, bước 2)
python3 kiem_ban_xuat.py       # app đọc lại bản xuất (cần tkinter)
python3 kiem_xuat_lr.py        # khâu 5 — bắt đường dẫn Export
python3 kiem_tim_tool.py       # tìm tool retouch
python3 kiem_retouch_095.py    # nối với saytool 0.9.5
python3 kiem_duyet_py.py       # Duyệt nhanh, phía Python

# cần màn hình (macOS chạy thẳng; Linux dùng xvfb-run -a)
python3 kiem_man_hinh.py       # mở CẢ app, soi chữ bị cắt (nhãn, ô chọn, nút vẽ tay), bảng điều khiển phải
python3 kiem_ve_that.py        # lưới ảnh vẽ thật: chia cột, chỉ vẽ ô đang nhìn, chọn ô, kho ảnh nhỏ, dải ảnh
python3 kiem_khung_anh.py      # ảnh lớn: zoom quanh con trỏ, kéo, nháy đúp, giữ xem gốc, nạp dần, vào mặt
python3 kiem_retouch_gui.py    # mô-đun Retouch: ảnh lớn + dải ảnh, bảng phải, nút Chạy, xem trước trên ảnh lớn (tool giả)
python3 kiem_xem_truoc.py      # xem trước với tool THẬT (máy Windows); AUTOTONE_TOOL_THU / AUTOTONE_ANH_THU để chỉ chỗ khác
python3 kiem_gui_duyet.py      # khâu Duyệt nhanh & Lightroom
python3 test_giao_dien_gon.py  # khung Evoto, nút Ghi, dải báo, một dòng, nhóm, thanh trượt, dấu ?

# cần lua5.1
lua5.1 kiem_duyet.lua AutoTone.lrplugin
lua5.1 kiem_batduongdan.lua AutoTone.lrplugin
lua5.1 kiem_xuatanh.lua AutoTone.lrplugin
lua5.1 kiem_dung_preview.lua AutoTone.lrplugin
lua5.1 kiem_chup.lua AutoTone.lrplugin       # chụp nguyên trạng bộ đã sửa
lua5.1 kiem_xuat_thong_so.lua AutoTone.lrplugin  # bản xuất có WhiteBalance/Contrast...
lua5.1 kiem_ket_qua_xuat.lua AutoTone.lrplugin   # giữ 30 bản xuất + ketqua_xuat.txt
```

## Chạy và đóng gói

```
python3 autotone_gui.py                    # chạy từ mã nguồn
python3 dong_goi.py --khong-retouch --khong-khoa   # đóng .app trên Mac
./CAI_DAT_MAC.command                      # tự tải Python riêng rồi đóng gói
python3 chan_doan.py "/thu/muc/anh"        # chẩn đoán khâu Phân tích
python3 chan_doan.py --anh "ANH.ARW"       # số đo thô một tấm, để so hai máy
python3 chan_doan.py --plugin              # thư mục plugin phải Add
python3 dong_goi.py --bao-mat              # đóng gói BẢN MÃ HOÁ LÕI (xem dưới)
```

## Bảo vệ mã nguồn: mã hoá lõi bằng Cython (4/10)

User: "mã hoá hết các model… tránh bị clone hay crack… viết 1 dòng để AI chọc
vào thì không lấy được code". Ba điểm đã nói thẳng với user và chốt:

- **Model KHÔNG mã hoá — vô ích.** Cả ba model đều công khai, tải tự do:
  `face_detection_yunet_2023mar.onnx` (YuNet/OpenCV), `resnet34_faceparse.onnx`,
  `buffalo_l` (InsightFace). Giá trị nằm ở **code Python**, không ở model.
- **Gói PyInstaller cũ ≈ phát hành mã nguồn.** `.pyc` trong PYZ, pyinstxtractor
  + dịch ngược ra Python đọc được trong vài phút.
- **Không app desktop nào bất khả crack.** Mã chạy trên máy khách. Mục tiêu: chặn
  "giải nén + đọc nguồn", giấu thuật toán + ngưỡng, nâng chi phí cắp.

**Cách làm — `bao_mat.py` + `dong_goi.py --bao-mat` (TUỲ CHỌN, không mặc định):**
- Cython dịch module lõi `.py → C → .pyd` (Windows) / `.so` (Mac): mở ra chỉ còn
  mã máy, `inspect.getsource()` vô hiệu, chuỗi hằng không nằm nguyên để grep.
  Đây là nghĩa THẬT của "AI chọc vào không lấy được code" — không phải câu comment.
- `bao_mat.MA_HOA` = lõi đáng giấu: `autotone, retouch, khoa, ban_quyen, thu_gu,
  learn_corrections, giao_dien, autotone_gui`. `dong_goi.MA_HOA_HET=True` để mã
  hoá MỌI `.py` ship (kín hơn, build lâu hơn — chỉ bật sau khi bản chỉ-lõi chạy ổn).
- `dung_cay_nguon()` dựng cây `build/nguon_bao_mat/`: lõi thành `.pyd/.so` (KHÔNG
  kèm `.py`), phần còn lại là `.py` có banner bản quyền, + launcher mỏng `chay.py`
  + `BAN_QUYEN.txt`. PyInstaller trỏ `--paths` + điểm vào vào cây này; cây GỐC
  không bị đụng. Điểm vào đã biên dịch nên PyInstaller không dò được import của
  nó → khai HẾT module trong cây vào `--hidden-import` (xem `ten_module_cay`).
- Đường build mặc định (không `--bao-mat`) giữ nguyên TỪNG CHỮ — chỉ thêm
  `--exclude-module bao_mat`. Bản cũ vẫn chạy y hệt.

**GIỚI HẠN — đừng tưởng bất khả xâm phạm (đã kiểm tận tay):**
- Hằng số cấp module vẫn đọc được LÚC CHẠY: `import khoa; khoa.BI_MAT` ra ngay
  khoá bí mật. Cython KHÔNG giấu cái đó. Khoá bản quyền vẫn MỀM đúng như
  `ban_quyen.py` ghi. Muốn cứng phải kiểm qua máy chủ (dự án cố ý không làm).
- `BI_MAT` không còn là chuỗi grep được trong `.so` (Cython gói bảng hằng), nhưng
  đó chỉ chặn tĩnh, không chặn `import` lúc chạy.

**Build trên từng máy (KHÔNG build chéo, như PyInstaller) — cần trình biên dịch C:**
- Windows: Microsoft C++ Build Tools (hoặc Visual Studio Desktop C++), rồi
  `venv_build\Scripts\python dong_goi.py --bao-mat`
- macOS: `xcode-select --install`, rồi `python3 dong_goi.py --bao-mat`
- Thiếu trình biên dịch → `bao_mat` báo lỗi rõ và dong_goi DỪNG, không âm thầm
  lùi về gói `.py` chưa mã hoá.

**Kiểm sau khi build (phải làm trên máy đích):**
- `kiem_goi.py` trỏ vào gói.
- Thử ngược trên cây staging: với `build/nguon_bao_mat` trước trên `sys.path`,
  `import autotone` phải ra `.so/.pyd`, và `test_san_phang` / `test_2ban_quay`
  phải ĐẠT (lõi biên dịch cho kết quả y hệt nguồn).
- Mở gói bằng pyinstxtractor: phải thấy `autotone...pyd/.so`, KHÔNG thấy
  `autotone.pyc` (và tương tự các module lõi khác).

**BẪY đã sập & vá (4/10) — vì sao PHẢI khai `quet_import_an`:** lần build Linux
đầu, gói chạy lên chết ngay: `ImportError: cannot import name filedialog`. Điểm
vào `autotone_gui` đã thành `.so` nên PyInstaller không đọc được `from tkinter
import filedialog` của nó → thiếu submodule `tkinter.filedialog` (và `.messagebox`,
`.ttk`, `.font`, các `PIL.*`...). Đây là bẫy CHUNG khi biên dịch điểm vào: mọi
`from X import Y` dạng submodule thư viện bị mất. Vá: `bao_mat.quet_import_an()`
dùng `ast` quét nguồn các module đem biên dịch, trả MỌI tên import (kể cả
`tkinter.filedialog`), và dong_goi nhét hết vào `--hidden-import`.

**Đã chứng minh TRỌN VẸN trên Linux (4/10):**
- 8/8 module cythonize sạch cú pháp; `.so` chạy đúng; `inspect.getsource` vô hiệu;
  `BI_MAT` không grep được trong `.so` (nhưng `khoa.BI_MAT` lúc chạy vẫn ra —
  giới hạn đã nêu).
- `test_san_phang` + `test_2ban_quay` ĐẠT khi `import autotone` là `.so`.
- Build `dong_goi.py --bao-mat --khong-retouch` TRÓT LỌT: gói chỉ chứa
  `autotone...so` (và 6 lõi khác), KHÔNG có `.pyc`/`.py` của lõi. Chạy gói
  (`AUTOTONE_TU_KIEM=1 ./AutoTone`): mọi mục ĐẠT (môi trường, model, khoá,
  `tao_ma.py` không lọt gói, đo 6/6, tách cảnh...). 5 mục HONG đều là `retouch`
  — đúng điều kiện `--khong-retouch` (retouch cần ToolCloneEvoto + torch, build
  trên máy đích), KHÔNG phải lỗi mã hoá: bản `--khong-retouch` thường cũng báo
  y hệt 5 mục đó.
- CÒN PHẢI KIỂM TRÊN MÁY ĐÍCH: build `.pyd` trên Windows + `.so` trên Mac (trình
  biên dịch C khác nhau), và bản CÓ retouch (torch + saytool đầy đủ).

**BỔ SUNG 4/10 — `--bao-mat` nay bọc CẢ phần retouch (saytool + model tự học):**
- Mục trên chỉ dịch LÕI AutoTone. `saytool/` (thuật toán retouch) và `mo_hinh/*.pt|npz`
  (model TỰ HỌC của ToolCloneEvoto) mới là phần đáng giấu nhất, và trước đó vẫn ship
  `.py` + `.pt` đọc được qua `saytool_du()`/`mo_hinh_du()`. "Model mã hoá vô ích" ở trên
  CHỈ đúng với model bên thứ ba (YuNet/faceparse/buffalo_l) — model retouch trong
  `ToolCloneEvoto/mo_hinh` là IP tự train, NAY đã mã hoá.
- `dong_goi.py --bao-mat`: sau khi mã hoá lõi, nếu `retouch_vao` thì chạy
  `<tool>/dong_goi_bao_mat.py --ra build/retouch_bao_mat` (script ở GỐC ToolCloneEvoto:
  Cython dịch saytool → `.pyd/.so` giữ 4 vỏ `__init__/cli/duong_dan`, mã hoá model; TỰ
  KIỂM giải mã khớp SHA + nạp thử, hỏng → mã ≠ 0 → DỪNG), rồi trỏ `goc_tool` vào cây đó.
  `saytool_du()`/`mo_hinh_du()` KHÔNG đổi — tự lấy `.so` + model mã hoá (cùng tên tệp).
  Chi tiết + quy tắc thêm model: `ToolCloneEvoto/CLAUDE.md` mục "Bảo mật bản final".
- `dong_goi.py --so-anh <thư mục>` (kèm `--bao-mat`): chạy THẬT 7 bước retouch bằng tool
  gốc và bản bảo mật, so ảnh ra — bản giao khách nên chạy (vài phút). Windows: dùng
  `DONG_GOI_BAO_MAT.bat` (tự dò Build Tools C++ + cython, chạy kèm `--so-anh bo_thuc`).
- `build-mac.yml`: MẶC ĐỊNH `--bao-mat` mọi lần (ô `khong_bao_mat` chỉ để gỡ lỗi — bản
  ra sẽ có mã nguồn đọc được, KHÔNG giao khách); cài thêm `cython` (+`torch` khi có
  retouch, để self-check nạp model trên chính máy Mac — chỗ DUY NHẤT kiểm được `.so` Mac);
  `timeout 90`; bước "Xem có gì trong gói" CHẶN build (exit 1) nếu `saytool` còn `.py` lạ
  ngoài 4 vỏ. `--nhe` vẫn loại torch khỏi GÓI (chỉ dùng lúc self-check rồi vứt).
- `dong_goi_bao_mat.py` KHÔNG mang bí mật (khoá model nằm trong
  `ToolCloneEvoto/saytool/bao_mat.py`, thuộc repo Private) — cứ để lên repo đó.

## Chuyện đã học về macOS

- **File `._TÊN.ARW`** — rác resource fork macOS để lại khi chép qua exFAT/NTFS.
  Có đúng đuôi `.ARW` nên lọt bộ lọc; Finder không hiện. `collect_pairs` đã bỏ.
- **`os.path.normcase()` chỉ viết thường trên Windows.** Ổ mặc định của macOS
  (APFS, HFS+) lại KHÔNG phân biệt hoa thường. Dùng `at.khoa_duong_dan()`.
- **Thư mục plugin khác nhau tuỳ cách chạy**: chạy từ mã nguồn thì plugin nằm
  cạnh file `.py`; chạy từ `.app` thì ở
  `~/Library/Application Support/AutoTone/AutoTone.lrplugin`. Add nhầm bản thì
  Lightroom ghi một nơi, app đọc một nơi, không bên nào báo lỗi.
- **stdout của tiến trình con** lấy mã trang hệ thống (cp1252 trên Windows) và
  đệm theo khối 8 KB. Ép `PYTHONIOENCODING`, `PYTHONUTF8`, `PYTHONUNBUFFERED`,
  và để JSON ở dạng thuần ASCII.
- **Không build chéo được.** `.app` phải build trên Mac, `.exe` trên Windows.

## Đang treo: ΔEV lệch giữa Windows và Mac

Cùng một tấm (ví dụ `03142`), cùng một bộ 64 ảnh: Windows ra **−0.26**, Mac ra
**+1.20**. Lệch ~1.46 EV.

Đã loại trừ: số ảnh trong mẻ (người dùng đã chạy cùng bộ).

Đã loại trừ: số ảnh trong mẻ; và **`gu.json` không hề tồn tại trên máy
Windows** (đã kiểm cả `%LOCALAPPDATA%\AutoTone` lẫn thư mục dự án) — tức hai
máy cùng chạy bằng DEFAULTS, không phải chuyện tham số đã học.

Còn lại, theo thứ tự khả năng:

1. **Bộ nhận diện mặt không chạy trên một trong hai máy.** Đây là nghi phạm
   hàng đầu. Ở chế độ đo `face`, ảnh thấy mặt đo theo thang MẶT, ảnh không thấy
   mặt lùi về thang CHỦ THỂ, và `decide()` bù chênh bằng trung vị của những ảnh
   có CẢ HAI. Không máy nào thấy mặt thì không còn gì để bù, bù thành 0, trong
   khi mục đích vẫn lấy theo `face_target_ev` — lệch cả mẻ một khoảng gần như
   cố định. Đúng hình dạng của 1,46 EV. Và `face_detector()` **nuốt mọi lỗi**
   rồi trả None, nên nhìn từ ngoài không có dấu hiệu gì.
   `chan_doan.py --anh` giờ in thẳng: có `metered_face_ev` hay không.
2. **Tuỳ chọn trên giao diện khác nhau** — mức đích, chế độ, cách đo, luật tách
   cảnh. Chúng KHÔNG được lưu giữa các lần chạy, nên mỗi máy khởi động bằng
   DEFAULTS; nhưng nếu người dùng đã chỉnh trên Windows trong phiên đang mở thì
   hai bên khác nhau thật.
3. **Bản xuất catalog** — cho biết ảnh đang có sẵn Exposure bao nhiêu.
4. **Thư viện giải nén** (numpy / Pillow) đọc preview ra khác nhau.

Cách phân biệt: chạy `chan_doan.py --anh` trên CẢ HAI máy rồi so. Số đo thô
giống nhau → lỗi ở (1) hoặc (2). Số đo thô đã khác → lỗi ở (3).

## Đang chờ cổng: hai bản sửa ngày 29/9 (cả hai đang TẮT)

Người dùng báo: cùng khung cảnh, ánh sáng gần như không đổi, tool kéo một tấm
lệch EV hẳn. Chạy lại đúng buổi `G:\HPC 25nam\TEST` (88 ảnh) bằng `plan()` thật —
khớp 88/88 với bản đã đẩy vào Lightroom — thì thấy:

- **NDT09826 KHÔNG bị tách cảnh** (cảnh 0, 34 ảnh; cùng f/2.8, 1/200, ISO 320).
  Độ sáng khung khớp hàng xóm; riêng phép đo MẶT nhảy lên −0.51 so với −1.05..−1.19.
  San phẳng cảnh làm mọi tấm cùng "độ sáng mặt SAU chỉnh", nên đo sai bao nhiêu
  thì thanh Exposure lệch bấy nhiêu: −0.87 so với hàng xóm −0.19..−0.33.

Bản sửa 1 — `mat_lech_khung_ev` (0 = tắt; đề xuất 0.5). Hàm
`sua_mat_lech_khung()`. Hàng xóm = cùng cảnh + cùng thân máy + cùng khẩu/tốc/ISO +
cùng bố cục (`scene_sig` cách ≤ 0.10). Khung ≤ 0.25 EV so với hàng xóm mà mặt
lệch > 0.5 EV → mặt suy từ khung + khoảng "mặt − khung" của hàng xóm. Trên TEST:
đúng 3 tấm đổi (09826 −0.87→−0.18, 09838 +0.45→−0.04, 09817 −0.21→0.00),
0 tấm khác xê dịch.
Hai phương án đã thử và BỎ, đừng thử lại: "cùng thông số máy thì cùng Exposure"
(chụp manual thì đèn sân khấu đổi mà thông số không đổi — cảnh 1 bị san về một
số trong khi khung trải −0.81..−2.99); và "chỉ so khoảng mặt−khung, không xét bố
cục" (bắt nhầm 12 tấm, đẩy NDT09869 xuống −0.45 trong khi NDT09870 y hệt khung
đứng ở +0.45 — tự tạo ra đúng bệnh cần chữa).

Bản sửa 2 — `trong_ngoai_min_shots` (1 = tắt; đề xuất 3). Hàm
`lam_min_trong_ngoai()`. Nhãn ngày/đèn (EV100 so với 8.5) nhảy MỘT tấm vì đổi tốc
1/160→1/200 thì trước đây mở cảnh 1 ảnh (không được san phẳng) và lấy màu da
đích của nhóm kia. Không phải nguyên nhân của NDT09826, nhưng là lỗ hổng thật.
Kèm: nhãn `scene_cut` giờ ghi đúng `doi-trong-ngoai` (trước bị ghi đè thành
`boi-canh`).

Cổng: `KIEM_CONG_SUA_CANH.bat` (mặc định G:\1308; phải bấm Phân tích buổi đó
trước để có bản xuất catalog mới). Đạt thì `kiem_gu.py ... --ghi-gu`.
Bài kiểm: `test_mat_lech_khung.py`, `test_tach_canh.py` (mục 19, 20) — đã thử ngược.
Buổi TEST sân khấu: EV100 8.9–9.6 nên bị xếp "ánh sáng ngày" dù là đèn — chọn
"Đèn" cho buổi sân khấu.

## Bản chụp "đáp án" của một buổi đã sửa tay (29/9)

`LUU_BO_DA_SUA.bat <thư mục buổi>` → plugin (`ChupCore.lua`, CHỈ ĐỌC) ghi
`_autotone_da_sua_<ngày giờ>.tsv` vào chính thư mục ảnh: mọi ảnh (kể cả 1 sao),
TOÀN BỘ `getDevelopSettings()` dạng JSON. Không bao giờ tự xoá — khác
`export_*.tsv` (plugin chỉ giữ 30 bản mới nhất, xem phần "Dùng lại một buổi").
Đọc bằng `xem_ban_chup.doc_ban_chup()`; đừng viết cách đọc thứ hai.

BẪY khi chạy lại tool để so với bản đã sửa:
- **Đừng bấm "Đẩy vào Lightroom"** — plugin đang bật tự áp, nó sẽ ghi đè lên
  chính bộ đã sửa. Chỉ cần Phân tích + Xuất CSV.
- `bo_qua_nguoi_sua` (mặc định BẬT) loại mọi ảnh có Exposure khác lần tool ghi
  — tức gần như cả bộ đã sửa tay. Công cụ so sánh phải tắt nó (như kiem_gu.py).
- Bản 2609 lần tool ghi: `jobs/apply_20260927_003227_2609.done` (3811 ảnh).

## Điểm lấy nét (AF) — lỗi xoay, đã vá 29/9

Sony ghi `FocusLocation` (MakerNote 0x2027) theo toạ độ CẢM BIẾN, luôn là khung
ngang. Ảnh dọc được xoay bằng `apply_orientation()` nhưng điểm AF KHÔNG xoay theo
→ rơi sai chỗ, trúng mặt người ngoài lề thì người đó thành "chủ thể theo AF" và
mọi mặt khác bị bỏ. Người dùng thấy qua "Vì sao tôi sửa" bộ 2609: 16 ảnh ghi
"đo không đúng điểm bắt nét", 15/16 là ảnh dọc (orientation 8); tấm
ngang còn lại (SAY06504) là AF rơi ở cổ — xem luật af_gan_mat bên dưới.
Vá: `af_theo_huong()`, LUÔN BẬT (sửa toạ độ, không phải tham số). Mẫu 51 ảnh
người dùng đã sửa của 2609: kéo lại gần 18, đẩy ra xa 7, sai trung bình
0.452 → 0.326 EV. Kiểm: `test_af_xoay.py` (chấm pixel rồi xoay ảnh thật).
Cẩn thận khi thử ngược: bản phá và bản đúng CÙNG kích thước file thì Python
dùng lại `.pyc` cũ — chạy `python -B`, xoá `__pycache__`.

Luật đi kèm, **ĐÃ TRƯỢT CỔNG — BỎ**: `af_gan_mat` (đề xuất 1.0) — AF rơi ở cổ / cổ áo
/ tóc sau gáy mà không trúng ô mặt nào thì lấy mặt gần nhất nếu cách mép ô mặt
≤ 1 lần cạnh ô. Mẫu 51 ảnh: thêm 6 ảnh dùng luật, tổng 23 gần / 6 xa, sai
0.281 EV. Riêng SAY06560 xấu đi (cô dâu quay nghiêng, mặt tối hơn, bị kéo lên
+0.50 trong khi người dùng chọn −0.29). Cổng: `KIEM_CONG_AF.bat` (G:\2609).

Chưa làm: ảnh Nikon (HIU_*.NEF) chưa đọc điểm AF — lùi về đoán theo nội dung.
Sheet "Vì sao tôi sửa" giờ vẽ vòng đỏ ở điểm AF (`thu_gu.ve_khung`).

### Kết quả cổng 29/9 (G:\2609, 3811 ảnh, bản xuất 14:39)
`af_gan_mat` = 1.0: cổng A ĐẠT (693 ảnh, gần 28 / xa 11, 0.211 → 0.209 EV) nhưng
cổng B TRƯỢT: 64/3118 ảnh đã duyệt xê dịch quá 0.30 EV = **2.05%** (cho phép dưới
2%) — trung vị 0.83, lớn nhất 2.03 EV, 44 ảnh bị kéo TỐI (say07576 +1.73 → −0.30).
Không nới cổng. Để `af_gan_mat` = 0, giữ mã và số đo ở đây để không ai thử lại mà
không có bằng chứng mới.

Cổng cho chính bản sửa XOAY (đã bật trước khi có cổng — sai quy trình, ghi nhận)
chạy bằng `kiem_gu.py --goc goc_af_cu.json --de-xuat de_xuat_af_xoay.json`. `--goc`
mới thêm: đặt lượt gốc về hành vi cũ để đo một thứ đã bật.
**Kết quả (29/9, 3811 ảnh): CẢ HAI CỔNG ĐẠT.** A: 693 ảnh, gần 142 / xa 73, sai
0.243 → 0.211 EV (nhóm "khác" = "đo không đúng điểm bắt nét": 0.793 → 0.435).
B: 13/3118 = 0.42%. Giữ BẬT.

## Nikon (29/9) — `af_nikon`, ĐÃ BẬT (người dùng duyệt tận mắt 39 ảnh)
`_af_nikon()` đọc MakerNote Nikon (TIFF riêng tại +10, thứ tự byte riêng), khối
0x00B7 AFInfo2 bản 0300/0301: tâm + kích thước VÙNG AF. Đối chiếu ExifTool trên 9
NEF thật của 2609 (NIKON Z 6_2, bản 0301, chế độ Wide-area S): khớp từng số.
Wide-area chọn nét ở đâu đó TRONG vùng, nên mặt nào CHẠM vùng là chủ thể
(`af_hop`), không đòi trúng tâm. Mẫu 9 ảnh: HIU_4204 cũ đo BÁNH XE Ô TÔ là mặt
(−2.35), bật lên đo đúng người (−0.99).
Bản 0100 (dòng D) và 0400 (Z8/Z9/Z6III) CHƯA có file thật nên KHÔNG đọc — ghi
`af_nikon_ban` rồi lùi về đoán. Canon: chưa có file nào để đối chiếu, chưa làm.

### Cổng Nikon (29/9): ĐẠT trên giấy, KHÔNG BẬT — vì mẫu số bị pha loãng
Chạy `kiem_gu --de-xuat de_xuat_af_nikon.json` trên 2609: A đạt (gần 2 / xa 0),
B 39/3118 = 1.25% → "CẢ HAI CỔNG ĐẠT". Nhưng thay đổi CHỈ chạm ảnh Nikon:
  - 292 ảnh Nikon, 285 đã duyệt, chỉ 7 có đích đúng → cổng A gần như không đo gì.
  - Trong 285 ảnh Nikon đã duyệt: 159 bị đụng tới, **39 xê dịch quá 0.30 EV =
    13.7%** (27 tối đi, 12 sáng lên; điển hình +0.45 → −0.40).
2800 ảnh Sony không đổi đã kéo tỉ lệ xuống 1.25%. Đây là CÙNG loại lỗi thống kê
đã ghi ở phần tách cảnh — con số đúng nhưng mẫu số sai. Không nới, không siết cổng
sau khi xem kết quả; chỉ không coi 1.25% là bằng chứng. Nhìn ảnh thì mặt Nikon AF
chọn hợp lý hơn (HIU_4150 cũ đo −2.04, mới đo đúng mặt −0.87), nhưng người dùng
đã duyệt +0.45 ở những ảnh đó. Cần người dùng nhìn tận mắt 39 ảnh rồi mới quyết.
TODO cho cổng: kiem_gu nên tính cổng B trên đúng những ảnh đề xuất CÓ THỂ chạm tới.

**Chốt 29/9:** người dùng xem `gu/2609/so_sanh_nikon_2609.pdf` (39 ảnh Nikon đã duyệt
bị xê dịch > 0.30 EV, cũ vs mới, có khung mặt + vùng AF) và kết luận: điểm bắt nét
chuẩn, ánh sáng bản mới ổn. → `af_nikon` = True trong DEFAULTS.

## Năm phần học từ 2 bản quay (2/10) — cổng 3/10; BẬT 2 mảnh, còn lại TẮT

**ĐÃ BẬT 3/10 trong DEFAULTS** (user xem `Claude outputs\do\so_sanh_ung_vien.pdf`
— 53 cặp ảnh trước/sau, dựng bằng `so_sanh_ung_vien.py` — và kết luận "đều oke"):
- `khung_sang_pct` = 12 (M3a: khung cháy ≥ 12% thì trần da 210 thay cho 232).
  KHÔNG kèm `phanh_da_hai_chieu` (vẫn tắt).
- `wb_tint_theo_may` = {"NIKON": -5} (M2b). Kèm sửa thứ tự: lệch Tint giờ cộng
  SAU san phẳng màu (`_tint_theo_may()`, cuối `decide()`). Trước đó san phẳng
  đưa cả cảnh về trung vị nên lệch đi theo đa số: TrainTool 12 ảnh SONY bị −5,
  7 ảnh Nikon mất −5. Sau khi sửa: đúng 155/155 Nikon −5, 1347 Sony 0; cổng B WB
  0/359 (trước 12/359).
Mọi khoá còn lại của năm phần vẫn TẮT. `test_2ban_quay.py` có mục `kiem_mac_dinh`
canh đúng hai mảnh này bật, không hơn không kém (thử ngược 18 lần, lần nào cũng đỏ).
Bật xong thì phải đóng/mở lại AutoTone để giao diện nạp DEFAULTS mới.

Buổi G:\TrainTool (cưới, 1502 ảnh, 5 thân máy). User quay 2 bản sửa tay có lời
giải thích — ghi chú `Claude outputs\TrainTool\GHI_CHU_HOC_2_BAN_QUAY.md`.
Năm phần nằm trong `autotone.py`, mỗi phần một nhóm khoá DEFAULTS, mặc định TẮT:
M1 `canh_ev100` (một ánh sáng một kết quả, `do_mat_theo_anh_sang`), M2 WB theo
máy (`wb_theo_may_pull`, `wb_tint_theo_may`, `wb_san_theo_may`,
`da_vang_lech_ngoai`; đọc nhiệt độ WB của máy trong MakerNote Sony 0xb021 /
Nikon 0x004F), M3 khung cháy (`khung_sang_pct` + `khung_sang_tran_da`,
`phanh_da_hai_chieu`), M4 `bu_exp_theo_may`, M5 `hl_ao_trang_max`.
Bài kiểm `test_2ban_quay.py` (thử ngược 15 lần, lần nào cũng đỏ). Mặc định thì
ra y hệt bản cũ (so 75/75 ảnh thật).

Cổng `kiem_2ban_quay.py`: chạy plan() thật trên số đo của `DO_BUOI.bat`
(`Claude outputs\do\<buổi>\do_<buổi>.json.gz` — đo MỘT lần, plan() chạy bao
nhiêu lượt cũng được, ~1 phút cho 2 buổi). Đáp án = bản chụp catalog so với lần
tool đẩy, tách riêng Exposure / Temp / Tint / HL. BẪY: ô "max EV kéo sáng" của
GUI không được lưu — dò ngược từ lần đẩy (TrainTool hôm đó để 3.0: khớp
1502/1502; để 1.0 chỉ 1437). G:\1308 không còn trên đĩa lẫn trong catalog.

Kết quả (TrainTool = TRONG mẫu, 2609 = NGOÀI mẫu, 2309 ảnh còn trên đĩa):

| Phần | TrainTool | 2609 |
|---|---|---|
| M1 canh_ev100 0.5 | A 110/72, B 6.34% — TRƯỢT | A 194/118 (0.196→0.176), B 14.77% — TRƯỢT |
| M2 cả gói | Temp A 84/117 — TRƯỢT | Temp 114/157, B 6.17% — TRƯỢT |
| ↳ M2a kéo về nhiệt độ máy | Temp 79/122 | Temp 107/164 — hướng SAI ở cả hai |
| ↳ M2b Tint Nikon −5 | Tint 57/0 — QUA | không ảnh Nikon nào bị sửa Tint (137 ảnh) |
| ↳ M2c san WB theo máy | Temp 6/31 | Temp 42/0, Tint 0/5 |
| ↳ M2d da vàng dưới đèn | Temp 15/47 | Temp 0/29 |
| M3 cả gói (có hai chiều) | A 49/25, B 6.34% — TRƯỢT | A 49/53 — TRƯỢT |
| ↳ M3a chỉ hạ trần 210 | A 43/22, B 2.82% (12 ảnh) — TRƯỢT sát | A 17/2, B 0.39% — QUA |
| M4 Nikon +0.24 (học trên TrainTool) | A 10/15 — TRƯỢT | A 6/11 — TRƯỢT |
| M5 HL áo trắng 65 | A 42/22, B 26.1% — TRƯỢT | A 18/0, B 12.99% — TRƯỢT |

Đã học được, đừng thử lại không có bằng chứng mới:
- M1 làm loạt cùng ánh sáng đều nhau thật (2609: loạt lệch >0.15 EV 41 → 25)
  nhưng gộp cả ảnh KHÁC người / khác bố cục trong cùng ánh sáng — mà ở đó user
  CHẤP NHẬN Exposure khác nhau (DSC08742–48 cùng thông số, user giữ
  +0.06/−0.46/−0.21…). Ảnh đã duyệt bị dời: phép đo mặt đổi trung vị 0.43–0.52
  EV, chỉ 35–42% có hàng xóm bố cục ≤ 0.05. Ảnh sửa được kéo GẦN: mặt đổi
  0.07–0.08, 81–84% có hàng xóm ≤ 0.05. Hướng tiếp: chỉ đồng thuận trong loạt
  cùng bố cục, chặn mức dời — phải kiểm trên buổi MỚI (TrainTool, 2609 đã dùng).
- Nikon: preview sáng/tương phản hơn Lightroom nên CẢ phép đo mặt LẪN p95 da
  lệch. M4 chỉ bù phép đo mặt → phanh da (p95 248–251 trên preview) chặn lại
  ngay (HIU_4051/4055 không nhúc nhích). Muốn bù phải bù cả p95.
- Kéo Temp về nhiệt độ WB của máy (hệ số 0.35 như nhánh sidecar) làm Temp tệ
  hơn ở cả hai buổi. Chưa biết vì sao — đừng bật lại bằng hệ số khác khi chưa đo.
- M5: user để nguyên Highlights ở phần lớn ảnh chủ thể sáng; nâng trần cho MỌI
  ảnh có vùng chủ thể ≥242 chiếm ≥15% là quá rộng.
- Phanh da hai chiều ở trần thường 232 kéo tối cả ảnh da 244–249 user vẫn giữ
  Exposure 0 (SAY06085–06110) → đã giới hạn chỉ trong khung cháy.
- Da cháy hẳn trên preview (p95 ≥ 250, DSC08688 da_chay_frac 20%, user −1.32
  vs tool −0.65) chưa phần nào xử lý — p95 bão hoà không nói được cháy bao sâu.

## Khung mặt ảo to (3/10) — `mat_ao_to_pct` 15 / `mat_ao_diem` 0.6, BẬT

HIU02258 (cận cổ tay, không có mặt): YuNet báo "mặt" điểm 0,50 chiếm 40% khung
→ tool kéo −1,31 trong khi HIU02257 ngay cạnh 0,00. `bo_mat_ao_to()` trong
`measure()` bỏ khung VỪA điểm < 0,6 VỪA > 15% khung. TrainTool + 2609: 40.521
khung, 0 khung trúng cả hai điều kiện (cổng B 0%). Hiu (đo lại hai tấm có khung
trúng điều kiện): Exposure đổi đúng 1 ảnh (HIU02258 −1,31 → 0,00); HIU02612 bỏ
khung 21% nhưng vẫn còn mặt thật → không đổi. Hệ quả phụ: cảnh cận tay
HIU02255–58 mất mẫu da (cánh tay) nên WB lùi về độ ngả hồng cố định, Temp
4967 → 5370 (4 ảnh). Kiểm: `test_mat_ao_to.py`.

**BẪY ĐÃ MẮC 3/10:** bản sửa này tưởng đã chép sang máy Windows nhưng
`autotone.py` trên máy vẫn là bản CŨ (chép nhầm file trong outputs) — trong khi
`test_mat_ao_to.py` và `thu_gu.py` (gọi `measure(..., mat_ao_to_pct=...)`) đã
sang. Phát hiện khi đối chiếu số đo `DO_BUOI` của Hiu. Chép xong PHẢI kéo file
về lại và so (cmp / sha1) — "đã ghi" không có nghĩa là "đã ghi đúng file".
`do_buoi.py` giờ ghi `autotone_sha1` lúc NẠP (trước ghi mtime lúc kết thúc).
Mắc lần hai cùng ngày (09:50): commit LẦN THỨ HAI từ cùng một đường dẫn trong
`/mnt/user-data/outputs/` (CLAUDE.md) ghi lên máy nội dung CŨ với mtime MỚI — kéo
về so sha1 mới thấy. Mỗi lần commit dùng một tên file nguồn mới (vd `CLAUDE_0951.md`).

## Quy trình "preset bỏ trống WB và Tone" (3/10) — bước 1 + bước 2 đã làm

Người dùng đề xuất: import RAW → áp preset KHÔNG có nhóm White Balance và Basic
Tone (Exposure, Contrast, Highlights, Shadows, Whites, Blacks); AutoTone tự ghi
hai nhóm đó.

Vì sao đúng hướng — đo trên Hiu (1303 ảnh Sony A7IV, TẤT CẢ WB đặt tay 3500–5800K;
lần đẩy 06:55 tái hiện 1303/1303 với chế độ sáng "Đèn", max EV kéo tối/sáng 3.0):
tool giả định preview ≈ Lightroom ở 5250K của preset, nhưng ảnh sân khấu máy đặt
3600–4000K → preview đã ấm (da lệch −1,1 đến −2,3 stop), tool muốn kéo −1246K mà
bị trần `wb_temp_max` 1000K chặn ở 4250K → Lightroom render ẤM HƠN cả preview.
Ảnh máy đặt 3600K: Temp tool đẩy trung vị 4982K. WB để As Shot thì Lightroom
xuất phát đúng chỗ preview đứng.

**Bước 1 (đã làm, 3/10): chuyển quy trình mà KHÔNG đổi kết quả.**
- Plugin xuất thêm `WhiteBalance` (CHỮ), `Contrast2012`, `Whites2012`,
  `Blacks2012` — bảng trường dùng chung `Core.EXPORT_FIELDS` / `Core.exportCell`
  cho cả hai đường xuất (menu + app yêu cầu).
- `preset_chua_ap()` nhận ra TỪNG ẢNH: Contrast/Whites/Blacks có mặt và đều 0,
  Highlights/Shadows 0 → bỏ trống Tone; WhiteBalance có mặt và khác "Custom" → bỏ
  trống WB. Plugin cũ không xuất các cột đó → không bao giờ nhận nhầm.
- `nen_cho_anh()` phủ nền SAY: `nen_tone` (Contrast 5, HL/Sh mốc 16, Whites −25,
  Blacks −18 — TrainTool 1502/1502 ảnh user không đụng 3 thanh kia), `nen_wb`
  5250/+16. Job ghi thêm 3 cột Tone; WB LUÔN ghi (`wb_ep_ghi`) kể cả khi tool
  không đổi gì — không ghi thì ảnh ở lại As Shot.
- Mốc (`_autotone_baseline.tsv`) giữ thêm 4 cột; mốc cũ (preset đầy đủ) + catalog
  đang As Shot/Tone 0 → lấy catalog làm nền (ghi chú `moc-cu-khac-quy-trinh`).
- Sidecar: mốc `atn:` ghi theo nền, không theo As Shot.
- Plugin cũ + Highlights/Shadows 0 ở ≥ nửa buổi → `CANH_BAO_PLUGIN`, giao diện
  báo "Reload plugin". Cập nhật plugin xong PHẢI Reload trong Plug-in Manager.
- Kiểm: `test_preset_khong_wb_tone.py` (21 lần thử ngược, lần nào cũng đỏ),
  `kiem_xuat_thong_so.lua` (6 lần thử ngược). Quy trình cũ: TrainTool tái hiện
  1502/1502, Hiu 1303/1303 — không xê dịch một số nào.

**Bước 2 — ĐÃ LÀM chiều 3/10, xem mục "WB theo As Shot" ở cuối.** Ghi chú lúc
lên kế hoạch (giữ lại để hiểu vì sao làm như vậy): cần số As Shot THẬT từ Lightroom
cho ảnh đã có đáp án. `getDevelopSettings()` CÓ trả Temperature/Tint khi WB = As
Shot — mẫu đầu tiên (bản xuất 3/10 08:25): `G:\1005\SAY00004.ARW` WhiteBalance
"As Shot", Temperature 5000, Tint 16. Mới MỘT ảnh — lần xuất cả buổi theo quy
trình mới sẽ xác nhận. Lưu ý khi làm:
- Temp kelvin không đều: cùng một độ lệch màu, ở 3600K chỉ cần ~0,47 lần số K so
  với ở 5250K (mired). `wb_temp_gain` / `wb_temp_max` hiện chỉnh ở nền 5250.
- San phẳng màu đang san `temp_adj` (độ lệch). Nền As Shot khác nhau từng ảnh thì
  phải san GIÁ TRỊ TUYỆT ĐỐI, không thì kế thừa nguyên độ nhấp nháy của máy.
- Thang K của máy và của Adobe chưa chắc trùng nhau — chưa đo. Đã đo: TrainTool /
  2609 (ban ngày, máy đặt 4600–5600K) user chốt trung vị 4800–5300K bất kể máy
  đặt bao nhiêu. Đừng lấy K trong MakerNote thay cho As Shot khi chưa có số
  Lightroom để đối chiếu.

**Lần xuất cả buổi đầu tiên theo quy trình mới (3/10 09:44, G:\1005, 630 ảnh).**
Cả 630 ảnh WhiteBalance "As Shot", 5 thanh Tone = 0; tool đẩy 09:45 — áp 630/630,
kiểm chứng đủ, Contrast/Whites/Blacks = 5/−25/−18, WB ghi cả 630. NHƯNG:
- `getDevelopSettings()` chỉ trả Temperature/Tint As Shot cho ảnh Lightroom ĐÃ
  DỰNG: 49/630 lúc 09:44:19, 59/630 lúc 09:44:46 (tăng khi user lướt ảnh); 571
  ảnh để trống, `AsShotTemperature` trống cả 630. → Bước 2 KHÔNG trông được vào
  bản xuất cho mọi ảnh. Bộ số gặp: 4800/10 ×40, 5000/16 ×18, 5450/17 ×1 — đúng
  kiểu máy đặt Kelvin tay, nên có thể đối chiếu với K trong MakerNote của chính
  những ảnh đó (chưa làm: G:\1005 chưa nối vào phiên).
- So với catalog lúc 08:25 (G:\1005 khi đó đã qua tool một lần, WB Custom):
  Exposure lần này thấp hơn, trung vị −0.31 EV, 584/629 ảnh lệch > 0.05; Temp
  +50K, Tint +4. CHƯA rõ 08:25 là số tool đẩy hay user đã sửa tay, và tuỳ chọn
  giao diện lần trước (chế độ sáng, max EV) không được lưu — đừng coi là lỗi khi
  chưa tách được.
- Ba file lưu ở `Claude outputs\do\1005\` (bản xuất As Shot, job tool ghi, bản
  xuất 08:25) — plugin chỉ giữ 30 bản xuất và XOA_BAN_XUAT.bat xoá sạch jobs.

## Dùng lại một buổi đã chạy (3/10) — bản xuất theo THƯ MỤC

User báo: "dùng lại folder đã chạy qua tool thì catalog không nhận đủ ảnh hoặc
không nhận được catalog". Ảnh màn hình: G:\1009 (437 ảnh) "bản xuất chỉ khớp 0
ảnh", đang đọc `export_20261003_082531.tsv` = 630 ảnh **G:\1005** (Lightroom đang
mở 1005, lệnh xuất ở menu lấy theo vùng đang xem). Năm chỗ hỏng thật:
1. App đọc "bản xuất mới nhất" bất kể của buổi nào; plugin chỉ giữ MỘT file cho
   cả catalog → xuất buổi này là mất bản của buổi kia.
2. **Nút "Xoá dữ liệu cũ" chưa bao giờ chạy được** (không rõ từ bao giờ): gọi
   `at.ban_xuat_moi_nhat()` — hàm không tồn tại → AttributeError ở dòng đầu,
   Tkinter nuốt lỗi, không hỏi, không xoá gì. Nút "Đọc từ Lightroom" cũng gọi
   `self.refresh_scan()` không tồn tại (văng ở dòng cuối).
3. Xoá dữ liệu (khi chạy được) xoá bản xuất của MỌI buổi, rồi bảo user vào
   Lightroom chọn thư mục, Ctrl+A, chạy menu — sai một bước là xuất nhầm/thiếu.
4. Ảnh không có trong bản xuất VẪN bị đẩy vào Lightroom với nền 0 (Highlights
   tính từ 0 thay vì 16, Exposure tính từ 0) — giao diện lại bảo "sẽ bị bỏ qua".
   Gồm cả ảnh 1 sao (plugin bỏ khi xuất theo quy ước).
5. `attach_catalog_settings` khoá bằng `normcase` — trên macOS không viết thường
   nên cả buổi khớp 0 (bản xuất khoá bằng `khoa_duong_dan`).

Đã sửa:
- `at.ban_xuat_cho_thu_muc()` — bản MỚI NHẤT CÓ ẢNH CỦA THƯ MỤC (nhớ kết quả theo
  mtime+size); `export_stamp(thu_muc=)` không coi bản xuất buổi khác là "đã trả lời".
- Plugin giữ 30 bản xuất mới nhất (`Core.donBanXuat`), không xoá bản buổi khác;
  mỗi lần app nhờ xuất thì ghi `jobs/ketqua_xuat.txt` (thu_muc, so_anh, bo_sao,
  file, cach, loi) — `at.ket_qua_xuat()`. Thư mục không có trong catalog →
  `loi=khong-co-trong-catalog`, app dừng chờ ngay và nói đúng bệnh.
- Chọn thư mục (nguồn catalog) là app TỰ nhờ plugin xuất đúng thư mục
  (`_xin_xuat_nen`); dòng trạng thái tách: khớp / ảnh 1 sao (bình thường) / chưa
  import (Synchronize Folder) / đang chờ Lightroom.
- Nút Xoá dữ liệu: chỉ xoá bản xuất + ketqua của buổi này, rồi tự nhờ xuất lại.
  **GIỮ mốc gốc** (`xoa_moc=False`): nút chạy được rồi thì lộ ra — ảnh trong
  Lightroom còn mang số tool ghi lần trước (user chỉ muốn chạy lại, không Reset)
  mà xoá mốc thì lần sau lấy số cũ làm nền và CỘNG THÊM: Exposure +0.71 → +1.42
  (preview trong RAW không đổi theo Lightroom nên delta lần hai y hệt lần đầu).
  Giữ mốc thì cả hai trường hợp (đã Reset / chưa Reset) đều ra đúng. Chỉ cần
  `xoa_moc=True` khi đổi SỐ của chính preset (vd Highlights 16 → 10).
- `ngoai_xuat`: ảnh không có trong bản xuất lẫn mốc thì KHÔNG vào job; cả buổi
  ngoài bản xuất thì nút ghi từ chối và giải thích.
- Kiểm: `test_dung_lai_buoi.py` (22 lần thử ngược), `kiem_tham_chieu.py` (bắt
  đúng hai tên sai trên bản GUI cũ), `kiem_ket_qua_xuat.lua` (7 lần thử ngược),
  `kiem_ban_xuat.py` sửa theo hành vi mới. Quy trình cũ: TrainTool 1502/1502,
  Hiu 1303/1303 — không xê dịch.
Lưu ý: sau khi Xoá, mọi ảnh (kể cả ảnh user đã sửa tay) được tính lại từ mốc và
ghi đè — đúng mục đích "chạy lại từ đầu", hộp thoại có nói.

**Cùng ngày, hai chuyện nữa (09:00–09:10):**
- "Nhờ Lightroom đọc thư mục" chờ mãi trong khi xuất tay ở menu thì nhanh: vòng
  lặp nền của plugin KHÔNG chạy từ 08:25 (plugin.log im 39 phút). User Reload lúc
  09:04:49 → 09:04:50 xuất xong 326 ảnh. Đường nhờ xuất mất ~1 giây KHI vòng lặp
  sống. Thêm: `Core.ghiNhip` (jobs/plugin_song.txt, ≤ 10 giây/lần) + `at.plugin_nhip()`
  — yêu cầu nằm im > 6 giây mà nhịp cũ > 30 giây (hoặc chưa có nhịp) thì app báo
  NGAY "Plugin trong Lightroom KHÔNG chạy — Reload"; POLL 5 → 2 giây.
  Lệnh xuất ở menu user bấm lúc 09:04:51 lại xuất G:\1005 (Lightroom đang xem 1005)
  — đừng khuyên xuất tay bằng menu nữa, đường nhờ xuất theo thư mục là đúng.
- G:\1009: Lightroom chỉ có 326/437 ảnh. 111 ảnh thiếu ĐÚNG là 111 ảnh DSC có bản
  sao y hệt (cùng kích thước, cùng mtime) ở **G:\Test1009** — thư mục thử user
  tạo hôm 11/9, đã nằm trong catalog. Lúc Import G:\1009, Lightroom bỏ chúng vì
  "Don't Import Suspected Duplicates". Đây là dạng hỏng ĐIỂN HÌNH của "dùng lại
  một buổi": sao chép ảnh sang thư mục mới để chạy lại. Nút "Ảnh nào thiếu?"
  (`_xem_anh_thieu`) liệt kê tên ảnh thiếu + nói nguyên nhân này + cách sửa
  (Synchronize Folder, bỏ tick Don't Import Suspected Duplicates, hoặc Remove thư
  mục bản sao khỏi catalog).
- **Chốt "bản xuất cũ hơn lần ghi" phải theo THƯ MỤC (09:40).** Hỏng do chính
  bản sửa "đọc theo thư mục" ở trên: `ban_xuat_cu_hon_lan_ghi` cũ lấy mtime lớn
  nhất của MỌI `export_*.tsv` (đúng khi app còn đọc "file mới nhất"). Buổi X dùng
  bản xuất chụp TRƯỚC lần ghi, chỉ cần một buổi Y vừa xuất sau lần ghi là chốt im
  → `danh_dau_nguoi_sua` bỏ cả buổi X (bệnh 2705). Giờ chốt so đúng file đang
  dùng: giao diện truyền `ban_xuat=self._file_xuat()` vào `at.plan()`; không
  truyền thì lấy bản phủ ĐÚNG thư mục trước bản gồm thư mục con (nhầm về phía báo
  oan). Kiểm: `kiem_moc_va_xuat.py` (6 lần thử ngược), `test_dung_lai_buoi.py`
  mục 7 (plan() thật — chốt cũ bỏ 6/6 ảnh). TrainTool: CSV từng ảnh trước/sau
  bản sửa giống hệt.
- `XOA_BAN_XUAT.bat` (user xin "xoá hết catalog đã export để test lại"): xoá
  `export_*.tsv`, `ketqua_xuat.txt`, `request_export.txt` trong jobs. KHÔNG đụng
  mốc, `apply_*.done`, `verify_*`. Tool không tự xoá được file trên máy user
  (cầu nối chỉ ghi) — việc xoá đi qua file .bat cho user bấm.
- Tái hiện TrainTool giờ khớp **1345/1502** với lần đẩy 2/10, không phải 1502:
  157 ảnh chênh ĐÚNG là `khung_sang_pct` = 12 (bật 3/10, user đã duyệt). Tắt nó
  thì về 1502/1502. Đừng tưởng là hỏng.

## Buổi sự kiện G:\1005 (3/10) — "Loại buổi" + bù sáng cả buổi

Sự kiện doanh nghiệp (sân khấu LED + tiệc), 630 ảnh, hai máy: SAY = ILCE-7M5
(439), DSC = ILCE-7M4 (191). Quy trình preset mới. Lần đẩy 09:45 tái hiện
**629/630** bằng plan() thật với chế độ sáng "Đèn" + max EV kéo sáng 3.0. Số đo:
`Claude outputs\do\1005\do_1005.json.gz` (DO_BUOI 10:02, sha1 cdaa0473); kèm bản
xuất As Shot, job tool ghi, bản xuất 08:25. Bộ tái hiện: `scratchpad r1005/chung.py`
(gọi `kiem_2ban_quay.chay`).

User xem tận mắt (quay màn hình 09:46–09:51): "ảnh hơi tối, cần tăng thêm một
chút sáng thôi"; SAY00023 da ám vàng; DSC00004 da ám tím và tối.
38 ảnh user sửa = **10 quyết định** (sync theo nhóm), 9 TĂNG / 1 giảm:

| nhóm | tool | user | cơ chế của tool |
|---|---|---|---|
| DSC00004 | +0.70 | +1.14 | phanh da sắp cháy / chủ thể cháy |
| DSC00006–08 | +0.58..+0.77 | +0.97 | như trên |
| DSC00009–14 (LED, khung cháy ~41%) | +0.11..+0.20 | +0.45 | phanh + M3a |
| DSC00015–21 (chân dung tối, nền −6.5 EV) | +0.11..+0.72 | +1.57 | mặt đã ~đích |
| DSC00071–73 | −0.50..−0.55 | −0.21 | dìm về đích |
| DSC00280–282 | −0.49..−0.51 | −0.31 | dìm về đích |
| DSC00283–288 (LED ~50%) | −0.18..−0.31 | 0.00 | dìm về đích |
| SAY00023–24 | −0.32/−0.36 | −0.53 (+ Temp 5118→4280) | dìm về đích |
| SAY00289–297 | −0.27..+0.24 | +0.20 | dìm về đích |
| SAY00398 | −0.37 | 0.00 (+ Tint 20→26) | dìm về đích |

Trung vị theo quyết định **+0.30 EV**. Tool để mặt đúng đích (delta trung vị 0.00).

Giả thuyết ĐÃ BÁC — đừng thử lại:
- Preset mới đổi nền Exposure: không, nền 0 cả 630 ảnh, như preset cũ.
- M3a (`khung_sang_pct`) làm tối cả buổi: tắt nó chỉ đổi 119/630 ảnh, +0.12 trung vị.
- "Bản 08:25 sáng hơn là chuẩn": bản đó do code CŨ ghi (mọi cấu hình hiện tại
  chỉ tái hiện ≤ 35/630) — không dùng làm mốc so.
- Đổi `face_target_ev`: 287/630 ảnh do PHANH chống cháy quyết định chứ không phải
  mốc — mốc −1.19 → −0.95 thì nửa buổi đứng yên (dịch trung vị +0.07). Và buổi
  CƯỚI user lại HẠ: TrainTool 219 ảnh sửa trung vị −0.09, 2609 688 ảnh −0.13
  (riêng ảnh đèn −0.14 / −0.10). Đổi mốc chung là làm hỏng hai buổi đã duyệt.

Sửa: `bu_sang_ca_buoi` (DEFAULTS 0) cộng vào delta CUỐI, sau phanh và san phẳng,
bỏ ảnh không mặt, tôn trần max_ev_up/max_ev, cờ `bu-sang+0.30`. Giao diện: khối
"Loại buổi" ở CỘT 3 (cột 1 hết chỗ — đặt ở đó thì 1900x1200 phải cuộn 29 px):
Cưới 0 / Sự kiện `bu_sang_su_kien` = +0.30, ô số sửa tay được. Trên 1005: 38 ảnh
sai trung bình 0.45 → 0.28 EV (bỏ nhóm chân dung tối: 0.26 → 0.12), 9/10 quyết
định gần hơn, 607 ảnh +0.30, 23 ảnh không mặt đứng yên. Mặc định 0: TrainTool CSV
từng ảnh giống hệt, 1005 vẫn 629/630. **+0.30 đo TRONG MẪU — cần thêm một buổi sự
kiện để chốt.** Kiểm: `test_bu_sang.py` (8 lần thử ngược, lần nào cũng đỏ).

Còn treo:
- DSC00015–21: ảnh low-key (mặt −1.3..−1.6, khung −6.2..−6.9 EV), user nâng cả
  khung +1.57. Chưa luật nào xử lý; một quyết định, đừng vặn riêng cho nó.
- Màu hai máy: 12/56 cảnh gộp cả hai máy (243 ảnh) → cùng một WB. User kéo ngược
  chiều: SAY00023/24 −838K (vàng), DSC00004 +390K (tím). `wb_san_theo_may` (M2c)
  đưa cả hai về phía user (4866 / 5619, user 4280 / 5508) — mới 2 quyết định và
  M2c từng trượt cổng TrainTool → chờ user sửa xong màu cả buổi rồi gác cổng.
- As Shot Lightroom vs K trong MakerNote: ILCE-7M4 4800 → 4800 (khớp); ILCE-7M5
  5200 → 5000, 5800 → 5450 (LỆCH). Thang K của máy khác Adobe theo từng đời máy
  → bước 2 không được lấy thẳng K MakerNote làm As Shot. (Đã giải: bảng
  `wb_asshot_lech_mired` + học từ chính buổi — mục "WB theo As Shot".)
- Đọc catalog không phiền user: ghi `jobs\request_export.txt` (dòng 1 thư mục,
  dòng 2 `skip_rating=1`) — plugin xuất trong 2 giây. G:\HPC 25nam\Hiu đã không
  còn trong catalog (10:10).

## Cùng khung + cùng thông số -> cùng một mức (3/10) — `dong_bo_loat`, BẬT

User (12:10, buổi cưới G:\2709, Nikon Z 1/800 f/2.2 ISO 125): "hai bức cùng khung
cảnh + cùng thông số mà ra hai mức sáng khác nhau — phải giải quyết DỨT ĐIỂM".
Hai ca: SUB_6485/87/88 −0.40 mà **SUB_6486 +0.45** (phép đo mặt −4.25 EV, hàng xóm
−0.79 — đo nhầm mặt); SUB_6652–6665 (mẹ + cô dâu) nhảy −0.47..+0.45 từng tấm,
phép đo mặt −0.89..−2.76 vì nhảy giữa hai người và người nền.
Lần đẩy 11:47 tái hiện 1074/1074 (chế độ "Trộn", max EV kéo sáng 3.0). Số đo:
`Claude outputs\do\2709\` (DO_BUOI 12:20).

VÌ SAO san phẳng cảnh không chữa được: nó đưa mọi tấm về cùng "mặt SAU chỉnh",
nên phép đo mặt lệch bao nhiêu thì Exposure nhảy bấy nhiêu. Mục 1 (`canh_ev100`)
và `sua_mat_lech_khung` sửa PHÉP ĐO, nhưng phanh chống cháy vẫn quyết từng tấm.

Luật: `chia_loat()` + `dong_bo_loat()` ở CUỐI decide() (sau san phẳng, trước Tint
theo máy và bù sáng). Loạt = cùng máy, cùng cảnh, cùng khẩu/tốc/ISO, liền nhau
≤ 60 giây, chữ ký khung lệch ≤ 0.10 và độ sáng khung lệch ≤ 0.25 EV so với
**tấm ĐẦU loạt** (so tấm liền trước thì đèn hạ dần nối thành chuỗi). Cả loạt nhận
TRUNG VỊ delta/HL/Shadows/WB/Curve của các tấm có mặt; tấm không mặt trong loạt
cũng theo. Ngưỡng 0.10 / 0.25 lấy lại của `sua_mat_lech_khung`, đặt trước khi đo.

Cổng (`cong_loat.py` trong scratchpad, gọi kiem_2ban_quay):
| | A (ảnh user sửa) | B (ảnh duyệt dời >0.30) |
|---|---|---|
| TrainTool | gần 158 / xa 108, sai 0.186 → 0.177 | 1.41% — ĐẠT |
| 2609 | gần 218 / xa 169, sai 0.193 → 0.189 | **7.10% — TRƯỢT** |
B trượt vì "ảnh đã duyệt" của 2609 chứa 94 loạt user CHẤP NHẬN THỤ ĐỘNG lệch
> 0.3 EV (không sửa tấm nào trong loạt) — đúng loại lệch user nay nói không chấp
nhận. Loạt user CÓ Ý để lệch > 0.3 (có sửa tay mà vẫn để lệch) bị luật ép: 2609
**0**, TrainTool **1** (7 ảnh). KHÔNG nới ngưỡng B; ghi lại, user quyết bật.
Đã quét thêm (trong mẫu, chỉ để hiểu, KHÔNG dùng chọn ngưỡng): bố cục 0.05 làm
B 2609 còn 4.34% nhưng phủ ít hơn 20% ảnh; 0.15/0.20 phủ nhiều hơn, B 9.4–9.8%;
thêm `mat_lech_khung_ev` 0.5 không đổi cổng đáng kể.
Kết quả 2709: 245 loạt / 894 ảnh; loạt lệch > 0.15 EV: 62 → 0; ảnh dời > 0.30: 39.
SUB_6485–88: −0.40 cả bốn. SUB_6652–6665: hai khung (chữ ký lệch ~0.2) → +0.03
(8 tấm) và −0.11 (6 tấm). 1005: 38 ảnh user sửa gần 7 / xa 6 (trung tính).
Kiểm: `test_dong_bo_loat.py` (11 lần thử ngược, lần nào cũng đỏ);
`test_mat_lech_khung.py` giờ tự tắt luật loạt (bài đó kiểm riêng phép đo).
Tái hiện lần đẩy CŨ giảm (2709 1074 → 524 khớp Exposure ±0.005) — đúng, luật đổi số.
Giao diện: ô "Cùng khung + cùng thông số → cùng một mức" (cột 3, mặc định BẬT).
Còn lại: hai khung gần nhau của cùng nhóm người (chữ ký ~0.2) vẫn có thể lệch nhẹ;
đo nhầm mặt (−4.25, −4.87) vẫn làm hỏng tấm đứng MỘT MÌNH — chưa sửa.

## WB theo As Shot (3/10 chiều) — bước 2 của quy trình preset bỏ trống WB, BẬT

User (15:12, G:\2709 cưới, chế độ "Trộn"): "ảnh ngoài trời bị kéo về ngưỡng bị
xanh". Ảnh mẫu SUB_6702 (Z5_2, cô dâu trùm voan ngoài trời). Đọc catalog 15:26:
user tự kéo SUB_6692 5359 → 5771, SUB_6698–6713 5359 → **5859** (Tint giữ 8,
Exposure cả nhóm về 0.00), DSC_9614 5186 → 4936 (lạnh đi). 2709: Nikon đặt **K TAY**
(4760/5260/5560/5880/6250/6670 — đúng các nấc K của Nikon, cùng một số cho hàng
trăm tấm liền), Sony đặt tay 5400–5800.

Gốc bệnh: ở quy trình preset bỏ trống WB, tool tính trên nền 5250 — bỏ qua WB
người chụp đã đặt. Z 8 đặt 6670K → tool ghi 5279K (ngày, trung vị).

Sửa (`uoc_asshot()` trong plan(), `_wb_theo_asshot()` ở CUỐI decide() — sau san
phẳng màu và đồng bộ loạt, trước Tint theo máy):
- As Shot của từng ảnh: số THẬT trong catalog (chỉ khi WhiteBalance "As Shot" —
  "Auto" cũng khác Custom nhưng số đó Lightroom tự tính), không có thì K trong
  MakerNote quy sang thang Adobe bằng `wb_asshot_lech_mired` (1e6/K_adobe −
  1e6/K_máy: 7M4 1.0, 7M5 9.5, Z 8 4.4, Nikon khác tạm lấy số Z 8 — hệ số WB R/B
  theo K của Z5_2/Z6_2/Z 8 trùng nhau). Buổi có ≥ 3 cặp (catalog, K máy) của một
  máy thì HỌC độ lệch từ chính buổi. Chỉ ảnh đang As Shot; preset đầy đủ thì
  không gán gì — quy trình cũ TrainTool 1502 / 2609 2309 ảnh lệch 0.
- `temp_adj += wb_asshot_pull × (As Shot trung vị theo (cảnh, máy) − 5250)` —
  hệ số 0.35 CÓ SẴN từ nhánh "kéo về AsShot" thời sidecar, không chỉnh. Áp cho
  MỌI ảnh đang As Shot của (cảnh, máy) đó, kể cả tấm không tự có số (Sony để Auto
  không ghi K; catalog chỉ trả As Shot cho tấm Lightroom đã dựng) — không thì
  trong một cảnh tấm user đã lướt qua bị kéo, tấm khác không.
- Hai chặn, đặt TRƯỚC khi chạy cổng: ảnh ngày chỉ kéo ẤM, ảnh đèn chỉ kéo LẠNH
  (`wb_asshot_theo_chieu` — đúng luật user nói "ngoài trời tăng K, không để xanh
  lạnh; trong nhà đèn vàng mới hạ K"); kéo dưới 50K thì bỏ (`wb_asshot_min_K`).
- Đường sidecar KHÔNG áp: ghi xong .xmp mang WB Custom, mốc atn chỉ giữ nền 5250
  → chạy lại mất As Shot (4716 → 5250). Đường catalog giữ As Shot trong MỐC.

Cổng (`kiem_2ban_quay.bao_cao_buoi` thật; TrainTool = bản xuất preset mới THẬT
112816, 2609 = giả lập WhiteBalance As Shot; script `wbas/cong_chinh.py`):
| | A (ảnh user sửa Temp) | B (WB, trừ Nikon) |
|---|---|---|
| TrainTool | gần 23 / xa 4, sai 414 → 390K (Z6_2 ngày 25/2) | 0% — ĐẠT |
| 2609 | 0 / 0 (không ảnh sửa nào đổi) | 0% — ĐẠT |
Ảnh Nikon user ĐỂ NGUYÊN cũng dời (cổng B không tính Nikon): TrainTool 89/103
ảnh ngày +219K (5376 → 5595; 27 ảnh user sửa thì user chốt 5605, tool mới 5659);
2609 75/125 +321K (5448 → 5769). Phải nói ra khi báo.
2709: 17/18 ảnh user sửa Temp lại gần (5359 → 5421 — user 5859/5771), DSC_9614
đứng yên; 776/1074 ảnh đổi, Z 8 ngày trung vị 5279 → 5714, Z5_2 5409 → 5519;
Exposure/Tint không đổi. 1005 ("Đèn", cả 630 ảnh đổi −88 / −158K): 9 ảnh user sửa
gần (DSC00015–21 5711 → 5553, user 5544; SAY00023/24), DSC00004 xa.
Phần còn lại của SUB_6698–6713 (user +500K, As Shot chỉ giải thích +63K) là gu
của cảnh đó — một cảnh, đừng suy ra cho cả buổi.
Lưu ở `Claude outputs\do\2709\`: bản xuất As Shot trước lần đẩy 11:47
(`asshot_export_…114747`), job tool ghi (`tool_ghi_apply_…114750_2709`), catalog
15:26 có các chỗ user sửa (`user_sua_export_…152656`).

ĐÃ THỬ, BỎ — đừng thử lại khi không có bằng chứng mới:
- Neo hẳn Temp vào As Shot (dịch theo màu da): 2709 18/18 gần, nhưng TrainTool B
  11.6%, 2609 A 99/160 + B 9.1%. Nikon Auto (TrainTool Z6_2, As Shot ~6200) user
  chốt 5605; Sony ban ngày user chốt 4800–5300 bất kể máy đặt. Hệ số 0.7 / 1.0
  (có hai chặn): TrainTool A trượt.
- Sàn "ảnh ngày không lạnh hơn As Shot": DSC_9614 (user 4936 < As Shot 5150),
  TrainTool A7M5 ngày 89 ảnh (user 4609 < 5300) đi ngược.
- Nhân mạnh phần WB theo màu da (×1.5–×3, cả quy trình cũ): TrainTool ×1.5 gần
  hơn nhưng 2609 tệ hơn; ×3 tệ cả hai. "Khớp vật lý" 70 mired/stop khớp 2 quyết
  định 2709 trong 20K là TRÙNG HỢP — đo từng ảnh thì không còn khớp.
- Kéo TRƯỚC san phẳng (như Mục 2a): cảnh trộn hai máy thì máy này ăn As Shot của
  máy kia (7M5 bị +168K thay vì +23K).
- Không hai chặn: TrainTool A 84/117, 2609 A 109/162 — toàn cú kéo Sony +17..+52K
  mắt không thấy mà cổng đếm. K máy thô (không quy thang): đúng y số Mục 2a
  (79/122, 107/164) → Mục 2a trượt vì 7M5 lệch thang ~300K.

Kiểm: `test_wb_asshot.py` (14 mục, 18 lần thử ngược — lần nào cũng đỏ, kể cả
"chạy lại lấy catalog thay mốc", "áp cả đường sidecar", "chỉ kéo tấm tự có số";
script thử ngược `thu_nguoc_asshot.py` trong scratchpad);
`test_preset_khong_wb_tone.py` giờ kiểm BƯỚC 1 với `wb_theo_asshot` TẮT, riêng
phần sidecar chạy DEFAULTS. Tắt: `wb_theo_asshot` = False (chưa có ô giao diện).

## Giao diện gọn (3/10 chiều)

User (16:41): "các bước Tổng quan, 3 4 6 7 gần như không cần tới. Đưa phần Ghi
và đẩy vào Lightroom lên giao diện của Phân Tích. Option của phân tích thu gọn
theo các nhóm. Tính năng có thông số thành thanh trượt. Chú thích vào dấu ? cạnh
mỗi tính năng, di chuột vào mới hiện."

(Mục này là bước TRƯỚC Evoto — cột trái, `KHAU_CHINH`, `_vua_tuy_chon`, ba cột
tuỳ chọn đều đã bỏ tối 3/10; giữ lại vì các bài học trong đó vẫn đúng. Bố cục
hiện hành ở mục "Giao diện kiểu Evoto" ngay dưới.)

- **Cột trái**: `KHAU_CHINH = ("nap", "phan_tich", "retouch")`. Mã khâu và `KHAU`
  giữ nguyên (trang_thai.tinh() vẫn trả đủ); tiêu đề khâu ẩn không mang số. Mở
  app là vào Nạp ảnh. 17:41 user: "bỏ luôn phần giao diện này vì không cần dùng
  tới" — đáy cột trái chỉ còn dòng hạn dùng: đã gỡ "Chạy hết" (cả `start_all`;
  cờ `chuoi` trong start_analyze vẫn giữ), "Bảng tóm tắt buổi…", "Khâu khác ▾".
  Tổng quan / Export / Vì sao tôi sửa / Gu đã học không còn lối vào; Duyệt nhanh
  vào từ menu "Thêm ▾".
- **Khâu Phân tích**: hàng 6 Phân tích/Dừng + thanh tiến độ (`pb3` = `pb`), hàng
  7 `btn_ghi3` "2 · Ghi và đẩy vào Lightroom" — VẪN là widget duy nhất gọi
  do_apply cả app — + "Đẩy thẳng vào Lightroom" + menu "Thêm ▾" (CSV, Hoàn tác,
  Đọc từ Lightroom, Duyệt nhanh, nhật ký, làm mới, cài plugin), hàng 8 `lbl_job`.
  `lbl_job` chỉ nói job của ĐÚNG buổi đang mở (`at.job_cua_buoi`, tên lấy từ
  `at.ten_job` — một chỗ duy nhất với write_lr_job); trước đó nó nằm trong thẻ
  khâu 3 và KHÔNG BAO GIỜ hiện (nhãn bị pack_forget).
- **Tuỳ chọn**: 7 nhóm `gd.Nhom` (Cách cân tone, Ánh sáng của buổi | Giới hạn
  chỉnh, Ghìm & bảo vệ, Loại buổi | Gom cảnh & đồng bộ, Lọc ảnh), ĐÓNG sẵn, mỗi
  nhóm một dòng tóm tắt (wraplength 300 — không được kéo rộng cột). Thân nhóm
  chỉ pack_forget, biến vẫn sống, read_cfg() như cũ. `_vua_tuy_chon` cho ô
  tuỳ chọn cao đúng bằng nội dung (trần = khung − 300), bảng ăn phần còn lại.
  Hai cột thì c3 nằm DƯỚI c1.
- **Thanh trượt** `gd.ThanhTruot`: StringVar cũ giữ nguyên, ô số đi kèm gõ được
  số ngoài khoảng thanh ("nghỉ quá" thanh 1–60, gõ tới 240). Tính lại kế hoạch
  (plan() ~1 s/1000 ảnh) chỉ khi THẢ chuột / Enter / rời ô — và chỉ khi số đổi
  so với lúc bắt đầu thao tác; phím mũi tên gom 0.4 s. `configure(state=...)`
  như Spinbox cũ (`_on_mode_change` không phải sửa).
- **Dấu ?** `gd.NutHoi` + `gd.GoiY` (cửa sổ nổi, trễ 280 ms, kẹp trong cửa sổ
  app — không theo màn hình chính). MỌI dòng chú thích cũ còn nguyên văn
  (test_giao_dien_gon có danh sách). Dòng mô tả khâu (`MO_KHAU`) vào dấu ? cạnh
  tiêu đề. Cảnh báo "không tách cảnh" vẫn in ra — cảnh báo phải thấy, không vào ?.
- **Ô chọn** rộng đúng chữ dài nhất (`gd.vua_chu`) — width mặc định 20 ký tự làm
  `_xep_cot` tưởng đủ chỗ trong khi chữ bị cắt TRONG ô ("Da trắng hồng — máy đo
  + ngả hồng (k"), lỗi có sẵn ở cửa sổ 1360/1660. kiem_man_hinh giờ đo cả chữ
  trong ô chọn.
- **Cảnh báo im lặng** (plugin chết / bản xuất cũ hơn lần ghi — bệnh 7/9) trước
  chỉ hiện trên Tổng quan, giờ lên dải trên cùng `dai_canh` (cùng `lbl_moi` "mã
  nguồn đã đổi"), khâu nào cũng thấy.
- **Vòng làm mới 4 giây TỪNG KHÔNG CHẠY**: dòng hẹn lại nằm lạc cuối
  `_hien_khoa()`, nên cột trái chỉ đọc trạng thái một lần lúc mở app (chọn buổi
  xong vẫn "CHƯA CHỌN BUỔI"). Giờ `_vong_lam_moi()` tự hẹn; `_lam_moi_ray()` gọi
  thẳng được (xuất xong, chọn buổi) mà không đẻ thêm vòng.
- Thanh trượt bị tắt / rê chuột hiện hai ô TRẮNG: map "." của clam (disabled
  #dcdad5, active #eeebe7). `dat_theme` ghi đè map của TScale.

Kiểm: `test_giao_dien_gon.py` (19 lần thử ngược, lần nào cũng đỏ đúng mục),
`kiem_bo_cuc.py` (12), `kiem_man_hinh.py` (4 — đo khi MỞ HẾT nhóm: không cuộn ở
≥1200, < 700 px; khi ĐÓNG HẾT: ≤ 260 px, ô nhìn bám nội dung, vẫn 3 cột).
Thử ngược trên bản sao thư mục thì mọi `.py` phải là file THẬT, không symlink —
autotone_gui chèn `Path(__file__).resolve().parent` vào sys.path, symlink resolve
về thư mục gốc nên đột biến mất tác dụng mà bài kiểm vẫn "đạt". Và tìm tên mục
trong dòng `[!]` chứ không trong cả đầu ra — tên mục in ra cả khi đạt.

## Giao diện kiểu Evoto (3/10 tối)

User (17:41, kèm ảnh khối "Chạy hết / Bảng tóm tắt buổi… / Khâu khác ▾"): "bỏ
luôn phần giao diện này vì k cần dùng tới. Sau khi bỏ. thì có thể tham khảo giao
diện của Evoto để thiết kế lại toàn bộ giao diện của ứng dụng". Chọn: bố cục
"Lưới ảnh như Evoto", màu nhấn vàng.

- **Khung** (`_build_shell`): hàng 0 dải cảnh báo `dai_canh` · hàng 1 thanh công
  cụ `thanh_cc` (AutoTone │ `nut_buoi` ▾ = `menu_buoi`: chọn thư mục, quét lại,
  gồm thư mục con, nguồn preset, xoá dữ liệu cũ │ `lbl_job` │ `btn_analyze` ·
  `btn_ghi3` · `btn_them` ⋯) · hàng 2 thân (`giua` + bảng điều khiển phải
  `ben_phai`/`cuon_phai` + cột mô-đun `thanh_md`) · hàng 3 thanh trạng thái
  `thanh_tt` (tiến độ · `lbl_status` · `lbl_han`). `gd.Ray` còn trong
  giao_dien.py nhưng không ai dùng.
- **Mở app vào thẳng trang chính** (`phan_tich`): dòng đầu [Lưới ảnh | Bảng số]
  + `lbl_tong` + `lbl_hint`, dưới là dải báo `dai_quet` rồi lưới / bảng. "nap"
  chỉ còn là bí danh của trang chính. Trang phụ (Duyệt nhanh…) có nút ← + tên
  trang + dấu ?. Retouch là mô-đun riêng: bảng điều khiển phải và nút trên
  thanh công cụ của RIÊNG nó, không mang dải báo của buổi (mục dưới).
- **Nút vàng = việc kế tiếp** (`_set_busy`): chưa có buổi → không nút nào trên
  thanh vàng (nút vàng là "Chọn thư mục buổi chụp" giữa lưới); có ảnh chưa phân
  tích → "1 · Phân tích"; có kết quả → "2 · Ghi". `NutTron.configure(kieu=)`.
  `btn_ghi3` VẪN là chỗ duy nhất gọi do_apply cả app (đếm cả mục menu).
- **Lưới ảnh** (`luoi_anh.py`): chỉ vẽ ô đang nhìn; đọc ảnh nhỏ ở luồng nền
  (ngăn xếp — ô đang nhìn trước, ô đã cuộn qua bỏ), PhotoImage chỉ tạo ở luồng
  chính; hết việc thì thôi hẹn nhịp; huỷ nhịp khi widget mất. Kho ảnh nhỏ trên
  đĩa `goc_du_lieu()/anh_nho` (khoá = đường dẫn + mtime + cỡ + 360; quá 30 000
  tấm xoá 1/4 lâu không dùng). `at.anh_nho()` lấy JPEG NHỎ NHẤT mà bảng IFD chỉ
  tới và đủ cạnh (vài KB), chỉ lùi về read_raw() khi không có — read_raw quét 16
  MB/tấm. Ô giãn kín bề ngang. Lưới và bảng số là HAI CÁCH NHÌN MỘT DANH SÁCH:
  cùng thứ tự (`_sort_by` sắp chính self.items), chọn bên này bên kia theo.
- **Ảnh SẼ KHÔNG được ghi vẫn hiện trên lưới**, tối đi + nhãn: "thiếu .xmp"
  (nguồn sidecar), "không ghi" (nguồn catalog, không có trong bản xuất — gồm ảnh
  1 sao plugin bỏ). Thử 3/10: buổi 60 RAW chưa có .xmp ra lưới TRỐNG kèm câu
  "Không tìm thấy file RAW nào" — sai, RAW có đủ.
- **Dải báo của buổi** `gd.DaiBao`: `lbl_scan` = `dai_quet.nhan`, `btn_fix` =
  `dai_quet.tao_nut()`; mọi chỗ gọi cũ (configure(text=, foreground=),
  .pack()/.pack_forget()) giữ nguyên — màu chữ truyền vào thành MỨC của dải
  (loi đỏ / canh cam / xong một dòng mờ), không chữ thì ẩn. Trước nằm giữa
  thanh công cụ: câu dài xuống 2–3 dòng đỏ, kéo cao cả thanh.
- **Một dòng**: `lbl_status`, `lbl_job` là `gd.NhanGon` — câu dài cắt "…", rê
  chuột hiện đủ, `cget("text")` vẫn trả câu ĐỦ. `lbl_job` nằm cạnh nút Ghi.
- **Bảng điều khiển phải** một cột, bề ngang CỐ ĐỊNH = thân nhóm rộng nhất (thanh
  chân `ttk.Frame(width=rong)` — đo được cả khi nhóm đóng) + chỗ thanh cuộn chừa
  sẵn (`Cuon.theo_noi_dung`): mở/đóng nhóm không làm lưới nhảy cột. Viên chọn
  Loại buổi / Nguồn sáng đứng một mình một hàng, ? ở mép phải. Nhãn WB rút còn
  "Da trắng hồng  (khuyên dùng)" (ô chọn dài nhất quyết định bề ngang cả cột;
  "máy đo + ngả hồng" đã có trong dấu ?).
- **Câu chỉ đường** theo bố cục mới: không còn "Enter ở ô thư mục", "khâu 1",
  "dưới nút Ghi", "Đổi ô Nguồn ở trên" — kiem_bo_cuc soi mọi chuỗi không phải
  docstring. `lbl_hint` chỉ nhắc "Read Metadata from File" khi ĐÃ TẮT "Đẩy
  thẳng" (đang đẩy thẳng mà nhắc là chỉ sai đường).
- Thanh tiến độ ở thanh trạng thái chỉ hiện khi đang chạy hoặc còn chữ "… xong
  N/N" (đổi buổi thì xoá). Bảng số có thanh cuộn ngang tự ẩn (15 cột ~1250 px >
  vùng giữa); dòng chọn màu xám trung tính (vàng trùng màu dòng "chỉnh mạnh").
- `luoi_anh` import TRONG hàm → phải có trong `NGAM` của dong_goi.py
  (kiem_dong_goi bắt).

**Mức của kiem_man_hinh đổi theo bố cục — ghi rõ vì sao, KHÔNG phải hạ mức.**
Mức cũ "mở hết nhóm thì ở cửa sổ ≥1200 px cao không phải cuộn; khối < 700 px"
đo khối tuỳ chọn NẰM TRÊN bảng kết quả (ba cột). Bố cục user chọn để tuỳ chọn ở
MỘT cột riêng bên phải, nút chính lên thanh công cụ — hai chuyện mức cũ canh
(khối tuỳ chọn ăn chỗ bảng ảnh; phải cuộn cả trang mới tới nút chính, 3/9) không
còn xảy ra được. Mức mới: đóng hết vừa ở mọi cỡ từ 1180×680; một nhóm (nhóm cao
nhất) vừa ở mọi cửa sổ ≥1200; MỞ HẾT vừa ở cỡ thật 2400×1380 (1227/1242 px trên
Linux — phải bớt khoảng thưa mới vừa). Cửa sổ 1900×1200 mở hết 7 nhóm thì cột
phải cuộn 165 px — in ra, không báo hỏng; muốn khỏi cuộn cả ở đó thì phải đổi
thanh trượt sang một hàng kiểu Lightroom (bỏ kiểu Evoto user đã chọn).

Kiểm: test_giao_dien_gon, kiem_bo_cuc, kiem_man_hinh, kiem_ve_that (giờ là lưới
ảnh vẽ thật) — 33 lần thử ngược (`gui/db_evoto.py` trong scratchpad), lần nào
cũng đỏ đúng mục. Một đột biến từng LỌT là đột biến tương đương: bỏ riêng
`vua_chu` thì ô chọn fill="x" vẫn giãn theo cột, chữ không bị cắt — đột biến
thật phải làm ô HẸP hơn chữ của nó.

## Retouch kiểu Evoto (3/10 tối)

User (sau khi duyệt bố cục Evoto): "oke đưa cả phần Retouch thay đổi luôn".
Không đụng gì bên ToolCloneEvoto. (Vùng giữa và Xem trước của mục này đã đổi
tiếp ở mục "Retouch: ảnh lớn + dải ảnh" ngay dưới — đọc mục đó cho bố cục hiện
hành.)

- **Đổi mô-đun** (`_chon_khau`): Cân tone ↔ Retouch đổi cả bảng điều khiển phải
  (`cuon_phai` ↔ `cuon_phai_rt`, cùng cột, cùng bề ngang 394 px — thanh chân
  `app._rong_bang`) lẫn nút bên phải thanh công cụ (`cc_phai` ↔ `cc_phai_rt`).
  Ở Retouch: ẩn `lbl_job`, đầu trang phụ `dau_trang`, dải báo của buổi
  `dai_quet`. Chưa dựng RetouchWindow thì ẩn hẳn `ben_phai`.
- **RetouchWindow(app, cha, ben=, thanh=)**: không truyền ben/thanh thì dựng
  ngay trong khung của nó (kiem_ghi_de vẫn gọi `RetouchWindow(app)`). Vùng giữa:
  [Lưới ảnh | Nhật ký] + `lbl_tt` + tiến độ `pb`; dải báo `dai_rt` khi tool chưa
  dùng được (chữ CHÉP từ `lbl_goc` qua `_dong_bo_dai`, không viết câu thứ hai,
  kèm nút "Chọn thư mục tool…"); dưới là lưới ảnh của thư mục VÀO. Bấm đúp một
  tấm = xem trước đúng tấm đó. Lưới trống có nút "Chọn thư mục ảnh đã Export".
- **Thanh công cụ**: "▶ Chạy retouch" (vàng) · "Xem trước" · ⋯ (Kiểm tra tool,
  Đọc lại tính năng, Mở thư mục vào/ra). "■ Dừng" chỉ hiện khi đang chạy
  (`_dat_dang_chay`).
- **Bảng phải**: 4 nhóm `gd.Nhom` — Thư mục (mở) · Mức áp dụng (mở) · Máy &
  cách chạy (đóng) · Tool retouch (đóng), mỗi nhóm một dòng tóm tắt khi đóng.
  Đang ép số luồng thì tóm tắt nói "⚠ ép N luồng" (nhóm đóng vẫn thấy). Ô tick →
  `gd.CongTac`, máy / chế độ → `gd.PhanDoan` (`TEN_CHE_DO`), nút → `gd.NutTron`,
  thanh kéo → `gd.Truot` (`configure(state=)`, `cget("state")` như ttk.Scale).
  Thẻ nhóm khuôn mặt là hàng viên chọn, `MOI_HANG_THE = 3` viên một hàng — sáu
  viên ("Nữ lớn tuổi"…) là vượt cột, cột phình, lưới nhảy cột khi đổi mô-đun.
  Nhóm có mức riêng mang dấu " ·" (`PhanDoan.dat_lua_chon`).
- **MỘT danh sách cho bộ đếm và lưới**: `rt.ds_anh(vao, ra, de_quy)` →
  [(ảnh, đã có kết quả)], lọc đúng cách duong_ong.chay() lọc; `rt.dem()` đếm
  trên nó, lưới vẽ từ nó ("✓ đã làm" — khoá `dau` của luoi_anh: nhãn thường,
  ảnh KHÔNG tối đi như `bo`). Ô "Ra" trống / "." là CHƯA CÓ, không phải thư mục
  hiện hành (`Path("") == Path(".")` — bản cũ coi mọi ảnh trùng tên trong thư
  mục app đang đứng là đã làm). Ghi đè: không đếm được bằng file → lấy
  `_tien_do_tool` (dòng tiến độ của saytool), lưới không gắn nhãn.
- **`at.anh_nho()` mở thẳng ảnh thường** (JPEG/PNG/TIFF/WebP/BMP đã Export) bằng
  PIL (draft + xoay EXIF). Đi read_raw() là quét 16 MB tìm preview trong một file
  vốn đã là ảnh; TIFF 16 bit còn rơi vào nhánh bảng IFD và ra "không đọc được".
- **Một chuyện một cảnh báo**: chưa có tool → chỉ dải báo trên lưới; thẻ "bảng
  DỰ PHÒNG" trong nhóm Mức áp dụng chỉ khi CÓ tool mà hỏi không được (bệnh 9/9).
  `gd.TheBao` (vạch màu bên trái + chữ + nút) cho: Vào lệch thư mục Export của
  buổi, bảng dự phòng, tool đã chuyển chỗ.
- **Ô hiện/ẩn nhớ chỗ** (`_dat_cho` / `_hien_an`): pack_forget quên vị trí, pack
  lại không có `before=` là ô chạy xuống cuối nhóm.
- **Xem trước** (`xem_truoc.py`) mở với MỨC CHUNG đang đặt (trước bắt đầu từ 0
  hết = xem một thứ khác với thứ sẽ chạy); mở được ảnh là tự tính một lần. Mức
  RIÊNG theo nhóm chưa sang xem trước — cửa sổ đó chỉ có thanh chung. NutTron +
  gd.Truot; số cạnh thanh đọc từ BIẾN (trace); thả chuột bind `add="+"` (bind
  đè mất `Truot._tha` → núm kẹt ở trạng thái đang kéo); phím mũi tên gom 0,4 s.
- **Widget vẽ tay** (NutTron, PhanDoan, Truot) vẽ theo `winfo_width()` khi > 1
  kể cả chưa map: `<Configure>` có thể tới TRƯỚC `<Map>`, vẽ theo `rong_can` lúc
  đó là viên chọn hẹp lệch một góc trong bảng Retouch.

Kiểm: kiem_retouch_gui (7 mục; mục 6 dáng Evoto, mục 7 xem trước mang mức),
kiem_bo_cuc 5b, test_giao_dien_gon (đổi mô-đun đổi cả bảng lẫn nút),
kiem_man_hinh (Retouch không còn đầu trang phụ) — 22 lần thử ngược
(`gui/db_retouch.py` trong scratchpad), lần nào cũng đỏ đúng mục; chạy lại cả
33 lần của bộ Evoto sau đợt này, vẫn đỏ cả 33. Ba lần từng
LỌT, đã sửa BÀI KIỂM (không sửa mức): nhãn ép `width=12` không bị so reqwidth
bắt (width= làm reqwidth bằng đúng ô, chữ bị cắt TRONG ô) → đo chữ bằng chính
font của nhãn (`chu_bi_cat`); "sáu thẻ một hàng" bị mục khác bắt → tách hằng
`MOI_HANG_THE`; bấm thẻ không đổi nhóm làm bài kiểm sập KeyError không có dòng
`[!]` → mục bấm báo lỗi rồi đi tiếp bằng `doi_nhom("nam")`.

Ngoài bộ kiểm: `test_retouch_luong.py` đã cũ TỪ TRƯỚC — đòi `LUONG_MAC_DINH = 1`
trong khi từ saytool 0.9.5 mặc định là 0 (tool tự dò); đỏ y hệt với retouch.py
trước đợt này. `kiem_xem_truoc.py` / `kiem_nhan_keo.py` chỉ chạy được trên máy
có ToolCloneEvoto thật (+ ảnh thử ở G:\TestRetouchFinal) — ở Linux in "bỏ qua".

## Retouch: ảnh lớn + dải ảnh, zoom làm lại (3/10 khuya)

User (22:03, kèm ảnh mô-đun Retouch): "Phần lưới ảnh của Retouch hãy làm giống
Evoto. 1 ảnh mở to và lưới ảnh bên dưới. Sửa lại cả tính năng zoom ảnh".

- **Bố cục giữa**: [Ảnh | Nhật ký] · tiến độ, rồi `tk.PanedWindow` dọc: trên là
  ẢNH LỚN (`khung_anh.KhungAnh` = `self.xem`) + thanh mỏng dưới ảnh
  (`_dung_thanh_xem`: chip trạng thái · tên · cỡ …… Vào mặt · Vừa khung · 100% ·
  tỉ lệ · Giữ xem gốc · ?); dưới là dải ảnh (`LuoiAnh(dai=True)`, vẫn là
  `self.luoi`). Thanh chia kéo được, cao dải nhớ ở retouch.json (`cao_dai_anh`).
- **Dải ảnh** (luoi_anh, `dai=True`): khung thấp hơn hai hàng ô thì MỘT hàng cuộn
  ngang (lăn chuột đi ngang 2 ô/nấc, không tên dưới ô, ↓ = tấm kế), kéo cao thì
  lại là lưới. Cao ô lượng tử 8 px (kéo thanh chia không đẻ hàng loạt
  PhotoImage). Chỉ kéo tới tấm đang chọn khi VỪA đổi chế độ / cỡ ô — lúc chạy
  `_dem` 1,5 s/lần gọi `dat_ds` lại, kéo mỗi lần thì không lướt dải được. Lưới
  Cân tone (`dai=False`) không đổi.
- **Ảnh lớn mở gì**: tấm đã làm → BẢN KẾT QUẢ (giữ chuột / phím \ / nút "Giữ
  xem gốc" = bản gốc, cùng chỗ đang soi); chưa làm → ảnh vào; ghi đè → ảnh vào,
  không chip. Đường kết quả: `rt.duong_ket_qua` — CHÍNH hàm `ds_anh` dùng gắn
  "✓ đã làm". Mở mô-đun là có ảnh lớn ngay (tấm đầu). Tấm đang xem vừa có kết
  quả (lượt chạy vừa ghi) → tự mở lại bản kết quả, giữ chỗ đang soi; đọc hỏng
  (đang ghi dở) thì lần đếm sau thử lại.
- **Zoom cũ (cửa sổ Xem trước) hỏng ba chỗ**: (1) tk.PhotoImage chỉ subsample
  được, không phóng — càng phóng ảnh càng BÉ; (2) mỗi nấc lăn là một vòng qua
  tiến trình con, ảnh đứng im; (3) kéo không chạy theo tay, kéo xong kẹt "ẢNH
  GỐC". `khung_anh.py` vẽ bằng PIL ĐÚNG vùng đang nhìn, đổi cỡ đúng bằng khung
  (6–40 ms/lần với ảnh 7008×4672), từ tháp 1/2·1/4·1/8 (`Image.reduce`). Lăn
  phóng QUANH CON TRỎ (×1,2/nấc, vừa khung ↔ 800%); kéo đi ngay; nháy đúp vừa
  khung ↔ 100% đúng chỗ bấm; phím 0 / 1 / + / − / M / ← → / \. Từ 300% vẽ
  NEAREST (soi điểm ảnh), đang lăn/kéo BILINEAR, ngừng tay 170 ms vẽ lại
  LANCZOS/BICUBIC. Từ vừa khung, nấc lăn đầu bị kẹp mép (ảnh mới lớn hơn khung
  một chút) nên điểm dưới con trỏ xê dịch — đúng ý, như Lightroom.
- **Nạp dần**: ảnh nhỏ của dải hiện NGAY (`Thap(tam=True)` — KHÔNG BAO GIỜ tính
  là đủ nét: ảnh 300 px trùng cỡ ảnh thật thì bản kết quả tới sau bị bỏ, ảnh lớn
  kẹt ở ảnh gốc — gặp ở bài kiểm), rồi bản nháp JPEG draft ≥1400 px (~60 ms),
  rồi bản đủ nét (~230 ms), ở MỘT luồng nền (việc mới thay việc cũ, tin của tấm
  cũ có mã → bỏ). Khung nhìn theo toạ độ ảnh đủ nét → ba bản thay nhau không
  nhảy.
- **Vào mặt**: YuNet trên bản nháp, bộ nhận diện RIÊNG cho luồng nạp
  (`at.face_detector()` dùng chung một đối tượng; setInputSize/detect từ hai
  luồng là đua). Mặt to trước; phóng vừa mặt ×2,6, tối đa 200%; bấm tiếp sang
  mặt kế.
- **Đóng app phải đợi luồng nạp** (`_BoNap.dung(cho=3)` trong `_huy`): luồng đang
  ở giữa cv2 mà tiến trình thoát là C++ "terminate called without an active
  exception" → abort (Windows: hộp thoại lỗi lúc tắt app). Gặp ở bài kiểm, rc 134.
- **Xem trước NGAY TRÊN ẢNH LỚN** — không còn cửa sổ riêng; `xem_truoc.py` chỉ
  còn `MayXem` + `MA_CON`. (Nút "Xem trước" trên thanh công cụ đã BỎ sáng 4/10 —
  kéo thanh là tự xem, xem mục kế.) Bấm đúp một tấm trên dải vẫn bật.
  Tiến trình con trả CẢ KHUNG 1400 px (zoom làm ở app); mọi tin mang `fp` (kết
  quả thêm `ma`) để bỏ tin của tấm cũ — kết quả muộn của tấm cũ không bao giờ đè
  lên tấm đang xem. Mức gửi = `muc_day_du()` (cả mức riêng theo nhóm); tool từ
  chối khoá "nam:vet" thì tính lại với mức chung + ghi nhật ký (`_xem_bo_nhom`).
  Đổi mức → tính lại sau 0,2 s ngừng tay (4/10; trước 0,45); đang tính thì chỉ đánh dấu, tính thêm
  MỘT lần khi xong; mức không đổi (đổi thẻ nhóm dựng lại thanh) thì không tính.
  Ảnh tool không thấy mặt VẪN tính (từ 0.9.5 có bước chạy trên cơ thể), chip nói
  ra. Bấm sang tấm khác lúc đang xem trước → hiện ngay bản trên đĩa trong lúc
  chờ. Bấm Chạy → tắt máy xem trước TRƯỚC (hai bộ mô hình trên một card = OOM);
  đang chạy cả mẻ thì không bật. Tiến trình chết → tắt xem trước, chip nói ra.
  Xem trước vẫn ở cỡ 1400 px (CANH trong MA_CON) — soi 100% ảnh thật thì xem
  bản kết quả sau khi chạy.

Kiểm: `kiem_khung_anh.py` (mới — ô cờ 10 px phải dài 40 px ở 400%, điểm dưới con
trỏ đứng yên, ảnh vẽ lại TRONG lúc kéo, kéo sau khi giữ không kẹt gốc, nạp dần
giữ khung nhìn, đổi ảnh nhanh không lóe ảnh cũ…), `kiem_ve_that.py` (dải ảnh),
`kiem_retouch_gui.py` mục 6–7 (tool giả chạy qua ĐÚNG tiến trình con), 
`kiem_bo_cuc.py` 5b, `kiem_xem_truoc.py` (tool THẬT — chạy được ở Linux với tool
giả qua AUTOTONE_TOOL_THU / AUTOTONE_ANH_THU). Thử ngược: `gui/db_anh_lon.py`
36 lần, `gui/db_retouch.py` 20, `gui/db_evoto.py` 33 (scratchpad). Bốn lần LỌT
đầu đều do BÀI KIỂM, đã sửa: event_generate không ghi `time` thì Tk coi lần bấm
thứ hai cùng chỗ là NHÁY ĐÚP (gọi `_dup` thay `_nhan`) — mọi sự kiện chuột trong
kiem_khung_anh giờ cách nhau 1 giây; đọc số dòng tool giả ghi ngay sau khi hẹn
tính là đua (đếm `_xem_ma` thay vì đợi file); ảnh nhỏ của dải chưa đọc xong thì
không đi qua nhánh ảnh tạm (đợi `_anh_pil`); bài kiểm sập không có dòng `[!]` là
lọt (bọc try, báo đúng mục).

## Retouch: kéo là xem · mức riêng từng ảnh · Sync (4/10 sáng)

User (kèm ảnh bảng phải): "Ở phần Retouch bỏ nút xem trước. Vì khi kéo sẽ load
luôn vào ảnh để thấy đc luôn" — rồi: "Và cần thêm nút Sync All các hiệu ứng đã
kéo cho các ảnh được chọn hoặc tất cả". Làm theo kiểu Evoto:

- **Không còn nút "Xem trước"**. Kéo một thanh (`_muc_doi` → `_nguoi_doi_muc`)
  là ảnh lớn TỰ tính lại theo mức của ảnh đang xem (`_mo_xem_truoc(tu_dong=True)`:
  không hộp thoại nào, chỉ nói ở chip). Tắt: bấm chip "Xem trước · …  ✕" dưới
  ảnh lớn — về bản trên đĩa, GIỮ vùng đang soi. Chỉ NGƯỜI kéo mới tính:
  `_nap_muc_vao_bang` (nạp mức của tấm vừa chọn) chạy dưới cờ `_dang_nap_muc`.
- **Máy xem trước mở SẴN**: vào mô-đun Retouch (App `_chon_khau`) → sau 0,3 s
  `_san_may_xem` mở tiến trình con ở nền và mở ngầm tấm đang xem (ảnh lớn vẫn là
  bản trên đĩa) → lần kéo đầu tính NGAY, không chờ nạp mô hình / tìm mặt. Rời
  mô-đun → `_nghi_may_xem` tắt (trả card đồ hoạ cho Lightroom). Chạy xong cả mẻ
  → mở lại. Máy chết thì `_xem_hong`: kéo thanh KHÔNG tự mở lại (tránh vòng
  chết → mở), chip bảo bấm đúp một tấm để thử lại; chọn tool mới thì xoá cờ.
- **Một lần mở ảnh mỗi lúc** (`_xem_xin_mo` + `_xem_mo_dang`): tiến trình con làm
  tuần tự — lướt nhanh mười tấm trước đây xếp hàng mười lần mở. Đang mở dở thì
  KHÔNG tính (`_xem_tinh` thoát): tính lúc đó là tính trên tấm khác ("chua mo anh
  nay") — và lỗi đó từng có thể bị hiểu nhầm là tool chê khoá nhóm, tắt luôn mức
  riêng theo nhóm trong xem trước. `_anh_hien` = tấm ẢNH LỚN đang hiện thật (so
  với nó, không so với tấm tiến trình con đang mở, khi quyết định hiện bản đĩa).
- **Giữ vùng soi khi đổi độ phân giải** (`KhungAnh._anh_xa`): bản đĩa 6000 px ↔
  bản xem trước 1400 px cùng tỉ lệ khung → giữ tâm (quy đổi) và tỉ lệ; bản 1400
  px không phóng quá `ZOOM_GIU` = 200%. Khác tỉ lệ khung → vừa khung.
- **Mức riêng từng ảnh**: bảng thanh kéo hiện MỨC CỦA ẢNH ĐANG XEM; kéo = chỉnh
  ảnh đó (`_muc_anh[khoá]`, khoá = `rt.khoa_anh`: tên, hoặc đường dẫn tương đối
  khi "Cả thư mục con"). Ảnh chưa chỉnh theo MỨC CHUNG = retouch.json "muc" (như
  trước — ai không đụng Sync thì kết quả y hệt). Mức riêng trùng mức chung thì
  KHÔNG giữ (không có nhãn "riêng" ảo). Mức riêng là bộ ĐẦY ĐỦ (cả nhóm mặt):
  `_muc_hieu_luc` chỉ lấy tính năng THIẾU từ mức chung, không lấy nhóm mặt.
  Ghi ra `du_lieu/retouch_anh/<sha1 thư mục vào>.json` (không ghi vào thư mục
  ảnh của khách), hẹn 0,6 s; đổi thư mục vào thì ghi NỐT bảng cũ rồi đọc bảng
  mới. Dải ảnh: nhãn vàng "riêng" góc trái trên.
- **Chọn nhiều trên dải** (`LuoiAnh(chon_nhieu=True)`, như Lightroom): Ctrl +
  bấm thêm/bớt, Shift + bấm một dãy, Ctrl+A, Esc; tấm ĐANG XEM (tấm nguồn của
  Sync) không đổi khi Ctrl/Shift. Rằng buộc riêng `<Control-Button-1>` /
  `<Shift-Button-1>` (Command CHỈ trên Mac — ngoài Mac nó là Mod1 = NumLock, xem
  mục 4/10 trưa) — KHÔNG đọc bit 0x8 của e.state: trên Windows là NumLock. Mũi
  tên / bấm thường = chọn một tấm. Lưới Cân tone không bật.
- **Bảng "Mức áp dụng"**: dòng phạm vi ("tên · mức riêng của ảnh này / theo mức
  chung"; tên dài thì XUỐNG DÒNG), nút "Về mức chung" ở DÒNG RIÊNG bên dưới (chỉ
  hiện khi ảnh có mức riêng — cùng dòng với tên là bảng phình 394 → 433 px, ảnh
  lớn / dải nhảy cột; ảnh chụp 4/10 bắt được), rồi [Sync ảnh đã chọn (N)] [Sync
  tất cả]. `_cap_nhat_pham_vi` chạy mỗi nhịp kéo → chỉ vẽ lại khi có gì đổi. Sync
  đã chọn: chép mức tấm đang xem sang các tấm chọn. Sync tất cả: mức đó thành
  MỨC CHUNG (ghi retouch.json ngay), xoá mọi mức riêng — HỎI LẠI nếu tấm khác
  đang có mức riêng khác.
- **Chạy theo nhóm mức** (`start()`): `rt.nhom_theo_muc` gom ảnh cùng mức hiệu
  lực. MỘT nhóm → chạy thẳng trên thư mục vào như trước. Nhiều nhóm → hỏi lại
  (kể từng nhóm), rồi mỗi nhóm MỘT lượt `rt.chay` của chính saytool trên thư
  mục tạm `.autotone_retouch_tam` CẠNH thư mục vào (liên kết cứng; exFAT thì
  chép; không ghi được thì thư mục tạm hệ thống), chỉ gồm tấm CÒN PHẢI LÀM; kết
  quả ra đúng thư mục ra, đúng tên. Nhóm mức 0 hết → chép NGUYÊN BẢN sang thư mục
  ra (không gọi tool). Ghi đè + nhiều nhóm → TỪ CHỐI (ghi đè trên thư mục tạm
  thì không biết ảnh gốc thật có đổi không). Thư mục tạm có file mốc
  `.autotone_tam` — chỉ xoá thư mục CÓ mốc; trùng tên mà không mốc là của người
  dùng → lấy tên `_1`, `_2`… Biến Tk đọc ở luồng chính, luồng nền chỉ cầm giá trị.

Kiểm: `kiem_retouch_gui.py` mục 7–8 (kéo là xem, mở sẵn / rời mô-đun, ✕ giữ vùng
soi, lướt nhanh một lần mở, Ctrl/Shift + bấm THẬT trên dải, Sync, ghi đĩa, chạy
theo nhóm với tool giả đếm lượt + kiểm liên kết cứng, thư mục trùng tên),
`kiem_ve_that.py` (`kiem_chon_nhieu`), `kiem_khung_anh.py` 10b, `kiem_bo_cuc.py`
5b, `kiem_xem_truoc.py` (kéo thanh thay nút). Thử ngược: `gui/db_sync.py` 48/48
+ chạy lại db_anh_lon 36 / db_retouch 20 / db_evoto 33 (4 đoạn gốc đổi theo mã
mới) — 137/137 bị bắt. Bài kiểm Retouch giờ THAY mọi hộp thoại tkinter bằng bản
ghi lại: một đột biến làm start() hiện hộp thoại modal là bài kiểm TREO tới hết
giờ (đã gặp) — và `gui/dot_bien.py` coi bài treo là LỌT chứ không sập cả bộ.

## Mặc định catalog · ẩn "Mặt sáng tới mức" (−1.00) · bấm khi NumLock (4/10 trưa)

User (ảnh menu "Lấy thông số preset từ:"): "Mặc định sẽ chỉ dùng Lightroom
Catalog." — rồi: "Do đã có tính năng bù sáng cả buổi nên ẩn đi phần Mặt sáng tới
mức đi. Có thể set phần mặt sáng tới mức về -1.00" — rồi (ảnh Retouch: khung to
vẫn tấm cũ, "Sync ảnh đã chọn (2)"): "Xử lý cả việc khi bấm vào 1 ảnh ở dưới lưới
ảnh thì cần hiển thị ngay trên khung to".

- **Nguồn mặc định = catalog** (`NGUON_MAC_DINH` trong autotone_gui.py): mở app
  là "Lightroom catalog qua plugin". Sidecar .xmp VẪN trong menu (máy chưa cài
  plugin), chỉ không còn mặc định. CLI (`autotone.py --nguon`) giữ mặc định cũ.
  Bài kiểm GUI nào quét thư mục CÓ RAW ở nguồn catalog là ghi
  `request_export.txt` → phải chuyển `at.LR_JOB_DIR` sang thư mục tạm trước
  (test_giao_dien_gon đã làm; các bài GUI khác hiện không quét).
- **Ẩn ô "Mặt sáng tới mức"**: `self.sp_target.pack_forget()` — biến, bật/tắt
  theo chế độ, đổi thang khi đổi cách đo vẫn sống; muốn hiện lại chỉ bỏ dòng đó.
  Sáng/tối theo buổi chỉnh ở "Bù sáng cả buổi" (nhóm Loại buổi); dấu ? của nó nói
  "Mốc sáng mặt: −1.00 EV". Dòng tóm tắt "Cách cân tone" bỏ "đích …"; chú thích
  "Chế độ" / "Độ trộn" thôi chỉ vào "ô dưới / ở trên".
- **Mốc `face_target_ev` −1.19 → −1.00** (DEFAULTS — áp cả CLI và công cụ đo).
  Giao diện lấy mốc từ DEFAULTS (`_moc_dich`), không ghi cứng "-1.19" ở bốn chỗ
  như trước → gu.json có `face_target_ev` thì giờ TỚI được giao diện (trước kia ô
  số luôn đè). Số cũ để đối chiếu: buổi CƯỚI TrainTool / 2609 user sửa trung vị
  −0.09 / −0.13 so với −1.19 (tức TỐI hơn) → với −1.00 ảnh cưới không bị phanh
  sáng hơn tối đa ~0.19 EV; dư sáng thì đặt "Bù sáng cả buổi" âm (vd −0.20). Mốc
  cao hơn cũng làm ảnh tối chạm trần "Kéo sáng tối đa" sớm hơn.
- **test_2ban_quay mục 1 ghim mốc −1.19** (`MOC_MUC_1`, `chay1`): số liệu
  DSC08668-72 đo trên mốc −1.19; với −1.00 nhóm A kéo +0.44 nên A6 (f/2.8, cần
  thêm +0.69) chạm trần max_ev_up 1.00 → bài đo bù khẩu thành đo trần (+0.56).
  Mục 1 kiểm CƠ CHẾ gộp theo ánh sáng, không kiểm mốc. Các mục khác đặt mặt đúng
  DICH (theo DEFAULTS) hoặc xa trần — không ghim. Cả bộ còn lại đạt với −1.00.
- **Bấm thường trên dải Retouch thành "chọn thêm" khi NumLock bật** (máy user):
  Tk NGOÀI Mac không báo lỗi tên `Command` — nó là tên khác của Mod1
  (`<Command-Button-1>` = `<Mod1-Button-1>`), mà Mod1 trên Windows chính là
  NumLock (bit 0x8). Bản sáng 4/10 tưởng "Tk báo lỗi tên lạ" nên ràng buộc ở mọi
  máy → NumLock bật là MỌI lần bấm thường khớp ràng buộc Command (khớp nhiều hơn
  `<Button-1>`) → thêm vào nhóm chọn, tấm đang xem đứng yên, khung to không đổi.
  Sửa: `<Command-Button-1>` chỉ khi `tk windowingsystem == "aqua"`. Bài học: tên
  modifier "chỉ có trên Mac" (Command / Option) là Mod1 / Mod2 ở MỌI nơi.
  Ctrl / Shift + bấm vẫn chỉ thêm vào nhóm chọn, giữ tấm đang xem (tấm nguồn Sync).

Kiểm: test_giao_dien_gon mục 0 (nguồn mặc định, menu còn Sidecar), mục 4 (thanh
trượt kiểm trên "Bù sáng cả buổi"), 4b (ô ẩn khi nhóm ĐANG MỞ, mốc trong code
−1.00 qua `GU_MAC_DINH`, cfg dùng mốc, đổi cách đo qua lại, tóm tắt, dấu ?),
`chu_thich_cu` đổi hai dòng (vẫn kiểm từng chữ); kiem_ve_that + kiem_retouch_gui:
bấm với state 0x8 trên dải → sang đúng tấm, ảnh lớn hiện tấm đó (Mac: Cmd + bấm
vẫn là chọn thêm). Thử ngược: `gui/db_numlock.py` 16/16; chạy lại mọi đột biến
cũ đụng file / bài vừa sửa: luoi_anh (kiem_ve_that) 24/24, kiem_retouch_gui +
test_giao_dien_gon (db_sync + db_cu_gop) 71/71; db_gon (16 đoạn còn khớp): 13
bắt, 3 lọt CŨ — đúng 3 cái đó cũng lọt trên mã trước 4/10 trưa (chữ phải thấy
đổi tên / cột trái và đầu trang phụ đã bỏ từ 3/10 tối). Bộ kiểm 38/38.

## Cập nhật không cài lại (OTA) — `cap_nhat.py` (4/10)

User: "update cho ứng dụng khi có cập nhật mới mà không phải cài lại bản mới".
Làm theo đúng triết lý `tai_nguyen.py` (vốn rất chắc), nhưng cho CODE + MODEL
thay vì thư viện nặng.

**Nguyên lý: tách CODE khỏi GÓI.** Gói PyInstaller (Python runtime + torch +
model ~2 GB) là phần nặng, ít đổi. Code app (`.pyd` lõi + `.py` plumbing) và
model retouch là phần hay đổi. Update chỉ tải CODE MỚI (vài MB) về
`goc_du_lieu()/cap_nhat/<ver>/`, và app NẠP CODE ĐÓ TRƯỚC code trong gói.

**Cơ chế nạp — vì sao chèn lên ĐẦU `sys.path` (đã kiểm chứng trên chính
`AutoTone.exe`):** module app trong gói nằm trong PYZ dạng `.pyc` (lõi mã hoá thì
là `.pyd/.so` ship riêng). **PyInstaller ≥ 6.10** cài importer của nó là
*path-entry-finder* chạy BÊN TRONG `PathFinder` — KHÔNG còn là meta-path finder
"nuốt" `sys.path` như bản cũ. Nên thư mục nào đứng TRƯỚC trong `sys.path` thì
thắng: thư mục update (FileFinder) đứng trước `sys._MEIPASS` (PyiFrozenFinder) →
module ở đó đè được bản trong PYZ, cả `.py` lẫn `.pyd`. Quy luật là THỨ TỰ
`sys.path`, KHÔNG phải "vì là .pyd". **Build phải dùng PyInstaller ≥ 6.10**
(`dong_goi.py` có chốt kiểm, chặn build nếu thấp hơn) — bản < 6.10 thì importer
là meta-path finder, `sys.path` bị bỏ qua, OTA âm thầm không ăn.
`kich_hoat()` gọi ở DÒNG ĐẦU khởi động, TRƯỚC mọi `import` module app (trước cả
`import tai_nguyen`).
- Bản chạy nguồn / không mã hoá: hook nằm trong `autotone_gui.main()`, ngay sau
  `freeze_support()`.
- Bản mã hoá: điểm vào thật là `chay.py` (`bao_mat.LAUNCHER`) — `kich_hoat()`
  nằm TRƯỚC `import autotone_gui` trong đó.
- `kich_hoat()` BỌC try/except rỗng: một bản cập nhật hỏng KHÔNG được chặn app
  mở lên. Thiếu hẳn module `cap_nhat` (bản cũ) cũng chạy bình thường.
- **Cạm bẫy `sys.modules` (đã vá + test + thử ngược):** thủ thuật `sys.path` chỉ
  ăn lúc import ĐẦU TIÊN. Nếu một module app lỡ bị import trước khi chèn, bản cũ
  nằm cache và `import` sau trả bản cũ. `kich_hoat()` vì vậy sau khi chèn đường
  sẽ POP khỏi `sys.modules` đúng những module mà bản update mang theo (chỉ những
  tên đó — không đụng stdlib/thư viện đang chạy) rồi `importlib.invalidate_caches()`.

**Model retouch — ĐÃ NỐI (4/10), qua `retouch.cwd_retouch()`:** saytool nạp
model theo đường TƯƠNG ĐỐI `mo_hinh/vet.pt` so với **CWD** của tiến trình con
(đã kiểm: nó KHÔNG đọc biến model riêng nào). Trước đây `retouch.py` đặt
`cwd=goc` ở cả 3 chỗ chạy saytool (`_hoi_keo`, `kiem_tra`, `chay`), mà `goc` =
`sys._MEIPASS` (chỉ-đọc). Cách nối:
- `cap_nhat.ap_model()` đặt `AUTOTONE_MO_HINH_VA` = thư mục `mo_hinh/` của bản
  vá đã kích hoạt (KHÔNG đặt biến cho saytool — vô ích).
- `retouch.cwd_retouch(goc)` (MỚI): thấy biến đó thì dựng một thư mục **lớp phủ**
  ghi được (`goc_du_lieu()/retouch_cwd/mo_hinh/` = model gói + model vá, **vá đè
  lên**) và trả nó làm CWD; không có biến → trả `goc` như cũ. Ba chỗ chạy saytool
  nay dùng `cwd=cwd_retouch(goc)`.
- VÌ SAO KHÔNG đổi thẳng `goc`: `la_goc_trong_goi(goc)` so `goc` với `_MEIPASS`
  để chọn lệnh `--say-chay` (bản gói). Đổi `goc` → nhận nhầm "chạy từ nguồn" →
  gọi `python -m saytool.cli` mà gói không có python → hỏng. Nên GIỮ `goc`, chỉ
  tách CWD ra (trước đây hai thứ trùng nhau).
- Model bản vá KHÔNG mang theo (ví dụ chỉ update code) → `nhan.pt`... vẫn là bản
  gói, không mất. Lớp phủ hỏng → lui về `goc` (retouch vẫn chạy với model gói).
- Kiểm: `test_retouch_cwd.py` (9 mục, gọi `cwd_retouch` thật) — vá đè đúng, giữ
  model gói chỗ bản vá không đụng, dùng lại lớp phủ, đổi bản vá thì cập nhật,
  thư mục vá không tồn tại thì lui về `goc`. Thử ngược: bỏ bước vá-đè → mục "vá
  đè" đỏ; đổi `return goc` → mục "đường cũ không đổi" đỏ.

**Kiểu cập nhật (đã chốt với user): HỎI trước khi tải.** Mở app → kiểm âm thầm
(thực ra kiểm chạy trong giao diện, luồng nền, sau khi cửa sổ mở — không làm
chậm khởi động) → có bản mới thì hỏi → người dùng đồng ý mới tải. KHÔNG tự áp
giữa chừng: tải xong ghi ra đĩa, LẦN MỞ SAU mới `kich_hoat()`. Đổi một `.pyd`
đang chạy bằng bản khác lúc đang chạy là trò mạo hiểm không cần. Có nút "Kiểm
tra cập nhật…" trong menu ⋯ (`App.kiem_cap_nhat` + lớp `TaiCapNhat`, theo đúng
mẫu `TaiTaiNguyenDialog`: queue + luồng nền + `_bom`).

**`latest.json` TÁCH THEO NỀN TẢNG** (quan trọng với bản mã hoá): bản `.pyd`
(Windows) ≠ `.so` (Mac), và `.so` còn khác giữa Apple Silicon (arm64) và Intel
(x86_64). Nên meta có khối `nen: {win:{...}, mac-arm64:{...}, mac-x86_64:{...}}`;
`cap_nhat.nen_may()` chọn đúng khối cho máy. KHÔNG có khối cho máy này → coi như
chưa có bản (KHÔNG tải nhầm `.so` hệ khác về). Bản `.py` THUẦN (chạy mọi hệ, tiện
sửa vặt plumbing) thì dùng meta đơn giản không có `nen` — vẫn tương thích ngược.

**Phát hành: `tao_ban_cap_nhat.py`** (chạy TRÊN máy đích, như `dong_goi.py` —
`.pyd` dịch trên Windows, `.so` trên Mac). Tạo `app-<ver>-<nen>.zip` (lõi mã hoá
+ plumbing, kèm `mo_hinh/` nếu `--mo-hinh`), in sẵn khối `latest.json` + SHA-256.
Có cả Win lẫn Mac thì chạy trên từng máy rồi GỘP các khối `nen`. `--khong-ma-hoa`
ra bản `.py` thuần. Rồi up lên Release tag cố định `app-latest` (xoá asset cũ, up
mới — URL không đổi). NHỚ đổi `cap_nhat.PHIEN_BAN_APP` cho lần build GÓI kế tiếp,
để gói mới không tự coi mình là cũ rồi nạp lại chính bản đó.

**Chống hỏng (đã kiểm + thử ngược — `test_cap_nhat.py`, 23 mục):**
- `.part` rồi đổi tên; SHA-256; giải nén ra thư mục TẠM rồi đổi tên; dấu `.xong`
  đánh dấu "giải nén đủ" — đúng ba nguyên tắc `tai_nguyen.py`.
- Chặn Zip Slip (entry `../` → OSError, không ghi ra ngoài).
- Phiên bản chặn đường dẫn lạ (`../..` → None); so sánh theo SỐ không theo chuỗi
  (`2026.9` KHÔNG > `2026.10`).
- Thử ngược đã chạy: phá `kich_hoat` (insert→append) → 2 mục `sys.path`/nạp-bản-vá
  đỏ; bỏ chặn Zip Slip → mục zip-slip đỏ. End-to-end: zip THẬT do
  `tao_ban_cap_nhat.py` sinh → `cap_nhat` kiểm/tải/giải nén/kích hoạt khớp.
- `cap_nhat` có trong `dong_goi.NGAM` (app import nó trong try/except, PyInstaller
  không dò được import trong try → thiếu thì OTA im lặng không chạy).

**Bẫy vá cùng lúc 4/10:** `kiem_dong_goi` báo `kiem_bq_giao_dien` +
`kiem_bq_online` chưa vào `LOAI_TRU`. `kiem_bq_giao_dien.py` `import cap_key` —
kéo cả khoá ký key vào gói nếu lọt. Đã thêm cả hai vào `LOAI_TRU` (cùng nhóm với
`tao_ma.py`/`cap_key.py`).
