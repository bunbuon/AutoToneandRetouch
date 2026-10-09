--[[ XemPresetCore.lua — XEM TRƯỚC PRESET LIGHTROOM cho CẢ LƯỚI ẢNH (9/10).

     User 9/10: "Thêm tính năng lấy ra Preset và khi chọn Preset thì sẽ load
     lại Preview với preset đã chọn cho toàn bộ ảnh preview" (kèm ảnh mẫu NEXUS
     AI Retouch: ô "Preset Lightroom" + "Xem trước bằng Lightroom").

     HAI VIỆC
       1. DANH SÁCH PRESET: LrApplication.developPresetFolders() -> jobs/
          lr_presets.tsv (uuid, tên, nhóm, thư mục). Chỉ ghi lại khi danh sách
          đổi (thêm / xoá / đổi tên preset trong Lightroom). App còn tự quét file
          .xmp nên có danh sách cả khi Lightroom chưa mở; bản này là bản chuẩn
          (đúng tên nhóm Lightroom hiện, có cả preset cài cùng Lightroom).
       2. RENDER THEO PRESET: SDK KHÔNG có cách render một ảnh "như thể đã áp
          preset" mà không đụng vào ảnh. Nên — y như NEXUS làm cho ảnh đang xem,
          ở đây cho cả danh sách, từng LÔ NHỎ:
              chụp thông số develop hiện tại của lô
              -> ghi SỔ KHÔI PHỤC (jobs/xempreset_khoiphuc.json)
              -> áp preset TẠM
              -> LrExportSession render JPEG (cùng thông số với ảnh duyệt)
              -> TRẢ LẠI nguyên thông số cũ, đọc lại so từng khoá quan trọng
              -> xoá sổ khôi phục.
          Lightroom tắt / máy sập giữa lô: lần nạp plugin sau, khoiPhuc() đọc
          sổ và trả lại trước khi làm gì khác. Máy này từng BSOD giữa lúc xuất
          (xem bộ nhớ dự án) — sổ này không phải phòng xa suông.

     BẪY ĐÃ BIẾT KHI TRẢ LẠI (học từ plugin NEXUS, họ đã đo):
       - CameraProfile / Look phải áp RIÊNG một lần nữa mới về đúng như cũ.
       - Ảnh RAW đang "As Shot" không có Temperature trong getDevelopSettings().
         Trả lại {WhiteBalance="As Shot"} bằng applyDevelopSettings KHÔNG xoá
         Kelvin của preset — Lightroom vẫn render theo Kelvin đó. Ở đây trả WB
         bằng một preset của plugin (addDevelopPresetForPlugin, chỉ có
         WhiteBalance) — đi đúng đường áp preset của Lightroom; rồi ĐỌC LẠI:
         lệch thì đếm "lech", ghi plugin.log, app báo người dùng.
       - Preset có mask / chỉnh cục bộ (preset Adaptive của Adobe...): trả lại
         bằng thông số không chắc gỡ được mask -> TỪ CHỐI xem tạm.
     Lịch sử chỉnh (History) của ảnh có thêm hai bước mỗi lần xem — Lightroom
     không có API xoá lịch sử.

     KHÔNG giữ vòng lặp quá lâu: mỗi lần Init gọi chỉ làm tới GIAY_MOI_LUOT giây
     rồi trả về — job áp màu / xuất ảnh / duyệt vẫn được phục vụ xen giữa. Yêu
     cầu MỚI (người dùng chọn preset khác) thay lượt đang dở ngay giữa hai lô.

     YÊU CẦU  jobs/request_xempreset.txt (app ghi, UTF-8):
         id=<số>  uuid=<uuid preset>  ten=<tên>  nhom=<nhóm>  dest=<thư mục ra>
         canh=1600  chat=0.8  ap=0|1  (1 = ÁP HẲN, không trả lại)
         ---
         <đường dẫn ảnh, mỗi dòng một tấm, theo thứ tự ưu tiên>
     DỪNG     jobs/request_xempreset_dung.txt
     TIẾN ĐỘ  jobs/xempreset_tiendo.txt   key=value: id trang_thai xong tong
              thieu lech dest thong_bao
     BẢNG     jobs/xempreset_anh.tsv      <ảnh gốc>\t<jpg>  (cả lượt, ghi lại mỗi lô)

     Nạp riêng như DuyetCore / XuatCore: hỏng ở đây chỉ mất xem trước preset,
     không đụng đường ghi màu. Không pcall quanh lời gọi SDK — dùng Core.try. ]]

