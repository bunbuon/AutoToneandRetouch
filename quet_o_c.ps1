# quet_o_c.ps1 — Tìm xem ổ C đang bị cái gì chiếm, KHÔNG đoán trước.
#
#   .\quet_o_c.ps1              <- quét, in bảng xếp hạng
#   .\quet_o_c.ps1 -Sau 20      <- lấy 20 dòng đầu thay vì 25
#   .\quet_o_c.ps1 -Nhanh       <- chỉ quét thư mục người dùng (nhanh hơn nhiều)
#
# VÌ SAO CÓ FILE NÀY, TRONG KHI ĐÃ CÓ don_o_c.ps1
#     don_o_c.ps1 chỉ nhìn đúng những chỗ tôi ĐOÁN TRƯỚC là thủ phạm:
#     .insightface, skin_spike, torch, puppeteer. Đoán đúng thì tốt, đoán thiếu
#     thì nó im lặng báo "xong rồi" trong khi ổ C vẫn đầy — và đó đúng là chuyện
#     vừa xảy ra.
#
#     File này không đoán gì cả: nó đo mọi thư mục con và xếp hạng theo dung
#     lượng. Thủ phạm tự lộ ra, kể cả khi nó là thứ chẳng liên quan gì tới hai
#     dự án.
#
# BẪY: JUNCTION
#     Sau khi dọn, C:\Users\ipmac\.insightface đã là JUNCTION trỏ sang ổ F.
#     Đi xuyên qua nó mà đếm thì 630 MB nằm trên F lại bị tính vào ổ C, và bảng
#     xếp hạng sẽ chỉ thẳng vào một thư mục đã dọn xong. Nên mọi reparse point
#     đều bị BỎ QUA và đánh dấu riêng — xem $bo_qua.
#
# CHẠY: bấm đúp DON_O_C.bat rồi chọn 8. Hoặc:
#     powershell -NoProfile -ExecutionPolicy Bypass -File .\quet_o_c.ps1

param(
    [int]$Sau = 25,
    [switch]$Nhanh
)

$ErrorActionPreference = "Stop"

#[[ Quet o muc THU MUC CON CAP 1-2, khong quet tung file tu goc C:.
#   Quet het o C mat hang chuc phut va phan lon la file he thong khong dong
#   duoc. May cho duoi day la noi 99% dung luong "tu nhien phinh ra" nam.
#]]
$GOC = @(
    "$HOME\AppData\Local",
    "$HOME\AppData\Roaming",
    "$HOME\AppData\LocalLow",
    "$HOME\Downloads",
    "$HOME\Documents",
    "$HOME\Desktop",
    "$HOME\Videos",
    "$HOME\Music",
    "$HOME\Pictures"
)
if (-not $Nhanh) {
    $GOC += @("C:\ProgramData", "C:\Program Files", "C:\Program Files (x86)",
              "C:\Windows\Temp", "C:\Windows\SoftwareDistribution", "C:\Temp")
}

$bo_qua = New-Object System.Collections.ArrayList

function La-Reparse($p) {
    try {
        $i = Get-Item -LiteralPath $p -Force -ErrorAction Stop
        return [bool]($i.Attributes -band [IO.FileAttributes]::ReparsePoint)
    } catch { return $false }
}

function Co-MB($p) {
    #[[ -Recurse cua PowerShell KHONG di xuyen junction, nhung chinh thu muc
    #   duoc truyen vao thi van bi doc. Nen chan o day, truoc khi doc.
    #]]
    if (La-Reparse $p) {
        [void]$bo_qua.Add($p)
        return -1
    }
    try {
        $t = Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue |
             Measure-Object -Property Length -Sum
        if ($null -eq $t.Sum) { return 0 }
        return [math]::Round($t.Sum / 1MB, 0)
    } catch { return 0 }
}

function Dia($o) {
    $d = Get-PSDrive -Name $o -ErrorAction SilentlyContinue
    if (-not $d) { return $null }
    return @{ Trong = [math]::Round($d.Free / 1GB, 1)
              Tong  = [math]::Round(($d.Free + $d.Used) / 1GB, 1) }
}

$c = Dia 'C'
Write-Host ""
Write-Host "  Ổ C: còn trống $($c.Trong) / $($c.Tong) GB" -ForegroundColor Cyan
Write-Host "  Đang quét... (1-4 phút, tuỳ ổ đĩa)"
Write-Host ""

