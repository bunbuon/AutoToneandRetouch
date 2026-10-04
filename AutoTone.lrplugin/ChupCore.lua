--[[ ChupCore.lua — CHỤP NGUYÊN TRẠNG thông số develop của cả một thư mục.

     VÌ SAO CÓ FILE NÀY (29/9)
     Người dùng sửa tay xong bộ 2609 (3811 ảnh) và muốn giữ lại bản đó làm
     "đáp án" để dạy tool cân WB: chạy lại tool, rồi so từng ảnh với bản đã sửa.

     Bản xuất có sẵn (export_*.tsv của AutoToneCore) KHÔNG dùng được cho việc này:
       - chỉ có 7 trường (Exposure, Highlights, Shadows, Temperature, Tint,
         AsShot*) — thiếu WhiteBalance, HSL, Color Grading, Calibration... là
         những thứ người dùng thực sự đã chỉnh khi cân màu;
       - nó tự xoá bản cũ mỗi lần xuất mới, và app xuất lại mỗi lần bấm Phân
         tích — tức "đáp án" sẽ mất ngay lần chạy tool kế tiếp.

     Nên bản chụp này:
       - lấy TOÀN BỘ getDevelopSettings() của từng ảnh, kể cả bảng lồng nhau
         (đường cong...), ghi thành JSON — đủ để dựng lại ảnh nếu cần;
       - ghi vào NGAY THƯ MỤC ẢNH, tên có ngày giờ, không bao giờ bị xoá;
       - lấy CẢ ảnh 1 sao (cột Rating để bên đọc tự lọc) — đây là bản sao lưu,
         không phải dữ liệu học, bỏ bớt thì không khôi phục được.

     CHỈ ĐỌC. Không một lời gọi nào ghi vào catalog.

     Nạp riêng như XuatCore/DuyetCore: hỏng ở đây thì mất bản chụp, không mất
     đường ghi màu.

     YÊU CẦU: jobs/request_chup.txt
         dòng 1: thư mục ảnh (như Lightroom thấy)
         dòng 2: (tuỳ chọn) thư mục ghi bản chụp — mặc định chính thư mục ảnh
     KẾT QUẢ: <thư mục ghi>/_autotone_da_sua_YYYYmmdd_HHMMSS.tsv
              jobs/chup_xong.txt   "<đường dẫn file>\t<số ảnh>"  hoặc  "LOI\t<lý do>"
]]

local LrApplication = import "LrApplication"
local LrFileUtils   = import "LrFileUtils"
local LrPathUtils   = import "LrPathUtils"
local LrTasks       = import "LrTasks"

local Core = require "AutoToneCore"

local M = {}
M.YEU_CAU = "request_chup.txt"
M.XONG    = "chup_xong.txt"
M.LO      = 200
M.TIEN_TO = "_autotone_da_sua_"

--[[ JSON tối giản, đủ cho getDevelopSettings(): số, chuỗi, bool, bảng.

     Bảng có khoá 1..n liền nhau -> mảng; còn lại -> đối tượng, khoá SẮP XẾP
     để hai lần chụp cùng một ảnh ra đúng cùng một dòng (so được bằng mắt).
     NaN/vô cực không có trong JSON -> null. Kiểu lạ (userdata, hàm) -> null
     chứ không làm hỏng cả dòng. ]]
local function chuoi(s)
    s = string.gsub(s, '[%c"\\]', function(c)
        if c == '"' then return '\\"' end
        if c == "\\" then return "\\\\" end
        if c == "\n" then return "\\n" end
        if c == "\r" then return "\\r" end
        if c == "\t" then return "\\t" end
        return string.format("\\u%04x", string.byte(c))
    end)
    return '"' .. s .. '"'
end

local function laMang(t)
    local n = 0
    for k in pairs(t) do
        if type(k) ~= "number" or k < 1 or math.floor(k) ~= k then return false end
        n = n + 1
    end
    for i = 1, n do
        if t[i] == nil then return false end
    end
    return true, n
end

