# don_o_c.ps1 — Chuyển dữ liệu của hai dự án khỏi ổ C sang F:\Claude AI
#
#   .\don_o_c.ps1            <- CHỈ XEM. Không đụng gì cả. Chạy cái này trước.
#   .\don_o_c.ps1 -Chay      <- Chuyển thật.
#   .\don_o_c.ps1 -Chay -XoaZipThua   <- Chuyển, và xoá file zip đã giải nén rồi.
#
# CHUYỂN BẰNG JUNCTION, KHÔNG PHẢI CHỈ CHUYỂN
#     Hai thư mục dưới đây là chỗ THƯ VIỆN TỰ TÌM TỚI, không phải chỗ mình chọn:
#     insightface luôn tìm ở "thư mục nhà\.insightface", không có biến môi
#     trường nào đổi được. Chuyển đi mà không để lại gì thì lần chạy sau nó
#     KHÔNG BÁO LỖI — nó lặng lẽ tải lại 630 MB về đúng chỗ cũ trên ổ C.
#
#     Nên: chuyển dữ liệu sang F, rồi tạo JUNCTION ở chỗ cũ trỏ sang F.
#     Junction chiếm 0 byte, mọi chương trình đi qua nó như thư mục thật, và
#     không cần quyền admin. App đóng gói sau này cũng chạy y nguyên.
#
#     Cách khác: sửa mã ToolCloneEvoto — FaceAnalysis nhận tham số root=, và
#     skin_spike4.py đã đọc biến SKIN_SPIKE_CACHE. Không chọn cách đó vì phải
#     sửa hai chỗ trong một dự án riêng, phải nhớ đặt biến môi trường cho mọi
#     tiến trình, và bản đóng gói sau này lại không thừa hưởng biến đó.
#     Junction không cần đụng một dòng mã nào.
#
# CHẠY Ở ĐÂU
#     PowerShell thường (KHÔNG cần Run as Administrator).
#     cd "F:\Claude AI\AutoToneImages"
#     .\don_o_c.ps1
#
#     Nếu Windows chặn script:  Set-ExecutionPolicy -Scope Process Bypass

param(
    [switch]$Chay,
    [switch]$XoaZipThua
)

$ErrorActionPreference = "Stop"
$DICH_GOC = "F:\Claude AI\cache"

# Tên hiển thị, chỗ cũ trên C, tên thư mục ở chỗ mới trên F
$MUC = @(
    @{ Ten = ".insightface (mô hình nhận mặt của ToolCloneEvoto)"
       Cu  = Join-Path $HOME ".insightface"
       Moi = "insightface" }
    @{ Ten = "skin_spike (mô hình phân vùng da)"
       Cu  = Join-Path $HOME ".cache\skin_spike"
       Moi = "skin_spike" }
)

function Co-Bao($duong_dan) {
    # Cỡ thư mục, MB. Trả 0 nếu không có.
    if (-not (Test-Path -LiteralPath $duong_dan)) { return 0 }
    $t = Get-ChildItem -LiteralPath $duong_dan -Recurse -File -ErrorAction SilentlyContinue |
         Measure-Object -Property Length -Sum
    if ($null -eq $t.Sum) { return 0 }
    return [math]::Round($t.Sum / 1MB, 1)
}