local LrApplication   = import "LrApplication"
local LrDate          = import "LrDate"
local LrExportSession = import "LrExportSession"
local LrFileUtils     = import "LrFileUtils"
local LrPathUtils     = import "LrPathUtils"

local Core = require "AutoToneCore"
local okDuyet, Duyet = pcall(require, "DuyetCore")
if not okDuyet then Duyet = nil end

local M = {}
M.DS        = "lr_presets.tsv"
M.XIN_DS    = "request_dspreset.txt"
M.YEU_CAU   = "request_xempreset.txt"
M.CO_DUNG   = "request_xempreset_dung.txt"
M.TIEN_DO   = "xempreset_tiendo.txt"
M.BANG      = "xempreset_anh.tsv"
M.SO_KP     = "xempreset_khoiphuc.json"
M.LO        = 6
M.GIAY_MOI_LUOT = 15
M.GIAY_DS   = 20
M.CANH      = 1600
M.CHAT      = 0.8

--[[ Khoá so sau khi trả lại: đủ để bắt "trả lại hỏng" mà không so cả trăm
     khoá (mảng đường cong... so bằng JSON). ]]
M.KHOA_KIEM = { "WhiteBalance", "Temperature", "Tint", "Exposure2012", "Contrast2012",
                "Highlights2012", "Shadows2012", "Whites2012", "Blacks2012", "Texture",
                "Clarity2012", "Dehaze", "Vibrance", "Saturation", "CameraProfile",
                "ProcessVersion", "ToneCurvePV2012", "HueAdjustmentRed",
                "SaturationAdjustmentOrange", "LuminanceAdjustmentOrange",
                "ColorGradeMidtoneHue", "ColorGradeMidtoneSat", "SplitToningShadowHue",
                "SplitToningHighlightHue", "SharpenDetail", "PostCropVignetteAmount",
                "CropTop", "CropLeft", "CropBottom", "CropRight", "CropAngle" }

local CUC_BO = { "MaskGroupBasedCorrections", "GradientBasedCorrections",
                 "CircularGradientBasedCorrections", "PaintBasedCorrections" }

local function dir() return Core.jobDir() end
local function f(ten) return LrPathUtils.child(dir(), ten) end

-- ------------------------------------------------------------------ JSON nhỏ
--[[ Đủ cho getDevelopSettings(): số, chuỗi, bool, bảng lồng nhau. Mảng = khoá
     1..n liền nhau. Giải mã viết tay (SDK không có JSON, không loadstring). ]]
local function jChuoi(s)
    return '"' .. string.gsub(s, '[%c"\\]', function(c)
        if c == '"' then return '\\"' end
        if c == "\\" then return "\\\\" end
        if c == "\n" then return "\\n" end
        if c == "\r" then return "\\r" end
        if c == "\t" then return "\\t" end
        return string.format("\\u%04x", string.byte(c))
    end) .. '"'
end