function M.json(v, sau)
    sau = (sau or 0) + 1
    local t = type(v)
    if t == "nil" then return "null" end
    if t == "boolean" then return v and "true" or "false" end
    if t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        return string.format("%.14g", v)
    end
    if t == "string" then return chuoi(v) end
    if t ~= "table" or sau > 8 then return "null" end
    local mang, n = laMang(v)
    local ra = {}
    if mang and n > 0 then
        for i = 1, n do ra[i] = M.json(v[i], sau) end
        return "[" .. table.concat(ra, ",") .. "]"
    end
    local khoa = {}
    for k in pairs(v) do khoa[#khoa + 1] = k end
    table.sort(khoa, function(a, b) return tostring(a) < tostring(b) end)
    for _, k in ipairs(khoa) do
        ra[#ra + 1] = chuoi(tostring(k)) .. ":" .. M.json(v[k], sau)
    end
    return "{" .. table.concat(ra, ",") .. "}"
end

local function ghiXong(noi_dung)
    local p = LrPathUtils.child(Core.jobDir(), M.XONG)
    local f = io.open(p .. ".part", "w")
    if not f then return end
    f:write(noi_dung .. "\n")
    f:close()
    Core.try("chupXong", function()
        LrFileUtils.delete(p)
        LrFileUtils.move(p .. ".part", p)
    end)
end

--[[ Ghi bản chụp. Trả về (số ảnh, đường dẫn) hoặc (0, nil, lý do). ]]
function M.chup(catalog, photos, dich)
    if not photos or #photos == 0 then return 0, nil, "khong co anh nao" end
    if not LrFileUtils.exists(dich) then
        LrFileUtils.createAllDirectories(dich)
    end
    local dest = LrPathUtils.child(dich, M.TIEN_TO .. os.date("%Y%m%d_%H%M%S") .. ".tsv")
    local fh, err = io.open(dest .. ".part", "w")
    if not fh then return 0, nil, "khong mo duoc file: " .. tostring(err) end
    fh:write("path\tRating\tsettings\n")

    -- Thu mot anh de biet co phai boc read-access khong (y het writeExport)
    local truc = Core.try("chupProbe", function()
        return photos[1]:getDevelopSettings()
    end)
    local canDoc = type(truc) ~= "table"

    local n, hong = 0, 0
    local function mot_lo(tu, den)
        for i = tu, den do
            local p = photos[i]
            local path = p:getRawMetadata("path")
            local sao = tonumber(p:getRawMetadata("rating")) or 0
            local s = p:getDevelopSettings()
            if path and path ~= "" and type(s) == "table" then
                fh:write(path .. "\t" .. tostring(sao) .. "\t" .. M.json(s) .. "\n")
                n = n + 1
            else
                hong = hong + 1
            end
        end
    end

    local i = 1
    while i <= #photos do
        local het = math.min(i + M.LO - 1, #photos)
        if canDoc then
            catalog:withReadAccessDo(function() mot_lo(i, het) end)
        else
            mot_lo(i, het)
        end
        LrTasks.yield()
        i = het + 1
    end
    fh:close()

    if n == 0 then
        LrFileUtils.delete(dest .. ".part")
        return 0, nil, string.format("%d anh khong doc duoc thong so", hong)
    end
    LrFileUtils.move(dest .. ".part", dest)
    if not LrFileUtils.exists(dest) then
        return 0, nil, "khong doi ten duoc file .part"
    end
    return n, dest, nil, hong
end

--[[ Vòng lặp nền gọi hàm này mỗi 5 giây. Không có yêu cầu thì về ngay. ]]
function M.runRequest()
    local req = LrPathUtils.child(Core.jobDir(), M.YEU_CAU)
    if not LrFileUtils.exists(req) then return 0 end
    local claimed = Core.claim(req)
    if not claimed then return 0 end

    local thu_muc, dich
    local fh = io.open(claimed, "r")
    if fh then
        thu_muc = fh:read("*l")
        dich = fh:read("*l")
        fh:close()
    end
    Core.try("chupBoYeuCau", function() LrFileUtils.delete(claimed) end)

    local function gon(s)
        if not s then return nil end
        s = string.gsub(s, "^%s*(.-)%s*$", "%1")
        -- BOM UTF-8 o dau file do Notepad / PowerShell ghi
        s = string.gsub(s, "^\239\187\191", "")
        if s == "" then return nil end
        return s
    end
    thu_muc, dich = gon(thu_muc), gon(dich)
    if not thu_muc then
        Core.log("chup: yeu cau thieu thu muc")
        ghiXong("LOI\tyeu cau thieu thu muc")
        return 0
    end
    dich = dich or thu_muc

    local catalog = LrApplication.activeCatalog()
    local photos, cach = Core.photosInFolder(catalog, thu_muc)
    if not photos or #photos == 0 then
        Core.log("chup: khong thay anh nao trong " .. thu_muc)
        ghiXong("LOI\tkhong thay anh nao trong catalog o " .. thu_muc)
        return 0
    end
    local n, dest, err, hong = M.chup(catalog, photos, dich)
    if err then
        Core.log("chup LOI: " .. tostring(err))
        ghiXong("LOI\t" .. tostring(err))
        return 0
    end
    Core.log(string.format("chup nguyen trang %d anh (%s)%s -> %s", n, cach,
             (hong or 0) > 0 and string.format(", %d anh doc hong", hong) or "", dest))
    ghiXong(dest .. "\t" .. tostring(n))
    return n
end

return M
