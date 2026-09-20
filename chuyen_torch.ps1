# chuyen_torch.ps1 — Đưa torch (~3 GB) khỏi Python hệ thống trên ổ C
#
#   .\chuyen_torch.ps1          <- xem đang ở bước nào, không đụng gì
#   .\chuyen_torch.ps1 -Buoc1   <- tạo .venv trên F và cài torch vào đó
#   .\chuyen_torch.ps1 -Buoc2   <- KIỂM: retouch có thật sự chạy bằng .venv không
#   .\chuyen_torch.ps1 -Buoc3   <- gỡ torch khỏi Python trên C + dọn cache pip
#
# VÌ SAO CHIA BA BƯỚC THAY VÌ MỘT NÚT
#     Bước 3 là bước KHÔNG LÙI ĐƯỢC nếu bước 1 chưa xong hẳn: gỡ torch khỏi
#     Python hệ thống mà bản trong .venv lại thiếu một gói nào đó thì retouch
#     chết hẳn, và cài lại mất thêm 2.5 GB tải về nữa.
#     Nên bước 2 phải ĐẠT rồi mới được chạy bước 3. Script tự chặn: bước 3 từ
#     chối chạy nếu bước 2 chưa từng đạt.
#
# MỘT CÁI BẪY CỦA CHÍNH VIỆC NÀY
#     retouch.py chọn Python theo thứ tự: có .venv thì dùng .venv, không thì
#     dùng python hệ thống. Nghĩa là NGAY KHI thư mục .venv xuất hiện, AutoTone
#     đã chuyển sang dùng nó — kể cả lúc nó mới cài được một nửa. Đó chính là
#     lý do bước 2 tồn tại, và vì sao nó gọi thẳng retouch.kiem_tra() của app
#     chứ không tự nghĩ ra một phép thử riêng.

param(
    [switch]$Buoc1,
    [switch]$Buoc2,
    [switch]$Buoc3,
    [string]$Tool = "F:\ToolCloneEvoto",
    [string]$App  = "F:\Claude AI\AutoToneImages"
)

$ErrorActionPreference = "Stop"
$TOOL = $Tool
$APP  = $App
#[[ Noi chuoi chu khong dung Join-Path.
#
#   Join-Path GIAI QUYET O DIA: neu o F chua gan (rut o ngoai, doi ten o) thi no
#   nem "Cannot find drive" ngay tu dong khai bao — truoc ca khi script kip in ra
#   mot cau nao de nguoi doc hieu chuyen gi. Noi chuoi thi khong dong toi dia, va
#   phep kiem ngay ben duoi bao dung van de.
#]]
$VENV   = "$TOOL\.venv\Scripts\python.exe"
$DAU_OK = "$TOOL\.venv\DA_KIEM_DAT.txt"

foreach ($d in @($TOOL, $APP)) {
    if (-not (Test-Path -LiteralPath $d)) {
        Write-Host ""
        Write-Host "  [!] Không thấy thư mục: $d" -ForegroundColor Red
        Write-Host "      Ổ đĩa chưa gắn, hay thư mục đã đổi chỗ?"
        Write-Host "      Chỉ rõ được bằng:  -Tool `"D:\ToolCloneEvoto`" -App `"D:\AutoToneImages`""
        Write-Host ""
        exit 1
    }
}

function Dia-Trong($o) {
    $d = Get-PSDrive -Name $o -ErrorAction SilentlyContinue
    if (-not $d) { return 0 }
    return [math]::Round($d.Free / 1GB, 1)
}

function Co-Bao($p) {
    if (-not (Test-Path -LiteralPath $p)) { return 0 }
    $t = Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue |
         Measure-Object -Property Length -Sum
    if ($null -eq $t.Sum) { return 0 }
    return [math]::Round($t.Sum / 1MB, 0)
}

function Python-He-Thong {
    #[[ Loc bo stub cua Microsoft Store o WindowsApps: no khong phai Python, chay
    #   vao la in "Python was not found..." ra stderr.
    #]]
    $ds = @()
    try { $ds += (& py -0p 2>$null | ForEach-Object { ($_ -split '\s{2,}')[-1] }) } catch {}
    try { $ds += (Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }) } catch {}
    $ds = $ds | Where-Object {
        $_ -and (Test-Path -LiteralPath $_) -and
        ($_ -notmatch '\\WindowsApps\\') -and ($_ -notmatch '\\\.venv\\')
    } | Select-Object -Unique
    return ($ds | Select-Object -First 1)
}

function Torch-O-Dau($py) {
    if (-not $py) { return 0 }
    try {
        $sp = & $py -c "import site;print(next((p for p in site.getsitepackages() if p.endswith('site-packages')),''))" 2>$null
    } catch { return 0 }
    if (-not $sp -or -not (Test-Path -LiteralPath $sp)) { return 0 }
    $t = 0
    foreach ($g in @("torch", "torchvision", "onnxruntime", "onnxruntime_gpu", "nvidia")) {
        $t += Co-Bao (Join-Path $sp $g)
    }
    return $t
}

