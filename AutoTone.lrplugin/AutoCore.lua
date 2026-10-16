--[[ AUTO (bảng Basic) CHO CẢ BUỔI — 16/10, "Quy trình Auto Lightroom (thử nghiệm)".

     User 16/10: "Khách hàng Import 1 bộ ảnh vào Lightroom -> Chọn preset của họ -> Xuất thông số
     cho AutoTone bắt đầu xử lý. Đổi quy trình sang bước đầu tiên sau khi nhận đc thông số. Bật chế
     độ Auto của phần Basic của tất cả các ảnh -> Đo các thông số hiện tại trên vùng da để bắt đầu
     căn chỉnh lại cho về với da đích -> WB -> Tone -> Curve RGB -> Áp lại LR -> Kiểm tra lại ...".

     CÁCH GOM (16/10 tối, user: "Việc để LR bấm Auto từng ảnh ntn rất lâu. Tìm hướng để có thể Áp
     cho toàn bộ ảnh"). Cách cũ — mở Develop, chọn từng ảnh, LrDevelopController.setAutoTone() —
     đo thật buổi TEST: 77 ảnh / 197 giây = 2,6 giây / ảnh (693 ảnh ~30 phút); thử một lệnh cho cả
     lô (Auto Sync) không ăn. Lightroom 15.5 có đường KHÔNG cần Develop (đọc ra từ
     LibraryToolkit.dll — LrPhoto — và Library.lrmodule — SdkOperations):
         photo:applyDevelopSettings(settings, historyName, flattenAutoNow)
     settings có AutoTone = true + flattenAutoNow = true -> Lightroom mở ảnh cỡ nhỏ
     (kSuggestedMinimumSizeForAutoSettings), autoToneKeysForSettings + flattenAutoValues -> ghi SỐ
     Auto vào catalog. Nút Auto của Develop (_updateAutoValues) dùng đúng hai hàm đó, cùng khoá
     AutoTone -> cùng một phép Auto; chỉ khác là không phải dựng ảnh to trong Develop.
       - mỗi lô một giao dịch (applyJob: một giao dịch to từng hết giờ, ảnh sau không nhận); cỡ lô
         tự chỉnh để mỗi giao dịch ~LO_GIAY giây
       - THỬ trước bằng ảnh lẻ, kèm hai số CANH (Whites −100, Blacks +100): Auto ghi đè -> gom
         được; còn nguyên / Lightroom để nguyên cờ AutoTone (không tính) -> trả lại hai ô, về
         cách cũ cho cả lượt. Ảnh không dùng được canh (PV2010) thì thử tới LO_THU ảnh xem có
         ảnh nào đổi
       - không vào Develop, không đổi ảnh đang chọn
     CHƯA thử trên Lightroom thật.

     YÊU CẦU RIÊNG (jobs/request_auto.txt), không nằm trong applyJob:
         #ma=<mã lượt>
         <đường dẫn ảnh>      (mỗi dòng một ảnh)
     Plugin ghi jobs/auto_tiendo.txt (ma, xong, tong, trang_thai) trong lúc chạy,
     jobs/auto_anh.tsv (path + thông số SAU Auto) và jobs/ketqua_auto.txt (ma, tong, bat,
     khong_doi, khong_thay, loi, dung, lo, cach, giay, ly_do, khi) khi xong. App xin dừng bằng
     jobs/dung_auto.txt (ma=<mã lượt>).

     KHÔNG pcall quanh lời gọi SDK — dùng Core.try. ]]

local LrApplication = import "LrApplication"
local LrDate        = import "LrDate"
local LrFileUtils   = import "LrFileUtils"
local LrPathUtils   = import "LrPathUtils"
local LrTasks       = import "LrTasks"

local Core = require "AutoToneCore"

local okDC, LrDevelopController = pcall(import, "LrDevelopController")
if not okDC then LrDevelopController = nil end
local okAV, LrApplicationView = pcall(import, "LrApplicationView")
if not okAV then LrApplicationView = nil end

local M = {}

M.YEU_CAU = "request_auto.txt"
M.TIEN_DO = "auto_tiendo.txt"
M.KET_QUA = "ketqua_auto.txt"
M.BANG    = "auto_anh.tsv"
M.DUNG    = "dung_auto.txt"
--  Ô Auto (bảng Basic) đổi — đọc lại sau Auto, ghi vào bảng cho app làm MỐC mới
M.O = { "Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012", "Whites2012",
        "Blacks2012", "Vibrance", "Saturation", "Temperature", "Tint", "WhiteBalance" }
--  tên bước History của lần Auto (cách gom)
M.TEN_BUOC = "AutoTone: Auto"
--  cách gom: ảnh THỬ đi lẻ, tối đa LO_THU ảnh tới khi một ảnh đổi (ảnh thử chưa đổi chờ thêm
--  CHO_THU giây — phòng Lightroom tính nền); sau đó lô 1…LO_MAX ảnh, mỗi giao dịch ~LO_GIAY giây
--  (giao dịch giữ khoá ghi catalog — khoá ghi là thứ làm Lightroom đơ), nghỉ NGHI giây giữa hai lô
M.LO_THU, M.CHO_THU, M.LO_MAX, M.LO_GIAY, M.NGHI = 5, 3.0, 40, 4.0, 0.1
--[[ ẢNH THỬ gửi kèm hai số CANH: Auto tính lại thì ghi đè; vẫn nguyên = Lightroom không tính (trả
     lại hai ô, về cách cũ). Không có canh thì ảnh ĐÃ Auto từ trước (Auto lại ra đúng số đang có)
     trông y như "không ăn" -> về cách cũ oan — buổi TEST 16/10 có sẵn 366 ảnh Auto bằng Develop.
     Hai số Auto không bao giờ ra (Whites −100 cùng Blacks +100). ]]
M.CANH = { Whites2012 = -100, Blacks2012 = 100 }
--  cách cũ (Develop): chờ Lightroom tính Auto xong cho một ảnh (Auto AI có thể mất ~1 giây)
M.CHO_MOI_ANH = 4.0

local function now()
    if LrDate and LrDate.currentTime then return LrDate.currentTime() end
    return os.time()
end

--[[ Hàm THUẦN: (mã, danh sách đường dẫn) từ nội dung file yêu cầu. ]]
function M.phanTich(chu)
    local ma, ds = "", {}
    for dong in string.gmatch(chu or "", "[^\r\n]+") do
        local m = string.match(dong, "^#ma=(.*)$")
        if m then
            ma = m
        elseif string.sub(dong, 1, 1) ~= "#" then
            local p = string.gsub(dong, "^%s*(.-)%s*$", "%1")
            if p ~= "" then ds[#ds + 1] = p end
        end
    end
    return ma, ds
end

--[[ Hàm THUẦN: nội dung file dừng có xin dừng ĐÚNG lượt `ma` không. ]]
function M.xinDung(chu, ma)
    local m = string.match(chu or "", "ma=([^\r\n]*)")
    if m == nil then return false end
    m = string.gsub(m, "^%s*(.-)%s*$", "%1")
    return m == (ma or "")
end

--[[ Hàm THUẦN: hai bảng thông số khác nhau ở ô tông nào không (Auto đã đổi ảnh). ]]
function M.daDoi(truoc, sau)
    if type(truoc) ~= "table" or type(sau) ~= "table" then return false end
    for _, k in ipairs({ "Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012",
                         "Whites2012", "Blacks2012", "Vibrance", "Saturation" }) do
        local a, b = tonumber(truoc[k]), tonumber(sau[k])
        if a ~= nil and b ~= nil and math.abs(a - b) > 1e-6 then return true end
        if (a == nil) ~= (b == nil) then return true end
    end
    return false
end

--[[ Hàm THUẦN: Lightroom còn để cờ AutoTone trong thông số (nhận lệnh mà CHƯA tính số Auto). ]]
function M.conCo(st)
    if type(st) ~= "table" then return false end
    local v = st.AutoTone
    return v == true or v == "True" or v == "true"
end

--[[ Hàm THUẦN: ảnh dùng được số canh không — bản xử lý 2012 trở đi (có Whites2012 / Blacks2012;
     PV2010 / 2003 "5.x" thì Auto không đụng hai ô đó). ]]
function M.coCanh(st)
    if type(st) ~= "table" then return false end
    for k in pairs(M.CANH) do
        if tonumber(st[k]) == nil then return false end
    end
    local pv = tostring(st.ProcessVersion or "")
    return string.sub(pv, 1, 2) ~= "5."
end

--[[ Hàm THUẦN: hai số canh còn nguyên (Lightroom chưa tính Auto cho ảnh thử). ]]
function M.conCanh(st)
    if type(st) ~= "table" then return false end
    for k, v in pairs(M.CANH) do
        if tonumber(st[k]) ~= v then return false end
    end
    return true
end

--[[ Hàm THUẦN: cỡ lô kế tiếp của cách gom — lô vừa rồi `n` ảnh mất `giay` giây. ]]
function M.coLo(n, giay)
    local moi = (tonumber(giay) or 0) / math.max(1, tonumber(n) or 1)
    if moi <= 0 then return M.LO_MAX end
    return math.max(1, math.min(M.LO_MAX, math.floor(M.LO_GIAY / moi)))
end

--[[ Lightroom này có bấm Auto trong Develop qua SDK được không (cách cũ). ]]
function M.coHam(dc)
    dc = dc or LrDevelopController
    return type(dc) == "table" and type(dc.setAutoTone) == "function"
end

--[[ Hàm THUẦN: một dòng bảng auto_anh.tsv. ]]
function M.dongBang(duong, st)
    local o = { duong }
    for _, k in ipairs(M.O) do
        local v = type(st) == "table" and st[k] or nil
        o[#o + 1] = (v == nil) and "" or tostring(v)
    end
    return table.concat(o, "\t")
end

local function ghiKv(ten, t, thuTu)
    local dir = Core.jobDir()
    local dest = LrPathUtils.child(dir, ten)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return end
    for _, k in ipairs(thuTu) do
        if t[k] ~= nil then fh:write(k .. "=" .. tostring(t[k]) .. "\n") end
    end
    fh:close()
    Core.try("autoGhi", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)
end

local function tienDo(ma, xong, tong, tt)
    ghiKv(M.TIEN_DO, { ma = ma, xong = xong, tong = tong, trang_thai = tt or "dang_chay" },
          { "ma", "xong", "tong", "trang_thai" })
end

local function ketQua(t)
    ghiKv(M.KET_QUA, t, { "ma", "tong", "bat", "khong_doi", "khong_thay", "loi", "dung", "lo",
                          "cach", "giay", "ly_do", "khi" })
end

local function ghiBang(ma, dong)
    local dest = LrPathUtils.child(Core.jobDir(), M.BANG)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return end
    fh:write("#ma=" .. tostring(ma) .. "\n")
    fh:write("path\t" .. table.concat(M.O, "\t") .. "\n")
    for _, d in ipairs(dong) do fh:write(d .. "\n") end
    fh:close()
    Core.try("autoGhiBang", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)
end

--[[ App xin dừng lượt `ma` chưa. File của lượt KHÁC (cũ) thì xoá, không dừng. ]]
local function kiemDung(ma)
    local f = LrPathUtils.child(Core.jobDir(), M.DUNG)
    if not LrFileUtils.exists(f) then return false end
    local fh = io.open(f, "r")
    local chu = fh and fh:read("*a") or ""
    if fh then fh:close() end
    Core.try("autoXoaDung", function() LrFileUtils.delete(f) end)
    return M.xinDung(chu, ma)
end

local function idCua(photo)
    if not photo then return nil end
    return photo.localIdentifier
end

local function thongSo(photo)
    return Core.try("autoDoc", function() return photo:getDevelopSettings() end)
end

local function duongCua(photo)
    return Core.try("autoDuong", function() return photo:getRawMetadata("path") end)
end

local function nhip(buoc)
    Core.try("autoNhip", function() return Core.ghiNhip(nil, 3, buoc) end)
end

--[[ Đợi thông số của ảnh đổi so với `truoc` (Auto đã tính xong) — tối đa `cho` giây. ]]
local function doiDoi(photo, truoc, cho)
    local t0 = os.time()
    repeat
        LrTasks.sleep(0.25)
        local sau = thongSo(photo)
        if M.daDoi(truoc, sau) then return sau end
    until os.time() - t0 >= (cho or M.CHO_MOI_ANH)
    return nil
end

-- ------------------------------------------------------------------ cách gom (SDK, cả lô)
--[[ Một giao dịch: Auto cho các ảnh `ds` (Lightroom tính + ghi số ngay); `canh` = kèm số canh
     (ảnh thử). -> (true) / (nil, lỗi). ]]
local function apLo(catalog, ds, canh)
    return Core.try("autoGom", function()
        catalog:withWriteAccessDo(M.TEN_BUOC, function()
            for _, p in ipairs(ds) do
                local st = { AutoTone = true }
                if canh then
                    for k, v in pairs(M.CANH) do st[k] = v end
                end
                p:applyDevelopSettings(st, M.TEN_BUOC, true)
            end
        end, { timeout = 60 })
        return true
    end)
end

--[[ Ảnh thử Lightroom KHÔNG tính: trả hai ô canh về số cũ (`canh`) và / hoặc gỡ cờ AutoTone còn
     treo (`goCo`). ]]
local function traLai(catalog, p, tr, canh, goCo)
    local st = {}
    if canh then
        for k in pairs(M.CANH) do st[k] = tonumber(type(tr) == "table" and tr[k]) or 0 end
    end
    if goCo then st.AutoTone = false end
    if next(st) == nil then return end
    Core.try("autoTraLai", function()
        catalog:withWriteAccessDo("AutoTone: trả lại", function()
            p:applyDevelopSettings(st, "AutoTone: trả lại")
        end, { timeout = 60 })
        return true
    end)
end

--[[ CÁCH GOM. -> true khi Lightroom tính Auto qua SDK được (chạy hết, hoặc tới lúc app xin dừng);
     false khi THỬ không ăn — chưa ghi gì vào `dong` / `kq.bat`, gọi cách cũ cho cả lượt.
     Lô hỏng làm lại từng ảnh; ảnh vẫn hỏng / còn cờ AutoTone -> `sot` (cách cũ làm tiếp). ]]
local function apGom(catalog, photos, truoc, ma, kq, dong, sot)
    local idx, lo, thu, nThu = 1, 1, true, 0
    local choXet = {}       -- ảnh chưa đổi ngay: xét lại cuối lượt (Lightroom có thể tính nền)
    while idx <= #photos do
        if kiemDung(ma) then
            kq.dung = 1
            Core.log(string.format("auto: app xin dung o anh %d/%d", idx, #photos))
            break
        end
        local last = math.min(idx + lo - 1, #photos)
        local ds = {}
        for i = idx, last do ds[#ds + 1] = photos[i] end
        local t0 = now()
        local hong = {}
        local canh = thu and #ds == 1 and M.coCanh(truoc[idCua(ds[1])])
        local ok, err = apLo(catalog, ds, canh)
        if not ok then
            --  giao dịch hỏng thì Lightroom huỷ CẢ lô -> mỗi ảnh một giao dịch
            Core.log(string.format("auto: lo %d-%d loi (%s)", idx, last, tostring(err)))
            if #ds > 1 then
                for _, p in ipairs(ds) do
                    local ok1, err1 = apLo(catalog, { p })
                    if not ok1 then hong[idCua(p)] = tostring(err1) end
                end
            else
                hong[idCua(ds[1])] = tostring(err)
            end
        end
        local dt = now() - t0
        for _, p in ipairs(ds) do
            local id = idCua(p)
            if hong[id] then
                sot[#sot + 1] = p
                if thu then nThu = nThu + 1 end
            elseif canh then
                --  ảnh thử có canh: canh bị ghi đè = Lightroom đã tính Auto (kể cả khi Auto ra đúng
                --  số ảnh đang có — ảnh Auto từ trước)
                local sau = thongSo(p)
                local t1 = os.time()
                while M.conCanh(sau) and os.time() - t1 < M.CHO_THU do
                    LrTasks.sleep(0.25)
                    sau = thongSo(p)
                end
                if type(sau) ~= "table" then
                    sot[#sot + 1] = p
                    nThu = nThu + 1
                elseif M.conCanh(sau) or M.conCo(sau) then
                    Core.log("auto: Lightroom khong tinh so Auto qua SDK (flattenAutoNow) -> cach cu (Develop)")
                    traLai(catalog, p, truoc[id], true, M.conCo(sau))
                    return false
                else
                    thu = false
                    if M.daDoi(truoc[id], sau) then kq.bat = kq.bat + 1 else kq.khong_doi = kq.khong_doi + 1 end
                    dong[#dong + 1] = M.dongBang(duongCua(p) or "", sau)
                end
            else
                local sau = thongSo(p)
                if thu and not M.daDoi(truoc[id], sau) and M.CHO_THU > 0 then
                    sau = doiDoi(p, truoc[id], M.CHO_THU) or thongSo(p)
                end
                if M.daDoi(truoc[id], sau) then
                    thu = false
                    kq.bat = kq.bat + 1
                    dong[#dong + 1] = M.dongBang(duongCua(p) or "", sau)
                elseif M.conCo(sau) then
                    if thu then
                        Core.log("auto: Lightroom nhan lenh nhung khong tinh so Auto (flattenAutoNow)")
                        traLai(catalog, p, truoc[id], false, true)
                        return false
                    end
                    sot[#sot + 1] = p
                else
                    choXet[#choXet + 1] = p
                    if thu then nThu = nThu + 1 end
                end
            end
        end
        if thu and nThu >= M.LO_THU then
            Core.log(string.format("auto: thu %d anh khong anh nao doi -> cach cu (Develop)", nThu))
            return false
        end
        if not thu then lo = M.coLo(#ds, dt) end
        idx = last + 1
        tienDo(ma, last, #photos)
        nhip(string.format("auto %d/%d", last, #photos))
        if idx <= #photos then LrTasks.sleep(M.NGHI) end
    end
    if thu and not kq.dung then return false end
    --  ảnh chưa đổi: đổi muộn thì lấy số mới; vẫn như cũ = Auto ra đúng số đang có
    for _, p in ipairs(choXet) do
        local sau = thongSo(p)
        if M.daDoi(truoc[idCua(p)], sau) then kq.bat = kq.bat + 1 else kq.khong_doi = kq.khong_doi + 1 end
        dong[#dong + 1] = M.dongBang(duongCua(p) or "", sau)
    end
    return true
end

-- ------------------------------------------------------------------ cách cũ (Develop, từng ảnh)
--[[ Chọn ảnh và đợi Develop nhận nó (~5 giây). ]]
local function chon(catalog, xem)
    Core.try("autoChon", function() catalog:setSelectedPhotos(xem, { xem }) end)
    local muon = idCua(xem)
    for _ = 1, 25 do
        LrTasks.sleep(0.2)
        local t = catalog:getTargetPhoto()
        if t and idCua(t) == muon then
            LrTasks.sleep(0.3)
            return true
        end
    end
    return false
end

local function bamAuto()
    local _, err = Core.try("autoBam", function()
        LrDevelopController.setAutoTone()
        return true
    end)
    return err
end

--[[ CÁCH CŨ cho `con`: mở Develop, chọn từng ảnh, setAutoTone, đợi số đổi; trả module + vùng
     chọn. Tiến độ đếm tiếp từ `dau` trên `tong`. ]]
local function chayDevelop(catalog, con, truoc, ma, kq, dong, dau, tong)
    local moduleCu = Core.try("autoModule", function() return LrApplicationView.getCurrentModuleName() end)
    local chonCu = Core.try("autoChonCu", function() return catalog:getTargetPhotos() end)
    Core.try("autoVaoDevelop", function() LrApplicationView.switchToModule("develop") end)
    LrTasks.sleep(1.5)
    for i = 1, #con do
        local photo = con[i]
        if kiemDung(ma) then
            kq.dung = 1
            Core.log(string.format("auto: app xin dung o anh %d/%d", dau + i, tong))
            break
        end
        if not chon(catalog, photo) then
            kq.loi = kq.loi + 1
        else
            local err = bamAuto()
            if err then
                kq.loi = kq.loi + 1
                Core.log("auto LOI " .. tostring(duongCua(photo)) .. ": " .. tostring(err))
            else
                local sau = doiDoi(photo, truoc[idCua(photo)])
                if sau then kq.bat = kq.bat + 1 else kq.khong_doi = kq.khong_doi + 1 end
                dong[#dong + 1] = M.dongBang(duongCua(photo) or "", sau or thongSo(photo))
            end
        end
        tienDo(ma, dau + i, tong)
        nhip(string.format("auto %d/%d", dau + i, tong))
    end
    if type(chonCu) == "table" and #chonCu > 0 then
        Core.try("autoTraChon", function() catalog:setSelectedPhotos(chonCu[1], chonCu) end)
    end
    if type(moduleCu) == "string" and moduleCu ~= "" and moduleCu ~= "develop" then
        Core.try("autoTraModule", function() LrApplicationView.switchToModule(moduleCu) end)
    end
end

function M.runRequest()
    local dir = Core.jobDir()
    local req = LrPathUtils.child(dir, M.YEU_CAU)
    if not LrFileUtils.exists(req) then return 0 end
    local claimed = Core.claim(req)
    if not claimed then return 0 end
    local fh = io.open(claimed, "r")
    local chu = fh and fh:read("*a") or ""
    if fh then fh:close() end
    Core.try("autoXoaYc", function() LrFileUtils.delete(claimed) end)
    local ma, ds = M.phanTich(chu)
    local kq = { ma = ma, tong = #ds, bat = 0, khong_doi = 0, khong_thay = 0, loi = 0 }
    local t0 = now()
    local function xong(lyDo)
        kq.ly_do = lyDo
        kq.giay = math.floor(now() - t0 + 0.5)
        kq.khi = os.date("%Y-%m-%d %H:%M:%S")
        ketQua(kq)
    end
    if #ds == 0 then xong(nil) return 0 end
    local catalog = LrApplication.activeCatalog()
    local photos, truoc = {}, {}
    for i = 1, #ds do
        local p = Core.try("autoTim", function() return catalog:findPhotoByPath(ds[i]) end)
        if p then
            photos[#photos + 1] = p
            truoc[idCua(p)] = thongSo(p)
        else
            kq.khong_thay = kq.khong_thay + 1
        end
        if i % 200 == 0 then LrTasks.yield() end
    end
    if kiemDung(ma) then
        kq.dung = 1
        xong("dung")
        return 0
    end
    Core.log(string.format("auto: %d anh (%d khong thay trong catalog)", #photos, kq.khong_thay))
    tienDo(ma, 0, #photos)
    local dong, sot = {}, {}
    local con
    if apGom(catalog, photos, truoc, ma, kq, dong, sot) then
        kq.lo, kq.cach = 1, "gom"
        con = sot
    else
        dong, kq.bat, kq.khong_doi = {}, 0, 0
        kq.cach = "develop"
        con = photos
    end
    if #con > 0 and not kq.dung then
        if M.coHam() and LrApplicationView then
            if kq.cach == "gom" then kq.cach = "gom+develop" end
            chayDevelop(catalog, con, truoc, ma, kq, dong, #photos - #con, #photos)
        elseif kq.cach == "develop" then
            ghiBang(ma, {})
            tienDo(ma, #photos, #photos, "xong")
            xong("lightroom-chua-ho-tro")
            Core.log("auto: Lightroom nay khong tinh Auto qua SDK va khong co LrDevelopController.setAutoTone")
            return 0
        else
            kq.loi = kq.loi + #con
            for _, p in ipairs(con) do dong[#dong + 1] = M.dongBang(duongCua(p) or "", thongSo(p)) end
        end
    end
    ghiBang(ma, dong)
    tienDo(ma, #photos, #photos, kq.dung and "dung" or "xong")
    xong(kq.dung and "dung" or nil)
    Core.log(string.format("auto xong (%s): bam %d, khong doi %d, khong thay %d, loi %d, %d giay "
                           .. "(%.2f giay/anh)", tostring(kq.cach), kq.bat, kq.khong_doi,
                           kq.khong_thay, kq.loi, kq.giay, kq.giay / math.max(1, #photos)))
    return kq.bat
end

return M
