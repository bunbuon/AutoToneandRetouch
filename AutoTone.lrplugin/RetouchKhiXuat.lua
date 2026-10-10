--[[ RETOUCH KHI XUẤT — hành động Post-Process của chính lượt Export (10/10).

     User 10/10: "đưa phần Retouch thành plugin add vào Lightroom, khi Export thì
     plugin Retouch cũng chạy cùng để xuất bức ảnh ra là đã được retouch".

     ============================================================
     CÁCH CHẠY
     ============================================================

     Người dùng tích "AutoTone: Retouch khi xuất" MỘT LẦN ở mục Post-Process
     Actions của hộp Export, lưu vào Export preset. Sau đó mọi lần Export bằng
     preset đó: Lightroom render từng ảnh -> postProcessRenderedPhotos nhận file
     vừa render -> gửi cho TRẠM RETOUCH (tram_retouch.py: engine thường trú của app,
     hoặc trạm chạy ngầm khi app tắt) qua <jobs>/tram_retouch/yc_<id>.txt -> chờ
     kq_<id>.txt -> trạm đã GHI ĐÈ TẠI CHỖ file đó -> báo Lightroom xong ảnh ->
     Lightroom ghi ảnh (đã retouch) ra thư mục đích như mọi lần Export.

     Sửa tại chỗ file waitForRender trả về rồi renditionIsDone(true) là cách các
     plugin hậu kỳ (LR/Mogrify, Run Any Command…) vẫn làm.

     ============================================================
     KHÔNG BAO GIỜ LÀM HỎNG LƯỢT GIAO KHÁCH
     ============================================================

     Mọi đường hỏng (trạm không chạy, quá giờ, tool lỗi, ảnh không phải JPEG/TIFF/
     PNG, hết hạn bản quyền) -> ảnh vẫn ra, CHƯA retouch, ghi plugin.log. Quá giờ thì
     ghi huy_<id>.txt để trạm không đè file nữa (Lightroom có thể đã chuyển nó đi).
     Lời gọi SDK có thể yield -> bọc bằng LrTasks.pcall (an toàn với yield), không
     pcall thường. Không require AutoToneCore: module này chạy trong hộp Export, một
     lỗi nạp ở đó là báo lỗi giữa lượt xuất của người dùng (cùng lý do BatDuongDan).

     ============================================================
     NẠP MÔ HÌNH TRƯỚC KHI BẤM EXPORT
     ============================================================

     startDialog (hộp Export vừa mở): app đang mở -> xin app nạp engine (xin_nap.txt);
     app tắt -> mở trạm chạy ngầm (lệnh trong tram_lenh.txt do app ghi). Lúc người
     dùng bấm Export thì mô hình đã nạp — chỉ còn xuất ảnh. Dòng trạng thái trong hộp
     cho biết đã sẵn sàng chưa.

     MỘT ẢNH MỘT LẦN, KHÔNG GỐI ĐẦU: chỉ sang ảnh kế khi ảnh này đã retouch xong rồi
     mới renditionIsDone — để Lightroom không bao giờ nhận file chưa retouch xong.
     Lightroom vẫn render các ảnh sau trong lúc trạm làm ảnh trước (nếu có render
     trước thì nó dùng); plugin.log ghi thời gian chờ render / chờ retouch từng ảnh
     để đo trên Lightroom thật. ]]

local LrDialogs       = import "LrDialogs"
local LrFileUtils     = import "LrFileUtils"
local LrPathUtils     = import "LrPathUtils"
local LrProgressScope = import "LrProgressScope"
local LrTasks         = import "LrTasks"
local LrView          = import "LrView"

local okTMJ, TMJ = pcall(require, "ThuMucJob")
local function jobDir()
    if okTMJ and type(TMJ) == "table" and TMJ.jobDir then return TMJ.jobDir() end
    return LrPathUtils.child(_PLUGIN.path, "jobs")
end

local M = {}

M.CHO_DAU     = 240     -- giây: ảnh đầu (có thể phải mở trạm + nạp mô hình)
M.CHO_MOI_ANH = 180     -- giây: các ảnh sau
M.CU_NHIP     = 6       -- nhịp trạm cũ hơn chừng này giây -> trạm không chạy
M.NGU         = 0.05    -- nhịp hỏi kết quả
M.DUOI = { jpg = true, jpeg = true, tif = true, tiff = true, png = true }