# ── Trạng thái ──────────────────────────────────────────────────────────────
$pyHe = Python-He-Thong
Write-Host ""
Write-Host "  Ổ C còn trống: $(Dia-Trong 'C') GB      Ổ F còn trống: $(Dia-Trong 'F') GB"
Write-Host ""
Write-Host "  Python hệ thống : $(if ($pyHe) { $pyHe } else { 'không dò được' })"
Write-Host "  torch ở đó      : $(Torch-O-Dau $pyHe) MB"
Write-Host "  .venv trên F    : $(if (Test-Path -LiteralPath $VENV) { "có — torch $(Torch-O-Dau $VENV) MB" } else { 'chưa có' })"
Write-Host "  Bước 2 đã đạt   : $(if (Test-Path -LiteralPath $DAU_OK) { 'rồi' } else { 'chưa' })"

if (-not ($Buoc1 -or $Buoc2 -or $Buoc3)) {
    Write-Host ""
    if (-not (Test-Path -LiteralPath $VENV))        { Write-Host "  Bước tiếp theo: -Buoc1" -ForegroundColor Yellow }
    elseif (-not (Test-Path -LiteralPath $DAU_OK))  { Write-Host "  Bước tiếp theo: -Buoc2" -ForegroundColor Yellow }
    else                                            { Write-Host "  Bước tiếp theo: -Buoc3" -ForegroundColor Yellow }
    Write-Host ""
    exit 0
}