local function jMa(v)
    local t = type(v)
    if t == "string" then return jChuoi(v) end
    if t == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        return string.format("%.17g", v)
    end
    if t == "boolean" then return v and "true" or "false" end
    if t ~= "table" then return "null" end
    local n = 0
    for _ in pairs(v) do n = n + 1 end
    local mang = n > 0
    for i = 1, n do if v[i] == nil then mang = false break end end
    local out = {}
    if mang then
        for i = 1, n do out[i] = jMa(v[i]) end
        return "[" .. table.concat(out, ",") .. "]"
    end
    local khoa = {}
    for k in pairs(v) do khoa[#khoa + 1] = tostring(k) end
    table.sort(khoa)
    for _, k in ipairs(khoa) do
        local val = v[k]
        if val == nil then val = v[tonumber(k)] end
        out[#out + 1] = jChuoi(k) .. ":" .. jMa(val)
    end
    return "{" .. table.concat(out, ",") .. "}"
end
M.jMa = jMa

local function jGiai(s)
    local pos = 1
    local giaTri
    local function trang() pos = string.find(s, "[^%s]", pos) or (#s + 1) end
    local function chuoi()
        local out, i = {}, pos + 1
        while true do
            local c = string.sub(s, i, i)
            if c == "" then error("JSON: chuoi chua dong") end
            if c == '"' then pos = i + 1 break end
            if c == "\\" then
                local e = string.sub(s, i + 1, i + 1)
                if e == "u" then
                    local cp = tonumber(string.sub(s, i + 2, i + 5), 16) or 63
                    if cp < 128 then out[#out + 1] = string.char(cp)
                    elseif cp < 2048 then
                        out[#out + 1] = string.char(192 + math.floor(cp / 64), 128 + cp % 64)
                    else
                        out[#out + 1] = string.char(224 + math.floor(cp / 4096),
                            128 + math.floor(cp / 64) % 64, 128 + cp % 64)
                    end
                    i = i + 6
                else
                    local map = { n = "\n", r = "\r", t = "\t", b = "\b", f = "\f" }
                    out[#out + 1] = map[e] or e
                    i = i + 2
                end
            else
                out[#out + 1] = c
                i = i + 1
            end
        end
        return table.concat(out)
    end
    giaTri = function()
        trang()
        local c = string.sub(s, pos, pos)
        if c == "{" then
            local t = {}
            pos = pos + 1
            trang()
            if string.sub(s, pos, pos) == "}" then pos = pos + 1 return t end
            while true do
                trang()
                local k = chuoi()
                trang()
                pos = pos + 1          -- ':'
                t[k] = giaTri()
                trang()
                local d = string.sub(s, pos, pos)
                pos = pos + 1
                if d == "}" then return t end
            end
        elseif c == "[" then
            local t = {}
            pos = pos + 1
            trang()
            if string.sub(s, pos, pos) == "]" then pos = pos + 1 return t end
            while true do
                t[#t + 1] = giaTri()
                trang()
                local d = string.sub(s, pos, pos)
                pos = pos + 1
                if d == "]" then return t end
            end
        elseif c == '"' then
            return chuoi()
        elseif string.sub(s, pos, pos + 3) == "true" then pos = pos + 4 return true
        elseif string.sub(s, pos, pos + 4) == "false" then pos = pos + 5 return false
        elseif string.sub(s, pos, pos + 3) == "null" then pos = pos + 4 return nil
        end
        local a, b = string.find(s, "^-?[%d%.eE%+%-]+", pos)
        if not a then error("JSON: ky tu la o " .. pos) end
        pos = b + 1
        return tonumber(string.sub(s, a, b))
    end
    return giaTri()
end
M.jGiai = jGiai

-- --------------------------------------------------------------- ghi file
local function ghiFile(path, text)
    local tmp = path .. ".part"
    local fh = io.open(tmp, "wb")
    if not fh then return false end
    fh:write(text)
    fh:close()
    Core.try("ghiFile", function()
        if LrFileUtils.exists(path) then LrFileUtils.delete(path) end
        LrFileUtils.move(tmp, path)
        return true
    end)
    return true
end

local function docFile(path)
    local fh = io.open(path, "rb")
    if not fh then return nil end
    local s = fh:read("*a")
    fh:close()
    return s
end

local function sach(s) return (string.gsub(tostring(s or ""), "[\t\r\n]", " ")) end

-- ------------------------------------------------------------ danh sách preset
local dsCu, tDs = nil, -1e9

function M.ghiDanhSach(ep)
    local dong = {}
    local folders = Core.try("presetFolders", function()
        return LrApplication.developPresetFolders()
    end) or {}
    for _, folder in ipairs(folders) do
        local nhom = Core.try("tenNhom", function() return folder:getName() end) or ""
        local duong = Core.try("duongNhom", function() return folder:getPath() end) or ""
        local ds = Core.try("presetTrongNhom", function() return folder:getDevelopPresets() end) or {}
        for _, p in ipairs(ds) do
            local uuid = Core.try("uuid", function() return p:getUuid() end) or ""
            local ten = Core.try("tenPreset", function() return p:getName() end) or ""
            dong[#dong + 1] = table.concat({ sach(uuid), sach(ten), sach(nhom), sach(duong) }, "\t")
        end
    end
    tDs = LrDate.currentTime()
    local txt = table.concat(dong, "\n") .. "\n"
    if not ep and txt == dsCu and LrFileUtils.exists(f(M.DS)) then return #dong end
    ghiFile(f(M.DS), txt)
    if dsCu ~= nil then Core.log("xempreset: danh sach preset doi -> gui lai " .. #dong) end
    dsCu = txt
    return #dong
end

local function timPreset(uuid, ten, nhom)
    local p
    if uuid and uuid ~= "" and LrApplication.developPresetByUuid then
        p = Core.try("presetByUuid", function() return LrApplication.developPresetByUuid(uuid) end)
        if p then return p end
    end
    local folders = Core.try("presetFolders", function()
        return LrApplication.developPresetFolders()
    end) or {}
    for _, folder in ipairs(folders) do
        local tn = Core.try("tenNhom", function() return folder:getName() end) or ""
        if not nhom or nhom == "" or tn == nhom then
            for _, x in ipairs(Core.try("presetTrongNhom", function()
                    return folder:getDevelopPresets() end) or {}) do
                if (Core.try("tenPreset", function() return x:getName() end)) == ten then
                    return x
                end
            end
        end
    end
    return nil
end

-- --------------------------------------------------------------- tiến độ
local function ghiTienDo(d, trangThai, thongBao)
    local t = {
        "id=" .. tostring(d and d.id or ""),
        "trang_thai=" .. tostring(trangThai),
        "xong=" .. tostring(d and #d.cap or 0),
        "tong=" .. tostring(d and d.tong or 0),
        "thieu=" .. tostring(d and d.thieu or 0),
        "lech=" .. tostring(d and d.lech or 0),
        "dest=" .. tostring(d and d.dest or ""),
        "ap=" .. tostring(d and d.ap and 1 or 0),
        "thong_bao=" .. sach(thongBao or ""),
    }
    ghiFile(f(M.TIEN_DO), table.concat(t, "\n") .. "\n")
end

local function ghiBang(d)
    local t = {}
    for _, c in ipairs(d.cap) do t[#t + 1] = c.src .. "\t" .. c.jpg end
    ghiFile(f(M.BANG), table.concat(t, "\n") .. (#t > 0 and "\n" or ""))
end

-- --------------------------------------------------------------- sổ khôi phục
local function ghiSo(lo)
    local t = {}
    for _, x in ipairs(lo) do
        if x.goc then t[#t + 1] = { path = x.path, goc = x.goc } end
    end
    return ghiFile(f(M.SO_KP), jMa(t))
end

local function xoaSo()
    Core.try("xoaSoKP", function()
        if LrFileUtils.exists(f(M.SO_KP)) then LrFileUtils.delete(f(M.SO_KP)) end
        return true
    end)
end

-- ----------------------------------------------------------------- trả lại
local presetWB = {}
local function presetTraWB(wb)
    if presetWB[wb] == nil then
        local p = Core.try("taoPresetWB", function()
            return LrApplication.addDevelopPresetForPlugin(_PLUGIN, "AutoTone tra WB " .. wb,
                                                           { WhiteBalance = wb })
        end)
        presetWB[wb] = p or false
    end
    return presetWB[wb] or nil
end

local function giong(a, b)
    if type(a) == "table" or type(b) == "table" then return jMa(a) == jMa(b) end
    if type(a) == "number" and type(b) == "number" then return math.abs(a - b) < 1e-6 end
    return a == b
end

--[[ Trả lại thông số gốc cho cả lô. Trả về (số ảnh lệch, lỗi). ]]
function M.traLai(catalog, lo, coWB)
    local _, err = Core.try("traLaiThongSo", function()
        catalog:withWriteAccessDo("AutoTone: trả lại thông số", function()
            for _, x in ipairs(lo) do
                if x.goc then
                    x.photo:applyDevelopSettings(x.goc, "AutoTone: trả lại")
                    if x.goc.CameraProfile or x.goc.Look then
                        x.photo:applyDevelopSettings({ CameraProfile = x.goc.CameraProfile,
                                                       Look = x.goc.Look }, "AutoTone: trả lại")
                    end
                end
            end
        end, { timeout = 60 })
        return true
    end)
    if coWB then
        local can = {}
        for _, x in ipairs(lo) do
            if x.goc and tonumber(x.goc.Temperature) == nil then can[#can + 1] = x end
        end
        if #can > 0 then
            Core.try("traWB", function()
                catalog:withWriteAccessDo("AutoTone: trả lại cân bằng trắng", function()
                    for _, x in ipairs(can) do
                        local p = presetTraWB(tostring(x.goc.WhiteBalance or "As Shot"))
                        if p then x.photo:applyDevelopPreset(p, _PLUGIN) end
                    end
                end, { timeout = 60 })
                return true
            end)
        end
    end
    local lech = 0
    for _, x in ipairs(lo) do
        if x.goc then
            local sau = Core.try("docSau", function() return x.photo:getDevelopSettings() end) or {}
            local khac = {}
            for _, k in ipairs(M.KHOA_KIEM) do
                if not giong(x.goc[k], sau[k]) then
                    khac[#khac + 1] = k .. "=" .. string.sub(jMa(x.goc[k]), 1, 40) .. "->"
                        .. string.sub(jMa(sau[k]), 1, 40)
                end
            end
            if #khac > 0 then
                lech = lech + 1
                Core.log("xempreset: TRA LAI LECH " .. tostring(x.path) .. " : "
                         .. table.concat(khac, ", "))
            end
        end
    end
    return lech, err
end

--[[ Lightroom tắt / máy sập giữa lô: trả lại theo sổ. Gọi MỘT lần lúc nạp. ]]
function M.khoiPhuc()
    local s = docFile(f(M.SO_KP))
    if not s or s == "" then return 0 end
    local ok, ds = pcall(jGiai, s)
    if not ok or type(ds) ~= "table" then
        Core.log("xempreset: so khoi phuc hong -> giu lai de xem tay: " .. tostring(ds))
        Core.try("doiTenSo", function()
            LrFileUtils.move(f(M.SO_KP), f(M.SO_KP) .. ".hong")
            return true
        end)
        return 0
    end
    local catalog = LrApplication.activeCatalog()
    local lo = {}
    for _, x in ipairs(ds) do
        local photo = Core.try("timAnhKP", function() return catalog:findPhotoByPath(x.path) end)
        if photo and type(x.goc) == "table" then
            lo[#lo + 1] = { path = x.path, photo = photo, goc = x.goc }
        end
    end
    local lech = M.traLai(catalog, lo, true)
    xoaSo()
    Core.log(string.format("xempreset: KHOI PHUC %d anh tu so (lan truoc dung giua lo), lech %d",
                           #lo, lech or 0))
    return #lo
end

-- --------------------------------------------------------------- render một lô
local function xuatLo(photos, dest, canh, chat)
    local thongSo
    if Duyet and Duyet.thongSo then
        thongSo = Duyet.thongSo(dest, canh, chat)
    else
        thongSo = { LR_export_destinationType = "specificFolder",
                    LR_export_destinationPathPrefix = dest, LR_export_useSubfolder = false,
                    LR_format = "JPEG", LR_jpeg_quality = chat, LR_collisionHandling = "overwrite",
                    LR_export_colorSpace = "sRGB", LR_size_doConstrain = true,
                    LR_size_maxWidth = canh, LR_size_maxHeight = canh, LR_size_resizeType = "wh",
                    LR_size_units = "pixels", LR_size_resolution = 72,
                    LR_reimportExportedPhoto = false, LR_renamingTokensOn = false,
                    LR_extensionCase = "lowercase", LR_export_postProcessing = "doNothing" }
    end
    local session = LrExportSession({ photosToExport = photos, exportSettings = thongSo })
    local ra = {}
    Core.try("renderLo", function()
        for _, r in session:renditions() do
            local ok, p = r:waitForRender()
            if ok and p then ra[#ra + 1] = p end
        end
        return true
    end)
    return ra
end

--[[ File JPEG của một ảnh gốc: tên đoán trước (LR_tokens = {{image_name}},
     đuôi thường — như ảnh duyệt), không có thì khớp theo tên không đuôi trong
     danh sách Lightroom trả về. Không dựa vào rendition.photo == photo: SDK
     không hứa hai đối tượng là một. ]]
local function jpgCua(dest, src, ra)
    local base = LrPathUtils.removeExtension(LrPathUtils.leafName(src))
    local du = LrPathUtils.child(dest, base .. ".jpg")
    if LrFileUtils.exists(du) then return du end
    for _, p in ipairs(ra) do
        if LrPathUtils.removeExtension(LrPathUtils.leafName(p)) == base then return p end
    end
    return nil
end

-- --------------------------------------------------------------- lượt
M.dang = nil

local function docYeuCau(path)
    local s = docFile(path)
    if not s then return nil end
    s = string.gsub(s, "^\239\187\191", "")
    local r, paths, phan = {}, {}, 1
    for line in string.gmatch(s, "[^\r\n]+") do
        if phan == 1 then
            if line == "---" then
                phan = 2
            else
                local k, v = string.match(line, "^%s*([%w_]+)%s*=%s*(.-)%s*$")
                if k then r[k] = v end
            end
        elseif line ~= "" then
            paths[#paths + 1] = line
        end
    end
    r.paths = paths
    return r
end

local function coCucBo(st)
    if type(st) ~= "table" then return false end
    for _, k in ipairs(CUC_BO) do
        local v = st[k]
        if type(v) == "table" and next(v) ~= nil then return true end
    end
    return false
end

local function coWBTrong(st)
    if type(st) ~= "table" then return true end      -- không đọc được: coi như có
    return st.WhiteBalance ~= nil or st.Temperature ~= nil or st.Tint ~= nil
        or st.IncrementalTemperature ~= nil or st.IncrementalTint ~= nil
end

function M.batDau(r)
    local d = { id = r.id or "", dest = r.dest or "", tong = #r.paths, thieu = 0, lech = 0,
                cap = {}, con = {}, ap = (r.ap == "1"),
                canh = tonumber(r.canh) or M.CANH, chat = tonumber(r.chat) or M.CHAT }
    if d.chat > 1 then d.chat = d.chat / 100 end
    for i, p in ipairs(r.paths) do d.con[i] = p end
    local preset = timPreset(r.uuid, r.ten, r.nhom)
    if not preset then
        M.ghiDanhSach(true)
        ghiTienDo(d, "loi", "Khong tim thay preset \"" .. tostring(r.ten) ..
                  "\" trong Lightroom (da xoa / doi ten?)")
        Core.log("xempreset: khong thay preset " .. tostring(r.ten) .. " / " .. tostring(r.uuid))
        M.dang = nil
        return false
    end
    local st = Core.try("presetSetting", function() return preset:getSetting() end)
    if not d.ap and coCucBo(st) then
        ghiTienDo(d, "loi", "Preset co mask / chinh cuc bo - khong xem truoc tam duoc " ..
                  "(khong tra lai chac chan)")
        M.dang = nil
        return false
    end
    d.preset = preset
    d.ten = r.ten or ""
    d.coWB = coWBTrong(st)
    if d.dest ~= "" and not LrFileUtils.exists(d.dest) then
        LrFileUtils.createAllDirectories(d.dest)
    end
    d.catalog = LrApplication.activeCatalog()
    if Duyet and Duyet.dungBangTra then
        d.tra = Duyet.dungBangTra(d.catalog)
    else
        d.tra = function(p) return d.catalog:findPhotoByPath(p) end
    end
    d.t0 = LrDate.currentTime()
    M.dang = d
    ghiBang(d)
    ghiTienDo(d, "dang_chay", (d.ap and "ap han " or "xem tam ") .. d.ten)
    Core.log(string.format("xempreset: bat dau %s \"%s\" %d anh -> %s",
                           d.ap and "AP HAN" or "xem tam", d.ten, d.tong, d.dest))
    return true
end

function M.motLo()
    local d = M.dang
    local lo = {}
    --[[ 10/10 (học NEXUS: họ chỉ render ảnh đang xem, ~1 s): lô ĐẦU chỉ MỘT ảnh —
         tấm app xếp đầu (ảnh đang mở / đang chọn) hiện theo preset sau một lần
         render, không đợi cả lô 6 tấm. ]]
    local co = (d.soLo or 0) == 0 and 1 or M.LO
    d.soLo = (d.soLo or 0) + 1
    while #lo < co and #d.con > 0 do
        local p = table.remove(d.con, 1)
        local photo = Core.try("timAnh", function() return d.tra(p) end)
        if photo then
            lo[#lo + 1] = { path = p, photo = photo }
        else
            d.thieu = d.thieu + 1
        end
    end
    if #lo == 0 then return end
    for _, x in ipairs(lo) do
        x.goc = Core.try("docGoc", function() return x.photo:getDevelopSettings() end)
    end
    local dung = {}
    for _, x in ipairs(lo) do if x.goc then dung[#dung + 1] = x end end
    lo = dung
    if #lo == 0 then return end
    if not d.ap then ghiSo(lo) end
    local okA, errA = Core.try("apPreset", function()
        d.catalog:withWriteAccessDo(d.ap and "AutoTone: áp preset" or "AutoTone: xem preset",
            function()
                for _, x in ipairs(lo) do x.photo:applyDevelopPreset(d.preset, _PLUGIN) end
            end, { timeout = 60 })
        return true
    end)
    local ra = {}
    if okA then
        local photos = {}
        for i, x in ipairs(lo) do photos[i] = x.photo end
        ra = xuatLo(photos, d.dest, d.canh, d.chat)
    else
        Core.log("xempreset: LOI ap preset -> " .. tostring(errA))
    end
    if not d.ap then
        local lech = M.traLai(d.catalog, lo, d.coWB)
        d.lech = d.lech + (lech or 0)
        xoaSo()
    end
    if okA then
        for _, x in ipairs(lo) do
            local jpg = jpgCua(d.dest, x.path, ra)
            if jpg then d.cap[#d.cap + 1] = { src = x.path, jpg = jpg } end
        end
    end
    ghiBang(d)
    ghiTienDo(d, "dang_chay", "")
end

local function ketThuc(trangThai, thongBao)
    local d = M.dang
    if not d then return end
    local giay = LrDate.currentTime() - (d.t0 or LrDate.currentTime())
    ghiTienDo(d, trangThai, thongBao or string.format("%.0f giay", giay))
    Core.log(string.format("xempreset: %s \"%s\" %d/%d anh, thieu %d, lech %d, %.0f giay",
                           trangThai, tostring(d.ten), #d.cap, d.tong, d.thieu, d.lech, giay))
    M.dang = nil
end

--[[ Việc khác đang chờ thì nhường vòng lặp (job áp màu, xuất ảnh, duyệt...). ]]
local function viecKhacCho()
    for _, ten in ipairs({ "request_xuatanh.txt", "request_export.txt", "request_duyet.txt",
                           "request_chup.txt" }) do
        if LrFileUtils.exists(f(ten)) then return true end
    end
    local co = false
    Core.try("timJob", function()
        for p in LrFileUtils.files(dir()) do
            local ten = LrPathUtils.leafName(p) or ""
            if string.match(ten, "^apply_.*%.tsv$") then co = true break end
        end
        return true
    end)
    return co
end

function M.runRequest()
    if LrFileUtils.exists(f(M.XIN_DS)) then
        Core.try("boXinDs", function() LrFileUtils.delete(f(M.XIN_DS)) return true end)
        M.ghiDanhSach(true)
    elseif not M.dang and LrDate.currentTime() - tDs > M.GIAY_DS then
        M.ghiDanhSach(false)
    end

    local req = f(M.YEU_CAU)
    if LrFileUtils.exists(req) then
        local claimed = Core.claim(req)
        if claimed then
            local r = docYeuCau(claimed)
            Core.try("boYeuCau", function() LrFileUtils.delete(claimed) return true end)
            if M.dang then ketThuc("thay", "co yeu cau moi") end
            if r then M.batDau(r) end
        end
    end
    if not M.dang then return 0 end

    if LrFileUtils.exists(f(M.CO_DUNG)) then
        Core.try("boCoDung", function() LrFileUtils.delete(f(M.CO_DUNG)) return true end)
        ketThuc("dung", "nguoi dung dung")
        return 0
    end

    local t = LrDate.currentTime()
    local truoc = #M.dang.cap
    while M.dang and #M.dang.con > 0 do
        M.motLo()
        if LrDate.currentTime() - t > M.GIAY_MOI_LUOT then break end
        if LrFileUtils.exists(req) or LrFileUtils.exists(f(M.CO_DUNG)) then break end
        if viecKhacCho() then break end
    end
    local n = M.dang and (#M.dang.cap - truoc) or 0
    if M.dang and #M.dang.con == 0 then ketThuc("xong") end
    return n
end

return M
