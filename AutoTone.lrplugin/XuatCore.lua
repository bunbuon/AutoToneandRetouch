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
local LrTasks         = import "LrTasks"

local Core = require "AutoToneCore"

local M = {}

M.YEU_CAU  = "request_xuatanh.txt"
M.TIEN_DO  = "xuatanh_tiendo.txt"
M.CO_DUNG  = "request_xuatanh_dung.txt"

--[[ Ảnh giao khách nặng hơn ảnh duyệt nhiều nên lô nhỏ hơn: người dùng thấy
     tiến trình nhúc nhích thường xuyên hơn, và xin dừng thì dừng nhanh hơn.
     Vẫn chia lô vì đúng ba lý do đã ghi ở DuyetCore.lua. ]]
M.LO = 15

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
                         "bo_sao", "thong_bao" }) do
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

--[[ Xuất một lô. Trả về số file thật sự ra được.

     Đếm theo FILE CÓ THẬT TRÊN ĐĨA (qua rendition.destinationPath), không đếm
     theo số ảnh đưa vào. Đếm theo số đưa vào thì lượt nào cũng "thành công
     100%" kể cả khi ổ đầy. ]]
local function xuatMotLo(photos, thongSo)
    local session = LrExportSession({
        photosToExport = photos,
        exportSettings = thongSo,
    })
    local _, err = Core.try("doExportGiao", function()
        session:doExportOnCurrentTask()
        return true
    end)
    if err then
        Core.log("xuatanh: LOI mot lo -> " .. tostring(err))
    end
    local ra = 0
    Core.try("docRenditionsGiao", function()
        for _, r in session:renditions() do
            local p = r.destinationPath
            if p and p ~= "" and LrFileUtils.exists(p) then ra = ra + 1 end
        end
        return true
    end)
    return ra
end

function M.xuat(photos, dest, thongSo, lo, tienDo)
    lo = tonumber(lo) or M.LO
    if lo < 1 then lo = 1 end
    if not LrFileUtils.exists(dest) then
        LrFileUtils.createAllDirectories(dest)
    end

    local ra, idx = 0, 1
    while idx <= #photos do
        local last = math.min(idx + lo - 1, #photos)
        local nhom = {}
        for i = idx, last do nhom[#nhom + 1] = photos[i] end

        ra = ra + xuatMotLo(nhom, thongSo)
        if tienDo then tienDo(last, #photos, ra) end
        M.ghiTienDo({ trang_thai = "dang_chay", xong = last, tong = #photos,
                      loi = last - ra, thu_muc = dest })
        LrTasks.yield()
        idx = last + 1

        if M.xinDung() then
            M.xoaCoDung()
            Core.log(string.format("xuatanh: nguoi dung xin dung o anh %d/%d",
                                   last, #photos))
            --[[ 'loi' tinh tren SO DA LAM, khong tren tong: may tam chua toi
                 luot khong phai la loi. Dem chung vao loi la bao dong gia —
                 cung ly do da ghi o DuyetCore.xuatDuyet. ]]
            return { ra = ra, loi = last - ra, da_dung = true, da_lam = last }
        end
    end
    return { ra = ra, loi = #photos - ra, da_dung = false, da_lam = #photos }
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
    local t0 = os.time()
    M.ghiTienDo({ trang_thai = "dang_chay", xong = 0, tong = #photos,
                  thu_muc = dest, bo_sao = boSao })

    local res, err = Core.try("xuatAnhGiao", function()
        return M.xuat(photos, dest, ts, tonumber(opts.lo))
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
                  thong_bao = string.format("%d giay, %.2f giay/anh", giay,
                                            (res.ra > 0) and (giay / res.ra) or 0) })
    Core.log(string.format("xuatanh: ra %d/%d anh vao %s (%d giay)",
                           res.ra, res.da_lam, dest, giay))
    return res.ra
end

return M