function La-Junction($duong_dan) {
    if (-not (Test-Path -LiteralPath $duong_dan)) { return $false }
    $i = Get-Item -LiteralPath $duong_dan -Force
    return [bool]($i.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Dia-Trong($o) {
    $d = Get-PSDrive -Name $o -ErrorAction SilentlyContinue
    if (-not $d) { return $null }
    return [math]::Round($d.Free / 1GB, 1)
}

# ── Phần XEM ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Ổ C còn trống: $(Dia-Trong 'C') GB      Ổ F còn trống: $(Dia-Trong 'F') GB"
Write-Host ""
Write-Host "  THUỘC HAI DỰ ÁN — sẽ chuyển:" -ForegroundColor Cyan

$tong = 0
foreach ($m in $MUC) {
    $co = Co-Bao $m.Cu
    $jn = La-Junction $m.Cu
    if ($jn) { $trang = "ĐÃ chuyển rồi (junction)" }
    elseif ($co -eq 0) { $trang = "không có" }
    else { $trang = "đang nằm trên C"; $tong += $co }
    "    {0,-52} {1,8} MB   {2}" -f $m.Ten, $co, $trang | Write-Host
}
Write-Host ("    {0,-52} {1,8} MB   sẽ giải phóng khỏi ổ C" -f "TỔNG", [math]::Round($tong, 1))

# File zip thừa: insightface tải zip về rồi giải nén, cái zip không dùng nữa
$zip = Join-Path $HOME ".insightface\models\buffalo_l.zip"
$giai = Join-Path $HOME ".insightface\models\buffalo_l"
$co_zip_thua = (Test-Path -LiteralPath $zip) -and (Test-Path -LiteralPath $giai)
if ($co_zip_thua) {
    #[[ Khong phai doan. Doc thang trong insightface/utils/storage.py:
    #     def download(sub_dir, name, force=False, root='~/.insightface'):
    #         dir_path = os.path.join(_root, sub_dir, name)
    #         if osp.exists(dir_path) and not force:
    #             return dir_path          <- ve luon, khong dong toi zip
    #         ...
    #         #os.remove(zip_file_path)    <- chinh insightface de lai file zip
    #   Tuc: da co models/buffalo_l/ thi cai zip khong bao gio duoc doc nua, va
    #   neu co phai tai lai thi no tai de len (overwrite=True) chu khong dung
    #   file cu. Xoa la an toan.
    #]]
    $cz = [math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 1)
    Write-Host ""
    Write-Host "    buffalo_l.zip: $cz MB — đã giải nén ra rồi, insightface không đọc lại bao giờ." -ForegroundColor DarkYellow
    Write-Host "    Thêm -XoaZipThua để xoá luôn."
}

# ── Cái KHÔNG thuộc hai dự án, nhưng đang chiếm nhiều nhất ──────────────────
Write-Host ""
Write-Host "  KHÔNG thuộc hai dự án — chỉ báo để anh biết, script này KHÔNG đụng vào:" -ForegroundColor Cyan
foreach ($t in @("puppeteer", "chrome-devtools-mcp")) {
    $p = Join-Path $HOME ".cache\$t"
    $c = Co-Bao $p
    if ($c -gt 0) { "    {0,-52} {1,8} MB" -f $t, $c | Write-Host }
}
Write-Host "    (của trình duyệt tự động / MCP, không phải AutoTone hay ToolCloneEvoto)"

# ── torch nằm ở đâu ─────────────────────────────────────────────────────────
#[[ ToolCloneEvoto KHONG co thu muc .venv, tuc no dang chay bang Python he thong.
#   Nghia la torch (ban CUDA, 2.5-4 GB) nam trong site-packages cua Python do —
#   gan nhu chac chan tren o C. Do la mieng lon nhat, nhung DOI CHO NO KHONG
#   PHAI VIEC CUA SCRIPT NAY: xem phan ghi chu cuoi file.
#]]
Write-Host ""
Write-Host "  Python và torch đang nằm ở đâu:" -ForegroundColor Cyan
$dsPy = @()
try { $dsPy += (& py -0p 2>$null | ForEach-Object { ($_ -split '\s{2,}')[-1] }) } catch {}
try { $dsPy += (Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }) } catch {}
#[[ BO CAI STUB CUA MICROSOFT STORE.
#
#   Windows dat san mot file python.exe gia o %LOCALAPPDATA%\Microsoft\
#   WindowsApps. No khong phai Python — chay vao la no in "Python was not
#   found; run without arguments to install from the Microsoft Store" ra
#   STDERR, va PowerShell bien do thanh NativeCommandError do ngau man hinh.
#   Test-Path van thay no ton tai nen loc bang duong dan, khong loc duoc bang
#   cach thu chay.
#]]
$dsPy = $dsPy |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) -and ($_ -notmatch '\\WindowsApps\\') } |
    Select-Object -Unique
if (-not $dsPy) { Write-Host "    (không dò được — bỏ qua)" }
foreach ($py in $dsPy) {
    #[[ Boc try/catch chu khong chi 2>$null: voi $ErrorActionPreference = "Stop",
    #   mot ban Python hong (thieu DLL, bi go do) van nem loi ket lieu va giet
    #   ca script — trong khi day chi la phan BAO CAO, hong mot ban thi bo qua
    #   ban do la du.
    #]]
    try {
        $sp = & $py -c "import site,sys;print(next((p for p in site.getsitepackages() if p.endswith('site-packages')),''))" 2>$null
    } catch { $sp = $null }
    $ct = 0
    if ($sp -and (Test-Path -LiteralPath $sp)) {
        foreach ($g in @("torch", "torchvision", "onnxruntime", "onnxruntime_gpu", "nvidia")) {
            $ct += Co-Bao (Join-Path $sp $g)
        }
    }
    $o = if ($py -like "C:*") { "  <- trên ổ C" } else { "" }
    "    {0,-58} torch+cuda: {1,8} MB{2}" -f $py, [math]::Round($ct, 0), $o | Write-Host
}

