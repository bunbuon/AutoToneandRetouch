--[[ XUẤT ẢNH GIAO KHÁCH — app bấm, Lightroom xuất, không mở hộp thoại nào.

     ============================================================
     VÌ SAO CÓ FILE NÀY BÊN CẠNH BatDuongDan.lua
     ============================================================

     Hai cái giải hai nửa của cùng một vấn đề, và cố tình không phụ thuộc nhau:

       BatDuongDan.lua  — anh vẫn Export bằng Lightroom như xưa, plugin chỉ
                          đứng nghe và chép lại thư mục đích.
       XuatCore.lua     — app tự chạy lượt Export. Lúc đó thư mục đích là do
                          app đặt ra, nên không còn gì để hỏi, để nghe, để
                          đoán. Chắc chắn tuyệt đối.

     Hỏng cái này thì cái kia vẫn chạy. Đó là lý do chúng nằm riêng.

     ============================================================
     THÔNG SỐ EXPORT LẤY TỪ ĐÂU
     ============================================================

     KHÔNG dựng lại hộp thoại Export trong app, và KHÔNG tự nghĩ ra thông số.
     App đọc đúng thông số Lightroom đang dùng (file cấu hình .agprefs, hoặc
     preset .lrtemplate người dùng lưu) rồi gửi sang đây nguyên vẹn — xem
     thongso_lr.py. Ở đây chỉ nhận và dùng.

     Vì gửi qua file văn bản nên phải mang theo KIỂU: "false" là chữ hay là
     giá trị sai? 0.7 là số hay là chuỗi? Sai kiểu thì Lightroom lặng lẽ bỏ
     qua khoá đó — đúng cái bệnh "xuất ra ảnh 1 điểm ảnh mà không báo lỗi" đã
     ghi ở đầu DuyetCore.lua. Nên mỗi dòng có dạng:

         ts <TAB> s|n|b <TAB> tên khoá <TAB> giá trị

     ============================================================
     KHÔNG DÙNG pcall QUANH LỜI GỌI SDK — dùng Core.try(). Xem AutoToneCore.lua.
]]

local LrApplication   = import "LrApplication"
local LrExportSession = import "LrExportSession"
local LrFileUtils     = import "LrFileUtils"
local LrPathUtils     = import "LrPathUtils"
local LrProgressScope = import "LrProgressScope"
local LrTasks         = import "LrTasks"

local Core = require "AutoToneCore"

local M = {}

M.YEU_CAU  = "request_xuatanh.txt"
M.TIEN_DO  = "xuatanh_tiendo.txt"
M.CO_DUNG  = "request_xuatanh_dung.txt"
--[[ 9/10 (Xuất một thao tác — app vừa xuất vừa retouch): bảng ẢNH GỐC -> FILE
     RA, ghi lại sau MỖI LÔ như DuyetCore.ghiBang. App cần nó vì tên file ra có
     thể khác tên gốc (quy tắc đặt tên trong thông số Export của người dùng):
     không có bảng thì vòng theo dõi thư mục chỉ đoán được theo tên gốc. ]]
M.BANG     = "xuatanh_anh.tsv"
--[[ 10/10 (kế thừa NEXUS AI Retouch): HÀNG ĐỢI — mỗi ảnh một dòng "<gốc>\t<jpg>"
     ghi NGAY sau waitForRender (file đã ghi xong), dòng cuối "#het\t<số ảnh ra>".
     App retouch từng ảnh ngay khi có, không phải quét thư mục rồi chờ file đứng
     yên qua hai lần quét (~2–4 s mỗi ảnh). Bảng M.BANG vẫn giữ cho bản app cũ. ]]
M.HANG_DOI = "xuatanh_hangdoi.tsv"