local function tramDir()
    local d = LrPathUtils.child(jobDir(), "tram_retouch")
    if not LrFileUtils.exists(d) then LrFileUtils.createAllDirectories(d) end
    return d
end
local function f(ten) return LrPathUtils.child(tramDir(), ten) end

local function docKV(path)
    local fh = io.open(path, "r")
    if not fh then return nil end
    local s = fh:read("*a") or ""
    fh:close()
    s = string.gsub(s, "^\239\187\191", "")
    local d = {}
    for dong in string.gmatch(s, "[^\r\n]+") do
        local k, v = string.match(dong, "^([^=]+)=(.*)$")
        if k then d[k] = v end
    end
    return d
end

local function ghiFile(path, text)
    local tmp = path .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return false end
    fh:write(text)
    fh:close()
    if LrFileUtils.exists(path) then LrFileUtils.delete(path) end
    LrFileUtils.move(tmp, path)
    return true
end

local function log(msg)
    local fh = io.open(LrPathUtils.child(jobDir(), "plugin.log"), "a")
    if fh then
        fh:write(os.date("%Y-%m-%d %H:%M:%S") .. "  retouch-xuat: " .. tostring(msg) .. "\n")
        fh:close()
    end
end

local function sach(s) return (string.gsub(tostring(s or ""), "[\r\n]", " ")) end

-- --------------------------------------------------------------------- trạm
function M.nhip(loai)
    local d = docKV(f("tram_" .. loai .. ".txt"))
    if not d then return nil end
    local t = tonumber(d.t or "")
    if not t or math.abs(os.time() - t) > M.CU_NHIP then return nil end
    return d
end

--[[ Mở trạm chạy ngầm bằng lệnh app đã ghi (tram_lenh.txt). Windows: lệnh dạng
     start "" "...AutoTone.exe" --say-tram "..." — cmd.exe cần cặp ngoặc kép bọc
     ngoài cùng (nó bỏ đi cặp ngoài). ]]
function M.moTram()
    local fh = io.open(f("tram_lenh.txt"), "r")
    if not fh then return false end
    local lenh = fh:read("*l")
    fh:close()
    if not lenh or lenh == "" then return false end
    if WIN_ENV then lenh = '"' .. lenh .. '"' end
    log("mở trạm retouch chạy ngầm")
    LrTasks.execute(lenh)
    M.tMo = os.time()
    return true
end

--[[ -> "app" | "rieng" | "dang_mo" | nil (không mở được). xinNap: app đang mở mà
     engine chưa nạp thì xin nạp ngay. ]]
function M.damBaoTram(xinNap)
    local a = M.nhip("app")
    local r = M.nhip("rieng")
    if a and (a.san_sang == "1" or not r) then
        if xinNap and a.san_sang ~= "1" then ghiFile(f("xin_nap.txt"), "1\n") end
        return "app"
    end
    if r then return "rieng" end
    if M.tMo and os.time() - M.tMo < 60 then return "dang_mo" end
    return M.moTram() and "dang_mo" or nil
end

function M.moTaTram()
    local a, r = M.nhip("app"), M.nhip("rieng")
    local function may(d) return (d.may and d.may ~= "") and (" · " .. d.may) or "" end
    if a and a.san_sang == "1" then
        return "Sẵn sàng — engine retouch của app đã nạp mô hình" .. may(a) .. ".", true
    end
    if r and r.san_sang == "1" then
        return "Sẵn sàng — trạm retouch chạy ngầm đã nạp mô hình" .. may(r) .. ".", true
    end
    if a then return "App Tone&Retouch đang nạp mô hình retouch…", false end
    if r or (M.tMo and os.time() - M.tMo < 120) then
        return "Đang mở trạm retouch chạy ngầm, nạp mô hình (~10–30 giây)…", false
    end
    if not LrFileUtils.exists(f("tram_lenh.txt")) then
        return "Chưa thấy app Tone&Retouch — mở app một lần để plugin biết cách chạy retouch.", false
    end
    return "Trạm retouch chưa chạy — sẽ tự mở khi bấm Export.", false
end

