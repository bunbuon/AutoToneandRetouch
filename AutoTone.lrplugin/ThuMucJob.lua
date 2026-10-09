--[[ THƯ MỤC JOB — một chỗ quyết định, cho mọi file của plugin.

     Mặc định = <thư mục plugin>/jobs (như trước nay). Cố tình KHÔNG dùng
     getStandardFilePath("appData"): tên thư mục chuẩn của Lightroom có thể trỏ
     %APPDATA% trong khi Python hiểu là %LOCALAPPDATA% — lệch một cái là plugin
     không bao giờ thấy job.

     9/10 — PLUGIN TỰ CÀI VÀO THƯ MỤC Modules CỦA LIGHTROOM (user: "có cách nào
     để Lightroom tự động nhận Plugin của Tool khi lần đầu cài Tool xong"): app
     chép plugin vào %APPDATA%\Adobe\Lightroom\Modules (Mac: ~/Library/Application
     Support/Adobe/Lightroom/Modules) — Lightroom tự nạp mọi plugin ở đó lúc khởi
     động, khỏi Plug-in Manager → Add. Nhưng app vẫn đọc / ghi job ở thư mục dữ
     liệu của nó. Nên app ghi kèm `jobs_dir.txt` (một dòng: đường dẫn thư mục job
     thật) vào bản trong Modules; có file đó thì dùng nó. Bản cũ người dùng đã Add
     (không có file trỏ) vẫn dùng jobs/ của chính nó — trùng đúng chỗ đó.

     File nhỏ, KHÔNG require gì của plugin: BatDuongDan.lua (chạy trong hộp thoại
     Export) và Init.lua (trước khi nạp AutoToneCore) gọi được mà không kéo theo
     lỗi của file khác. ]]

local LrPathUtils = import "LrPathUtils"

local M = {}
M.TEN_TRO = "jobs_dir.txt"

local daDoc, troDen = false, nil

--[[ Đọc file trỏ MỘT lần mỗi lần nạp plugin (Reload / mở Lightroom là đọc lại).
     Dòng trống / không đọc được -> coi như không có. ]]
function M.doc(goc)
    local f = io.open(LrPathUtils.child(goc, M.TEN_TRO), "r")
    if not f then return nil end
    local d = f:read("*l")
    f:close()
    if not d then return nil end
    d = string.gsub(d, "^\239\187\191", "")          -- BOM UTF-8 (nếu có)
    d = string.gsub(d, "^%s*(.-)%s*$", "%1")
    if d == "" then return nil end
    return d
end

function M.jobDir()
    if not daDoc then
        daDoc = true
        troDen = M.doc(_PLUGIN.path)
    end
    return troDen or LrPathUtils.child(_PLUGIN.path, "jobs")
end

return M