# ── BƯỚC 1: cài torch vào .venv trên F ──────────────────────────────────────
if ($Buoc1) {
    Write-Host ""
    Write-Host "  === BƯỚC 1: cài torch vào .venv trên F ===" -ForegroundColor Yellow

    if (-not (Test-Path -LiteralPath (Join-Path $TOOL "cai_dat.py"))) {
        Write-Host "  [!] Không thấy $TOOL\cai_dat.py" -ForegroundColor Red; exit 1
    }
    if (-not $pyHe) {
        Write-Host "  [!] Không dò được Python hệ thống để tạo .venv." -ForegroundColor Red; exit 1
    }
    if ((Dia-Trong 'F') -lt 10) {
        Write-Host "  [!] Ổ F chỉ còn $(Dia-Trong 'F') GB. Cần ít nhất 10 GB (torch ~3 GB" -ForegroundColor Red
        Write-Host "      cộng chỗ giải nén tạm). Dọn bớt F rồi chạy lại."; exit 1
    }
    $dang = Get-Process -Name "python", "pythonw", "AutoTone" -ErrorAction SilentlyContinue
    if ($dang) {
        Write-Host "  [!] Đóng AutoTone và các cửa sổ Python lại trước đã." -ForegroundColor Red; exit 1
    }

    #[[ Day cache VA thu muc tam cua pip sang F trong luc cai.
    #
    #   Mac dinh pip tai file .whl ve %LOCALAPPDATA%\pip\Cache va GIAI NEN o
    #   %TEMP% — ca hai deu tren o C. Banh torch nang ~2.5 GB, nen neu khong doi
    #   thi giua chung o C phong len khoang 5 GB, dung cai ma minh dang co don.
    #]]
    $tam = Join-Path $TOOL ".pip_tam"
    New-Item -ItemType Directory -Force -Path $tam | Out-Null
    $cu = @{ PIP_CACHE_DIR = $env:PIP_CACHE_DIR; TMP = $env:TMP; TEMP = $env:TEMP }
    $env:PIP_CACHE_DIR = Join-Path $tam "cache"
    $env:TMP  = $tam
    $env:TEMP = $tam
    Write-Host "  (cache và thư mục tạm của pip tạm đặt ở $tam để ổ C không phồng lên)"
    Write-Host ""

    try {
        Push-Location $TOOL
        & $pyHe "cai_dat.py"
        $ma = $LASTEXITCODE
    } finally {
        Pop-Location
        $env:PIP_CACHE_DIR = $cu.PIP_CACHE_DIR
        $env:TMP  = $cu.TMP
        $env:TEMP = $cu.TEMP
    }

    Write-Host ""
    if ($ma -ne 0 -or -not (Test-Path -LiteralPath $VENV)) {
        Write-Host "  [!] cai_dat.py chưa xong (mã $ma). KHÔNG chạy bước 3." -ForegroundColor Red
        Write-Host "      Python trên C vẫn còn nguyên torch nên retouch vẫn chạy được"
        Write-Host "      bằng đường cũ — trừ khi thư mục .venv đã hình thành: xem cảnh"
        Write-Host "      báo ở đầu file này."
        exit 1
    }
    Remove-Item -LiteralPath $tam -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  Xong bước 1. torch trong .venv: $(Torch-O-Dau $VENV) MB" -ForegroundColor Green
    Write-Host "  Tiếp:  .\chuyen_torch.ps1 -Buoc2" -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

# ── BƯỚC 2: kiểm bằng chính hàm app dùng ────────────────────────────────────
if ($Buoc2) {
    Write-Host ""
    Write-Host "  === BƯỚC 2: kiểm retouch chạy được bằng .venv chưa ===" -ForegroundColor Yellow
    if (-not (Test-Path -LiteralPath $VENV)) {
        Write-Host "  [!] Chưa có .venv. Chạy -Buoc1 trước." -ForegroundColor Red; exit 1
    }

    #[[ Goi THANG retouch.kiem_tra() cua app chu khong tu nghi ra phep thu rieng.
    #   kiem_tra() chay han mot tien trinh con de BIET thieu goi nao, va no la
    #   dung cai ma nut Retouch trong AutoTone dung de quyet dinh chay hay khong.
    #   Tu viet mot phep thu khac o day thi co the "dat" trong khi app van bao
    #   chua san sang — kiem mot dang, chay mot neo.
    #]]
    $ma_py = @"
import sys
sys.path.insert(0, r'$APP')
import retouch
print('PYTHON CHON:', retouch.python_cho(r'$TOOL'))
ok, mo = retouch.kiem_tra(r'$TOOL', 300)
print('KET QUA:', 'DAT' if ok else 'HONG')
print(mo)
sys.exit(0 if ok else 1)
"@
    $f = Join-Path $env:TEMP "kiem_retouch_$PID.py"
    Set-Content -LiteralPath $f -Value $ma_py -Encoding UTF8
    try {
        & $pyHe $f
        $ma = $LASTEXITCODE
    } finally {
        Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    if ($ma -eq 0) {
        Set-Content -LiteralPath $DAU_OK -Value (Get-Date -Format "o") -Encoding UTF8
        Write-Host "  ĐẠT. Giờ mới được chạy bước 3." -ForegroundColor Green
        Write-Host "  Nên chạy thêm retouch một buổi ảnh thật cho chắc, rồi:" -ForegroundColor Yellow
        Write-Host "      .\chuyen_torch.ps1 -Buoc3"
    } else {
        Remove-Item -LiteralPath $DAU_OK -Force -ErrorAction SilentlyContinue
        Write-Host "  HỎNG — xem mô tả ở trên, nó nói đúng tên gói còn thiếu." -ForegroundColor Red
        Write-Host "  TUYỆT ĐỐI chưa chạy bước 3. Cách lùi lại nhanh nhất nếu cần dùng" -ForegroundColor Red
        Write-Host "  retouch ngay: đổi tên thư mục $TOOL\.venv thành .venv_hong —"
        Write-Host "  AutoTone sẽ quay lại dùng Python hệ thống như trước."
    }
    Write-Host ""
    exit $ma
}

# ── BƯỚC 3: gỡ khỏi ổ C ─────────────────────────────────────────────────────
if ($Buoc3) {
    Write-Host ""
    Write-Host "  === BƯỚC 3: gỡ torch khỏi Python trên ổ C ===" -ForegroundColor Yellow
    if (-not (Test-Path -LiteralPath $DAU_OK)) {
        Write-Host "  [!] Bước 2 chưa đạt. Từ chối chạy." -ForegroundColor Red
        Write-Host "      Gỡ torch lúc bản trên F chưa chắc chạy được là retouch chết hẳn."
        Write-Host "      Chạy:  .\chuyen_torch.ps1 -Buoc2"
        exit 1
    }
    if (-not $pyHe) { Write-Host "  [!] Không dò được Python hệ thống." -ForegroundColor Red; exit 1 }
    $dang = Get-Process -Name "python", "pythonw", "AutoTone" -ErrorAction SilentlyContinue
    if ($dang) { Write-Host "  [!] Đóng AutoTone và các cửa sổ Python lại trước đã." -ForegroundColor Red; exit 1 }

    $truoc = Dia-Trong 'C'
    Write-Host "  Gỡ khỏi: $pyHe"
    Write-Host ""
    & $pyHe -m pip uninstall -y torch torchvision onnxruntime onnxruntime-gpu
    Write-Host ""
    Write-Host "  Dọn cache pip (chỉ là bản tải về để cài lại cho nhanh, xoá vô hại)"
    & $pyHe -m pip cache purge

    Write-Host ""
    Write-Host "  Ổ C: $truoc GB -> $(Dia-Trong 'C') GB" -ForegroundColor Green
    Write-Host "  torch còn lại trên C: $(Torch-O-Dau $pyHe) MB"
    Write-Host "  torch trong .venv trên F: $(Torch-O-Dau $VENV) MB"
    Write-Host ""
    Write-Host "  Mở AutoTone bấm Retouch một buổi ảnh để chắc chắn." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}