-- --------------------------------------------------------------------- một ảnh
local dem = 0
local function moiId()
    dem = dem + 1
    return string.format("%d_%d_%04d", os.time(), dem, math.random(0, 9999))
end

local function duoiNhan(path)
    local e = string.lower(LrPathUtils.extension(path) or "")
    return M.DUOI[e] == true
end

--[[ Gửi một ảnh cho trạm, chờ kết quả. -> bảng kết quả (ok/bo_qua/loi/mo_ta/giay). ]]
function M.guiVaCho(anh, goc, cheDo, cho)
    local id = moiId()
    ghiFile(f("yc_" .. id .. ".txt"), table.concat({
        "anh=" .. sach(anh), "goc=" .. sach(goc), "che_do=" .. sach(cheDo),
        "t=" .. tostring(os.time()) }, "\n") .. "\n")
    local kq = f("kq_" .. id .. ".txt")
    local t0 = os.time()
    local daMoLai = false
    while true do
        if LrFileUtils.exists(kq) then
            local d = docKV(kq) or {}
            LrFileUtils.delete(kq)
            return d
        end
        local troi = os.time() - t0
        if troi > cho then break end
        --[[ Không trạm nào còn nhịp quá 20 giây: thử mở trạm chạy ngầm MỘT lần,
             không được thì thôi chờ. ]]
        if troi > 20 and troi % 5 == 0 and not M.nhip("app") and not M.nhip("rieng") then
            if not daMoLai and M.moTram() then
                daMoLai = true
            elseif daMoLai and troi > 120 then
                break
            end
        end
        LrTasks.sleep(M.NGU)
    end
    --  quá giờ: rút yêu cầu nếu trạm chưa nhận; nhận rồi thì cấm trạm đè file
    ghiFile(f("huy_" .. id .. ".txt"), "1\n")
    local yc = f("yc_" .. id .. ".txt")
    if LrFileUtils.exists(yc) then LrFileUtils.delete(yc) end
    return { ok = "0", loi = string.format("quá %d giây chưa xong", cho) }
end

-- ------------------------------------------------------------ hộp Export
M.exportPresetFields = {
    { key = "autotone_rt_bat", default = true },
    { key = "autotone_rt_muc", default = "app" },
}