--[[ 9/10 — XUẤT MỘT LẦN, KHÔNG CHIA LÔ (user: "Khi chọn xuất ảnh trong Lightroom
     sẽ xuất 1 lần toàn bộ ảnh luôn. K chia nhỏ 15 ảnh nữa"). Trước đây mỗi 15 ảnh
     là một LrExportSession mới: Lightroom dựng lại phiên, hiện từng đợt nhỏ, và
     giữa hai đợt thì đứng. Giờ MỘT phiên cho cả lượt — Lightroom tự xếp hàng / vẽ
     song song như khi anh Export tay. Vẫn theo dõi TỪNG ẢNH bằng
     session:renditions() + rendition:waitForRender() (cách SDK đưa cho
     LrExportSession): xong ảnh nào là đếm, ghi bảng ảnh gốc -> file ra, ghi nhịp
     sống (thưa: GHI_MOI_GIAY); cờ dừng kiểm trước MỖI ảnh -> phần còn lại
     rendition:skipRender(). ]]
M.GHI_MOI_GIAY = 2

function M.xinDung()
    return LrFileUtils.exists(LrPathUtils.child(Core.jobDir(), M.CO_DUNG))
end

function M.xoaCoDung()
    Core.try("xoaCoDungXuat", function()
        LrFileUtils.delete(LrPathUtils.child(Core.jobDir(), M.CO_DUNG))
        return true
    end)
end

function M.ghiTienDo(bang)
    local dir = Core.jobDir()
    if not LrFileUtils.exists(dir) then LrFileUtils.createAllDirectories(dir) end
    local dest = LrPathUtils.child(dir, M.TIEN_DO)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return nil end
    for _, k in ipairs({ "trang_thai", "xong", "tong", "loi", "thu_muc",
                         "bo_sao", "thong_bao", "tsv" }) do
        if bang[k] ~= nil then fh:write(k .. "=" .. tostring(bang[k]) .. "\n") end
    end
    fh:close()
    Core.try("ghiTienDoXuat", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)
    return dest
end

-- ------------------------------------------------------------ đọc yêu cầu

--[[ Hàm THUẦN: nhận mảng dòng, trả về (thư mục nguồn, opts, thongSo).

     Tách thuần để bài kiểm gọi thẳng, không cần Lightroom, không cần đĩa.
     Mọi lỗi phân tích ở đây đều là lỗi im lặng nếu không kiểm được. ]]
function M.docDong(dong)
    local folder, opts, ts = nil, {}, {}
    for i = 1, #dong do
        local d = dong[i]
        if i == 1 then
            folder = string.gsub(d, "^%s*(.-)%s*$", "%1")
        else
            local kieu, khoa, gt = string.match(d, "^ts\t([snb])\t([%w_]+)\t(.*)$")
            if kieu then
                if kieu == "n" then
                    --[[ tonumber that bai -> BO QUA khoa do, tuyet doi khong
                         nhet chuoi vao cho cho so. Lightroom nhan chuoi o o so
                         thi bo qua ca khoa ma khong noi gi. ]]
                    local so = tonumber(gt)
                    if so then ts[khoa] = so end
                elseif kieu == "b" then
                    ts[khoa] = (gt == "true" or gt == "True" or gt == "1")
                else
                    ts[khoa] = gt
                end
            else
                local k, v = string.match(d, "^%s*([%w_]+)%s*=%s*(.-)%s*$")
                if k then opts[k] = v end
            end
        end
    end
    return folder, opts, ts
end

-- ----------------------------------------------------------------- xuất ảnh

--[[ Bảng ảnh gốc -> file ra, ghi đè cả bảng (.part rồi đổi tên). ]]
function M.ghiBang(cap)
    local d = Core.jobDir()
    if not LrFileUtils.exists(d) then LrFileUtils.createAllDirectories(d) end
    local path = LrPathUtils.child(d, M.BANG)
    local tmp = path .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return nil end
    fh:write("path\tjpg\n")
    for _, c in ipairs(cap) do
        fh:write(tostring(c.src) .. "\t" .. tostring(c.jpg) .. "\n")
    end
    fh:close()
    Core.try("ghiBangXuat", function()
        LrFileUtils.delete(path)
        LrFileUtils.move(tmp, path)
        return true
    end)
    return path
end

function M.xoaBang()
    Core.try("xoaBangXuat", function()
        LrFileUtils.delete(LrPathUtils.child(Core.jobDir(), M.BANG))
        return true
    end)
    Core.try("xoaHangDoiXuat", function()
        LrFileUtils.delete(LrPathUtils.child(Core.jobDir(), M.HANG_DOI))
        return true
    end)
end

local function duongHangDoi() return LrPathUtils.child(Core.jobDir(), M.HANG_DOI) end

--[[ Hàng đợi: mở mới (rỗng) đầu lượt, thêm từng dòng (mở "a" — mỗi dòng ghi trọn
     rồi đóng, app đọc tới dòng nào đủ "\n" thì lấy dòng đó). ]]
function M.moHangDoi()
    local fh = io.open(duongHangDoi(), "w")
    if fh then fh:close() end
end

function M.themHangDoi(src, jpg)
    local fh = io.open(duongHangDoi(), "a")
    if fh then
        fh:write(tostring(src) .. "\t" .. tostring(jpg) .. "\n")
        fh:close()
    end
end

function M.hetHangDoi(n)
    local fh = io.open(duongHangDoi(), "a")
    if fh then
        fh:write("#het\t" .. tostring(n) .. "\n")
        fh:close()
    end
end

--[[ Xuất cả danh sách trong MỘT phiên. tienDo(daLam, tong, ra) gọi khi ghi tiến độ.
     Đếm theo FILE CÓ THẬT TRÊN ĐĨA (waitForRender trả đường dẫn + kiểm tồn tại),
     không đếm theo số ảnh đưa vào — đếm vậy thì lượt nào cũng "thành công 100%"
     kể cả khi ổ đầy. ]]
function M.xuat(photos, dest, thongSo, _lo, tienDo)
    if not LrFileUtils.exists(dest) then
        LrFileUtils.createAllDirectories(dest)
    end
    -- đường dẫn gốc lấy TRƯỚC khi export, lúc còn chắc chắn đọc được
    local goc = {}
    Core.try("docDuongDanGiao", function()
        for i = 1, #photos do goc[i] = photos[i]:getRawMetadata("path") end
        return true
    end)
    local tong = #photos
    --  thư mục đích do app đặt THẮNG mọi đường dẫn có sẵn trong thông số
    thongSo.LR_export_destinationPathPrefix = dest
    local session = LrExportSession({ photosToExport = photos, exportSettings = thongSo })
    local ra, daLam, cap, dung, lanGhi, soLoi = 0, 0, {}, false, -1000, 0
    M.moHangDoi()

    --[[ 10/10 (user: "khi bấm xuất trên tool thì trong Lightroom cũng cần hiển thị tiến
         trình xuất, và có thể cancel trong Lightroom"): thanh tiến độ KHÔNG chặn ở góc
         trên trái Lightroom (LrProgressScope — không phải hộp thoại modal như Duyệt
         nhanh: người dùng vẫn làm việc trong Lightroom được). Bấm ✕ trên thanh = dừng
         như nút Dừng của app: ảnh còn lại skipRender, ảnh đã ra vẫn được retouch. ]]
    local thanhLR = nil
    local tenDich = LrPathUtils.leafName(dest) or dest
    Core.try("moThanhTienDo", function()
        thanhLR = LrProgressScope({ title = "AutoTone: xuất ảnh" })
        thanhLR:setCancelable(true)
        thanhLR:setCaption(string.format("Chuẩn bị xuất %d ảnh → %s", tong, tenDich))
        return true
    end)
    local huyLR = false
    local function capNhatThanh()
        if not thanhLR then return end
        Core.try("thanhTienDo", function()
            thanhLR:setPortionComplete(daLam, tong)
            thanhLR:setCaption(string.format("Xuất ảnh %d/%d → %s", daLam, tong, tenDich))
            return true
        end)
    end
    local function lrBamHuy()
        if not thanhLR then return false end
        local huy = Core.try("thanhHuy", function() return thanhLR:isCanceled() end)
        return huy == true
    end
    --[[ DỪNG THẬT (10/10): skipRender KHÔNG chặn được Lightroom render nền nốt cả
         phiên — đo thật: dừng ở 195/554 lúc 02:05:14 mà thư mục xuất vẫn nhận 359
         ảnh cỡ gốc tới 02:13. Phiên gắn vào thanh tiến độ (renditions{progressScope,
         stopIfCanceled}); dừng từ app thì HUỶ thanh — như bấm ✕ của Lightroom —
         Lightroom bỏ phần render còn lại. ]]
    local function huyThanh()
        if thanhLR then Core.try("huyThanh", function() thanhLR:cancel() return true end) end
    end
    local thamSo = thanhLR and { progressScope = thanhLR, renderProgressPortion = 1,
                                 stopIfCanceled = true } or nil

    local function ghi(cuoi)
        local bay = os.time()
        if not cuoi and bay - lanGhi < M.GHI_MOI_GIAY then return end
        lanGhi = bay
        local tsv = M.ghiBang(cap)
        if tienDo then tienDo(daLam, tong, ra) end
        M.ghiTienDo({ trang_thai = "dang_chay", xong = daLam, tong = tong,
                      loi = daLam - ra, thu_muc = dest, tsv = tsv })
        --[[ NHỊP SỐNG kèm bước: lượt xuất cả nghìn ảnh cỡ gốc chặn vòng lặp plugin
             hàng chục phút; không ghi nhịp thì app thấy plugin_song.txt cũ 45 s là
             báo "plugin chết". Bản Core cũ không có hàm thì bỏ qua. ]]
        if type(Core.ghiNhip) == "function" then
            Core.try("nhipXuat", function()
                return Core.ghiNhip(nil, 0, string.format("xuất ảnh %d/%d", daLam, tong))
            end)
        end
    end

    local _, err = Core.try("xuatMotPhien", function()
        local i = 0
        for _, r in session:renditions(thamSo) do
            i = i + 1
            if not dung and M.xinDung() then
                dung = true
                M.xoaCoDung()
                huyThanh()
                Core.log(string.format("xuatanh: nguoi dung xin dung o anh %d/%d", daLam, tong))
            end
            if not dung and lrBamHuy() then
                dung, huyLR = true, true
                Core.log(string.format("xuatanh: huy tren thanh tien do Lightroom o anh %d/%d",
                                       daLam, tong))
            end
            if dung then
                Core.try("boQuaAnhGiao", function() r:skipRender(); return true end)
            else
                local thanh, duong = r:waitForRender()
                daLam = daLam + 1
                if thanh and duong and duong ~= "" and LrFileUtils.exists(duong) then
                    ra = ra + 1
                    --[[ Ảnh gốc của rendition: hỏi thẳng (r.photo), không được thì
                         theo thứ tự — tên ra có thể đã đổi theo quy tắc đặt tên. ]]
                    local src = nil
                    if r.photo then
                        src = Core.try("docGocGiao", function()
                            return r.photo:getRawMetadata("path")
                        end)
                    end
                    cap[#cap + 1] = { src = src or goc[i] or duong, jpg = duong }
                    M.themHangDoi(cap[#cap].src, duong)      -- app retouch NGAY ảnh này
                else
                    soLoi = soLoi + 1
                    if soLoi <= 5 then
                        Core.log("xuatanh: anh khong ra file -> " .. tostring(duong))
                    end
                end
                ghi(false)
                capNhatThanh()
                LrTasks.yield()
            end
        end
        return true
    end)
    if err then
        Core.log("xuatanh: LOI phien xuat -> " .. tostring(err))
    end
    --  bấm ✕ trên thanh Lightroom: vòng lặp tự dừng (stopIfCanceled) trước khi kịp hỏi
    if not dung and daLam < tong and lrBamHuy() then
        dung, huyLR = true, true
        Core.log(string.format("xuatanh: huy tren thanh tien do Lightroom o anh %d/%d", daLam, tong))
    end
    --  "#het" TRƯỚC tiến độ "xong": app thấy Lightroom xong là hàng đợi đã đủ
    M.hetHangDoi(ra)
    ghi(true)
    if thanhLR then
        Core.try("dongThanhTienDo", function() thanhLR:done() return true end)
    end
    --[[ 'loi' tinh tren SO DA LAM, khong tren tong: anh chua toi luot (dung giua
         chung) khong phai la loi — cung ly do da ghi o DuyetCore.xuatDuyet. ]]
    return { ra = ra, loi = daLam - ra, da_dung = dung, da_lam = daLam, huy_lr = huyLR }
end

-- ------------------------------------------------------- yêu cầu từ phía app

function M.runRequest()
    local req = LrPathUtils.child(Core.jobDir(), M.YEU_CAU)
    if not LrFileUtils.exists(req) then return 0 end
    local claimed = Core.claim(req)
    if not claimed then return 0 end

    local dong = {}
    local fh = io.open(claimed, "r")
    if fh then
        for line in fh:lines() do dong[#dong + 1] = line end
        fh:close()
    end
    Core.try("boYeuCauXuat", function() LrFileUtils.delete(claimed) end)

    local folder, opts, ts = M.docDong(dong)
    if not folder or folder == "" then
        M.ghiTienDo({ trang_thai = "loi", thong_bao = "thieu duong dan nguon" })
        return 0
    end
    local dest = opts.dest
    if not dest or dest == "" then
        M.ghiTienDo({ trang_thai = "loi", thong_bao = "thieu thu muc dich" })
        return 0
    end

    --[[ Khong co thong so thi DUNG LAI, khong tu bia mot bo mac dinh.
         Tu bia thong so cho anh giao khach la kieu sai te nhat: anh van ra,
         nhin qua van dep, nhung khac han thu anh van giao. ]]
    if not ts.LR_format then
        M.ghiTienDo({ trang_thai = "loi",
                      thong_bao = "thieu thong so export (khong tu bia)" })
        Core.log("xuatanh: yeu cau khong kem thong so -> bo qua")
        return 0
    end
    ts.LR_export_destinationPathPrefix = dest

    local catalog = LrApplication.activeCatalog()
    local photos = Core.photosInFolder(catalog, folder)
    if not photos or #photos == 0 then
        M.ghiTienDo({ trang_thai = "loi", thong_bao = "khong thay anh nao" })
        return 0
    end

    --[[ Loc anh 1 sao dung ham da co trong DuyetCore — cung mot quy uoc voi
         writeExport va voi burst_reject_rating cua autotone: anh 1 sao khong
         xuat, khong retouch. Viet lai o day la mo duong cho hai quy uoc lech
         nhau. DuyetCore co the vang mat (ban plugin cu) nen phai kiem. ]]
    local boSao = 0
    local okD, Duyet = pcall(require, "DuyetCore")
    if okD and type(Duyet.locSao) == "function" then
        photos, boSao = Duyet.locSao(photos, opts.bo_sao)
    end
    if #photos == 0 then
        M.ghiTienDo({ trang_thai = "loi", thong_bao = "loc xong khong con anh nao" })
        return 0
    end

    M.xoaCoDung()          -- cờ sót của lần trước làm lượt mới dừng ngay lô đầu
    M.xoaBang()            -- bảng của lượt trước: app đọc nhầm là ảnh lượt này
    local t0 = os.time()
    M.ghiTienDo({ trang_thai = "dang_chay", xong = 0, tong = #photos,
                  thu_muc = dest, bo_sao = boSao })

    local res, err = Core.try("xuatAnhGiao", function()
        return M.xuat(photos, dest, ts)
    end)
    if not res then
        Core.log("xuatanh: LOI -> " .. tostring(err))
        M.ghiTienDo({ trang_thai = "loi", thong_bao = tostring(err) })
        return 0
    end

    local giay = os.time() - t0
    M.ghiTienDo({ trang_thai = res.da_dung and "dung" or "xong",
                  xong = res.ra, tong = res.da_lam, loi = res.loi,
                  thu_muc = dest, bo_sao = boSao,
                  thong_bao = (res.huy_lr and "da huy tren thanh tien do Lightroom, " or "")
                      .. string.format("%d giay, %.2f giay/anh", giay,
                                       (res.ra > 0) and (giay / res.ra) or 0) })
    Core.log(string.format("xuatanh: ra %d/%d anh vao %s (%d giay)",
                           res.ra, res.da_lam, dest, giay))
    return res.ra
end

return M