if (-not $Chay) {
    Write-Host ""
    Write-Host "  Đây mới chỉ là XEM, chưa đụng gì. Chuyển thật:" -ForegroundColor Yellow
    Write-Host "      .\don_o_c.ps1 -Chay"
    if ($XoaZipThua) {
        Write-Host "  (-XoaZipThua một mình không làm gì — phải đi kèm -Chay.)" -ForegroundColor DarkYellow
    }
    Write-Host ""
    exit 0
}

# ── Phần CHẠY ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  === CHUYỂN THẬT ===" -ForegroundColor Yellow

#[[ File dang bi mo thi robocopy chuyen hut mot phan roi de lai mot mo hon
#   tap: mot nua tren F, mot nua tren C, khong cai nao day du. Chan truoc.
#]]
$dangChay = Get-Process -Name "python", "pythonw", "AutoTone" -ErrorAction SilentlyContinue
if ($dangChay) {
    Write-Host ""
    Write-Host "  [!] Đang có tiến trình giữ mấy file này: " -ForegroundColor Red -NoNewline
    Write-Host (($dangChay | Select-Object -ExpandProperty ProcessName -Unique) -join ", ")
    Write-Host "      Đóng AutoTone và mọi cửa sổ Python lại rồi chạy lại. Chuyển lúc"
    Write-Host "      file đang mở sẽ để lại nửa trên F nửa trên C."
    exit 1
}

New-Item -ItemType Directory -Force -Path $DICH_GOC | Out-Null

foreach ($m in $MUC) {
    $cu = $m.Cu
    $moi = Join-Path $DICH_GOC $m.Moi
    Write-Host ""
    Write-Host "  --- $($m.Ten)"

    if (La-Junction $cu) { Write-Host "      đã là junction rồi, bỏ qua."; continue }
    if (-not (Test-Path -LiteralPath $cu)) { Write-Host "      không có trên máy, bỏ qua."; continue }
    if (Test-Path -LiteralPath $moi) {
        Write-Host "      [!] $moi ĐÃ CÓ SẴN. Dừng để khỏi ghi đè." -ForegroundColor Red
        Write-Host "          Xoá hoặc đổi tên nó rồi chạy lại."
        continue
    }

    Write-Host "      chép sang $moi ..."
    # /MOVE = chép xong thì xoá nguồn. /R:2 /W:2 = thử lại 2 lần, chờ 2 giây.
    #[[ Hung ca 2>&1 vao bien: voi $ErrorActionPreference = "Stop", chu bat ky
    #   dong nao robocopy ghi ra stderr cung co the bi PowerShell 5.1 bien thanh
    #   loi ket lieu, va the la dung giua chung sau khi da chep xong mot nua.
    #]]
    $r = robocopy $cu $moi /E /MOVE /R:2 /W:2 /NFL /NDL /NJH /NJS 2>&1
    # robocopy: 0-7 la thanh cong, >=8 la loi. Khong phai quy uoc thong thuong.
    if ($LASTEXITCODE -ge 8) {
        Write-Host "      [!] robocopy lỗi (mã $LASTEXITCODE). KHÔNG tạo junction." -ForegroundColor Red
        Write-Host "          Dữ liệu vẫn còn, kiểm tra cả hai chỗ trước khi làm tiếp."
        continue
    }

    #[[ Tu day tro di du lieu DA nam tren F. Neu tao junction that bai ma cu de
    #   im lang thi cho cu tren C khong con gi ca, va lan chay sau insightface
    #   se tai lai 630 MB ve dung o C — dung cai minh vua don di. Nen bat loi
    #   va in ra dung cau lenh de lam tay.
    #]]
    try {
        if (Test-Path -LiteralPath $cu) { Remove-Item -LiteralPath $cu -Recurse -Force }
        New-Item -ItemType Junction -Path $cu -Target $moi | Out-Null
        Write-Host "      junction: $cu  ->  $moi" -ForegroundColor Green
    } catch {
        Write-Host "      [!] Dữ liệu đã sang F rồi, NHƯNG không tạo được junction:" -ForegroundColor Red
        Write-Host "          $($_.Exception.Message)"
        Write-Host "          Chạy tay lệnh này rồi kiểm lại:" -ForegroundColor Yellow
        Write-Host "          cmd /c mklink /J `"$cu`" `"$moi`""
        Write-Host "          Chưa làm thì thư viện sẽ tải lại từ đầu về ổ C."
    }
}