local function dsPreset()
    local ds = {}
    local fh = io.open(f("presets.txt"), "r")
    if fh then
        for dong in fh:lines() do
            dong = string.gsub(dong, "^\239\187\191", "")
            if dong ~= "" then ds[#ds + 1] = dong end
        end
        fh:close()
    end
    return ds
end

M.lanMo, M.lanDong = 0, 0

function M.startDialog(pt)
    M.lanMo = M.lanMo + 1
    local lan = M.lanMo
    pt.autotone_rt_trang_thai = "Đang kiểm trạm retouch…"
    LrTasks.startAsyncTask(function()
        if pt.autotone_rt_bat == false then
            pt.autotone_rt_trang_thai = "Đang tắt — ảnh xuất ra không retouch."
            return
        end
        M.damBaoTram(true)
        for _ = 1, 360 do                  -- tối đa 3 phút
            if M.lanDong >= lan then return end
            local chu, xong = M.moTaTram()
            pt.autotone_rt_trang_thai = chu
            if xong then return end
            LrTasks.sleep(0.5)
        end
    end)
end

function M.endDialog(_pt)
    M.lanDong = M.lanMo
end

function M.sectionForFilterInDialog(fv, pt)
    local bind = LrView.bind
    local items = { { title = "Theo app — mức đã đặt cho buổi (preview trong app)", value = "app" } }
    for _, ten in ipairs(dsPreset()) do
        items[#items + 1] = { title = "Preset: " .. ten, value = "preset:" .. ten }
    end
    if pt.autotone_rt_trang_thai == nil then
        pt.autotone_rt_trang_thai = (M.moTaTram())
    end
    return {
        title = "AutoTone — Retouch khi xuất",
        fv:row {
            fv:checkbox { title = "Retouch ảnh xuất ra (mức / preset đặt trong app Tone&Retouch)",
                          value = bind "autotone_rt_bat" },
        },
        fv:row {
            fv:static_text { title = "Mức retouch:" },
            fv:popup_menu { items = items, value = bind "autotone_rt_muc",
                            enabled = bind "autotone_rt_bat" },
        },
        fv:static_text { title = bind "autotone_rt_trang_thai", fill_horizontal = 1 },
        fv:static_text {
            title = "Chỉ áp cho ảnh JPEG / TIFF / PNG. Ảnh lỗi vẫn xuất ra (chưa retouch) — xem plugin.log.",
            fill_horizontal = 1,
        },
    }
end

-- ------------------------------------------------------------ lượt Export
function M.postProcessRenderedPhotos(functionContext, filterContext)
    local pt = filterContext.propertyTable or {}
    local bat = pt.autotone_rt_bat ~= false
    local cheDo = pt.autotone_rt_muc or "app"
    if cheDo == "" then cheDo = "app" end
    local tong = #(filterContext.renditionsToSatisfy or {})
    local thanh = nil
    if bat then
        LrTasks.pcall(function()
            thanh = LrProgressScope({ title = "AutoTone: retouch khi xuất",
                                      functionContext = functionContext })
            thanh:setCancelable(true)
            thanh:setCaption(string.format("Chuẩn bị retouch %d ảnh…", tong))
        end)
        local kieu = M.damBaoTram(false)
        log(string.format("bắt đầu %d ảnh · mức %s · trạm %s", tong, cheDo, tostring(kieu)))
    end
    local i, ok, boQua, loi, huyTay = 0, 0, 0, 0, false
    local tCho, tRt = 0, 0
    for sourceRendition, renditionToSatisfy in filterContext:renditions() do
        i = i + 1
        local t0 = os.time()
        local thanhR, duong = sourceRendition:waitForRender()
        tCho = tCho + (os.time() - t0)
        if not thanhR then
            renditionToSatisfy:renditionIsDone(false, duong)
        else
            if bat and thanh and not huyTay then
                local okH, h = LrTasks.pcall(function() return thanh:isCanceled() end)
                if okH and h then
                    huyTay = true
                    log(string.format("bấm ✕ ở ảnh %d/%d — các ảnh còn lại xuất KHÔNG retouch", i, tong))
                end
            end
            if bat and not huyTay and duoiNhan(duong) then
                local goc = ""
                LrTasks.pcall(function()
                    goc = sourceRendition.photo:getRawMetadata("path") or ""
                end)
                if i == 1 then
                    log("ảnh đầu: render " .. tostring(duong) .. " · đích "
                        .. tostring(renditionToSatisfy.destinationPath) .. " · gốc " .. tostring(goc))
                end
                local t1 = os.time()
                local okG, kq = LrTasks.pcall(function()
                    return M.guiVaCho(duong, goc, cheDo, i == 1 and M.CHO_DAU or M.CHO_MOI_ANH)
                end)
                tRt = tRt + (os.time() - t1)
                if not okG then kq = { ok = "0", loi = tostring(kq) } end
                if kq.ok == "1" and kq.bo_qua == "1" then
                    boQua = boQua + 1
                    if boQua <= 3 then
                        log(LrPathUtils.leafName(duong) .. ": không retouch — " .. tostring(kq.mo_ta))
                    end
                elseif kq.ok == "1" then
                    ok = ok + 1
                else
                    loi = loi + 1
                    if loi <= 10 then
                        log(LrPathUtils.leafName(duong) .. ": xuất CHƯA retouch — " .. tostring(kq.loi))
                    end
                end
            end
            renditionToSatisfy:renditionIsDone(true, "")
        end
        if thanh then
            LrTasks.pcall(function()
                thanh:setPortionComplete(i, tong)
                thanh:setCaption(string.format("Retouch %d/%d ảnh%s", i, tong,
                                 loi > 0 and string.format(" · %d ảnh chưa retouch", loi) or ""))
            end)
        end
    end
    if thanh then LrTasks.pcall(function() thanh:done() end) end
    if bat then
        log(string.format("xong %d ảnh: retouch %d, không cần %d, CHƯA retouch %d%s · chờ render %d s, chờ retouch %d s",
                          i, ok, boQua, loi, huyTay and " (bấm ✕)" or "", tCho, tRt))
        if loi > 0 then
            LrTasks.pcall(function()
                LrDialogs.showBezel(string.format("AutoTone: %d ảnh xuất ra CHƯA retouch — xem plugin.log", loi), 6)
            end)
        end
    end
end

return M