$ket = New-Object System.Collections.ArrayList
foreach ($g in $GOC) {
    if (-not (Test-Path -LiteralPath $g)) { continue }
    $con = @()
    try {
        $con = Get-ChildItem -LiteralPath $g -Directory -Force -ErrorAction SilentlyContinue
    } catch {}
    foreach ($d in $con) {
        $mb = Co-MB $d.FullName
        if ($mb -gt 20) {
            [void]$ket.Add([pscustomobject]@{ MB = $mb; Duong = $d.FullName })
        }
    }
    #[[ File nam THANG trong thu muc goc (khong trong thu muc con nao) cung
    #   phai tinh — vi du mot file .iso 6 GB nam tho lo trong Downloads se khong
    #   bao gio hien ra neu chi duyet thu muc con.
    #]]
    try {
        $le = Get-ChildItem -LiteralPath $g -File -Force -ErrorAction SilentlyContinue |
              Where-Object { $_.Length -gt 200MB }
        foreach ($f in $le) {
            [void]$ket.Add([pscustomobject]@{
                MB = [math]::Round($f.Length / 1MB, 0); Duong = $f.FullName })
        }
    } catch {}
}

$top = $ket | Sort-Object MB -Descending | Select-Object -First $Sau
Write-Host "  CHIẾM NHIỀU NHẤT TRÊN Ổ C:" -ForegroundColor Cyan
Write-Host ""
foreach ($r in $top) {
    $d = $r.Duong
    if ($d.Length -gt 68) { $d = "..." + $d.Substring($d.Length - 65) }
    $mau = if ($r.MB -ge 1000) { "Yellow" } else { "Gray" }
    Write-Host ("    {0,8:N0} MB   {1}" -f $r.MB, $d) -ForegroundColor $mau
}

$tong = ($ket | Measure-Object MB -Sum).Sum
Write-Host ""
Write-Host ("    {0,8:N0} MB   = tổng mọi thứ đo được ({1} mục)" -f $tong, $ket.Count)

# ── Mấy chỗ luôn đáng nhìn riêng ────────────────────────────────────────────
Write-Host ""
Write-Host "  MẤY CHỖ HAY PHÌNH MÀ ÍT AI NGHĨ TỚI:" -ForegroundColor Cyan
$rieng = @(
    @{ T = "Thư mục tạm (%TEMP%)";        P = $env:TEMP }
    @{ T = "Cache pip";                   P = "$HOME\AppData\Local\pip\Cache" }
    @{ T = "Windows Update đã tải";       P = "C:\Windows\SoftwareDistribution\Download" }
    @{ T = "Thùng rác";                   P = "C:\`$Recycle.Bin" }
    @{ T = "Dữ liệu AutoTone (bản .exe)"; P = "$HOME\AppData\Local\AutoTone" }
)
foreach ($r in $rieng) {
    if (Test-Path -LiteralPath $r.P) {
        $mb = Co-MB $r.P
        $s = if ($mb -lt 0) { "junction — đã trỏ sang ổ khác" } else { "{0:N0} MB" -f $mb }
        "    {0,-30} {1}" -f $r.T, $s | Write-Host
    }
}

# torch nằm ở đâu
Write-Host ""
Write-Host "  torch:" -ForegroundColor Cyan
$dsPy = @()
try { $dsPy += (& py -0p 2>$null | ForEach-Object { ($_ -split '\s{2,}')[-1] }) } catch {}
try { $dsPy += (Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }) } catch {}
$dsPy += "F:\ToolCloneEvoto\.venv\Scripts\python.exe"
$dsPy = $dsPy | Where-Object {
    $_ -and (Test-Path -LiteralPath $_) -and ($_ -notmatch '\\WindowsApps\\')
} | Select-Object -Unique
foreach ($py in $dsPy) {
    try {
        $sp = & $py -c "import site;print(next((p for p in site.getsitepackages() if p.endswith('site-packages')),''))" 2>$null
    } catch { $sp = $null }
    $t = 0
    if ($sp -and (Test-Path -LiteralPath $sp)) {
        foreach ($g in @("torch", "torchvision", "onnxruntime", "onnxruntime_gpu", "nvidia")) {
            $m = Co-MB (Join-Path $sp $g); if ($m -gt 0) { $t += $m }
        }
    }
    $o = if ($py -like "C:*") { "  <- TRÊN Ổ C" } else { "  (ngoài ổ C)" }
    "    {0,-56} {1,7:N0} MB{2}" -f $py, $t, $o | Write-Host
}

if ($bo_qua.Count) {
    Write-Host ""
    Write-Host "  Đã bỏ qua (junction, dữ liệu thật nằm ổ khác nên không tính vào C):" -ForegroundColor DarkGray
    foreach ($p in ($bo_qua | Select-Object -Unique)) { Write-Host "    $p" -ForegroundColor DarkGray }
}

Write-Host ""
Write-Host "  Gửi bảng này lại là biết dọn tiếp chỗ nào." -ForegroundColor Yellow
Write-Host ""