if ($XoaZipThua) {
    # Sau khi chuyen, duong dan cu di qua junction nen van tro dung file.
    if ((Test-Path -LiteralPath $zip) -and (Test-Path -LiteralPath $giai)) {
        Remove-Item -LiteralPath $zip -Force
        Write-Host ""
        Write-Host "  Đã xoá buffalo_l.zip (bản giải nén vẫn còn nguyên)." -ForegroundColor Green
    }
}

# ── Kiểm lại: junction có thật sự dùng được không ────────────────────────────
#[[ Tao junction xong ma khong doc thu qua no thi khong biet no co dung khong.
#   Doc DUNG MOT FILE MO HINH qua DUONG DAN CU — do la thu ma thu vien se lam.
#]]
Write-Host ""
Write-Host "  === KIỂM LẠI ===" -ForegroundColor Yellow
$hong = 0
$canDoc = @(
    (Join-Path $HOME ".insightface\models\buffalo_l\det_10g.onnx"),
    (Join-Path $HOME ".cache\skin_spike\resnet34_faceparse.onnx")
)
foreach ($f in $canDoc) {
    if (Test-Path -LiteralPath $f) {
        try {
            $fs = [IO.File]::OpenRead($f); $b = $fs.ReadByte(); $fs.Close()
            $mb = [math]::Round((Get-Item -LiteralPath $f).Length / 1MB, 1)
            Write-Host "    [ĐẠT] đọc được qua đường dẫn cũ: $f ($mb MB)" -ForegroundColor Green
        } catch {
            Write-Host "    [HỎNG] có file nhưng KHÔNG đọc được: $f" -ForegroundColor Red
            $hong++
        }
    } else {
        Write-Host "    [HỎNG] không thấy: $f" -ForegroundColor Red
        $hong++
    }
}

Write-Host ""
Write-Host "  Ổ C còn trống: $(Dia-Trong 'C') GB      Ổ F còn trống: $(Dia-Trong 'F') GB"
Write-Host ""
if ($hong -eq 0) {
    Write-Host "  XONG. Mở ToolCloneEvoto chạy thử một ảnh để chắc chắn." -ForegroundColor Green
} else {
    Write-Host "  $hong CHỖ HỎNG — xem ở trên. Đừng chạy retouch cho tới khi sửa xong." -ForegroundColor Red
}
Write-Host ""

# ── GHI CHÚ: miếng lớn nhất trên ổ C mà script này CỐ Ý không đụng ───────────
#
# ToolCloneEvoto không có thư mục .venv, tức nó đang chạy bằng Python hệ thống.
# Vậy torch (bản CUDA, 2.5-4 GB) đang nằm trong site-packages của Python đó,
# gần như chắc chắn trên ổ C. Đó là miếng lớn hơn hẳn hai thư mục ở trên.
#
# Script này KHÔNG tự đụng vào, vì đổi chỗ torch không phải là chuyển thư mục —
# phải cài lại vào môi trường mới rồi mới gỡ bản cũ, và làm sai thì retouch
# chết hẳn. Muốn làm thì đúng trình tự là:
#
#     cd F:\ToolCloneEvoto
#     python cai_dat.py          # tự tạo .venv NGAY TRONG F:\ToolCloneEvoto
#                                # và cài torch bản CUDA vào đó
#     # chạy thử retouch một ảnh, chắc chắn chạy được, RỒI mới:
#     python -m pip uninstall torch torchvision onnxruntime-gpu
#
# Lệnh uninstall cuối gỡ torch khỏi Python HỆ THỐNG trên ổ C. Chỉ chạy sau khi
# đã xác nhận bản trong .venv chạy được — gỡ trước là retouch chết ngay.
# AutoTone sẽ tự tìm thấy .venv mới (retouch.py có hàm python_venv).
