--[[ DANH SÁCH ẢNH CỦA BUỔI TRONG CATALOG — 13/10.

     User 13/10: "Ở lưới Preview, chỉ load các ảnh mà trong lightroom đang hiển
     thị. Ví dụ tổng 1000 ảnh, khi người dùng xoá 10 ảnh đi thì ngoài preview
     cũng sẽ chỉ hiện 990 ảnh … và ngược lại".

     App ghi jobs/theo_doi_ds.txt (dòng 1 = thư mục buổi, sau đó khoá=giá_trị:
     con=1 gồm thư mục con). Mỗi vòng lặp nền (Init.lua) gọi M.runTheoDoi():
     cứ ~4 giây đọc lại danh sách ảnh của thư mục đó trong catalog, và CHỈ KHI
     KHÁC lần trước (xoá / gỡ / thêm ảnh, đổi buổi) mới ghi jobs/ds_catalog.tsv
     (.part rồi đổi tên — app không đọc phải file đang ghi):

         #thu_muc=<thư mục>
         #trong_catalog=1|0
         #so=<số ảnh>
         #khi=<giờ>
         <đường dẫn ảnh>          (mỗi dòng một ảnh, GỒM CẢ ảnh 1 sao)

     KHÁC bản xuất thông số (export_*.tsv): bản đó bỏ ảnh 1 sao, chỉ làm khi app
     nhờ, và nặng (đọc develop settings). Đây chỉ đọc đường dẫn — rẻ, chạy đều.

     trong_catalog=0: thư mục chưa import (getFolderByPath trả nil) — app KHÔNG
     lọc gì (hiện cả buổi), khác với "có trong catalog mà 0 ảnh" (lọc hết).

     KHÔNG pcall quanh lời gọi SDK — dùng Core.try (xem đầu AutoToneCore.lua). ]]

local LrApplication = import "LrApplication"
local LrFileUtils   = import "LrFileUtils"
local LrPathUtils   = import "LrPathUtils"
local LrTasks       = import "LrTasks"

local Core = require "AutoToneCore"

local M = {}

M.YEU_CAU = "theo_doi_ds.txt"
M.FILE_DS = "ds_catalog.tsv"
M.CACH_GIAY = 4

local lanCuoi = 0
local daGhi = nil            -- chữ ký lần ghi trước: thư mục + danh sách

--[[ Hàm THUẦN (bài kiểm gọi được, không cần Lightroom): nội dung file từ
     thư mục + danh sách đường dẫn (đã sắp) + có trong catalog hay không. ]]
function M.noiDung(thuMuc, ds, trongCatalog, khi)
    local dong = {
        "#thu_muc=" .. tostring(thuMuc or ""),
        "#trong_catalog=" .. (trongCatalog and "1" or "0"),
        "#so=" .. tostring(#ds),
        "#khi=" .. tostring(khi or ""),
    }
    for i = 1, #ds do dong[#dong + 1] = ds[i] end
    return table.concat(dong, "\n") .. "\n"
end

--[[ Đọc yêu cầu: (thư mục, gồm thư mục con) hoặc nil. ]]
function M.docYeuCau(path)
    local fh = io.open(path, "r")
    if not fh then return nil end
    local thuMuc = fh:read("*l")
    local opts = {}
    for line in fh:lines() do
        local k, v = string.match(line, "^%s*([%w_]+)%s*=%s*(.-)%s*$")
        if k then opts[k] = v end
    end
    fh:close()
    if not thuMuc then return nil end
    thuMuc = (string.gsub(thuMuc, "^%s*(.-)%s*$", "%1"))
    if thuMuc == "" then return nil end
    return thuMuc, opts.con ~= "0"
end

--[[ Đường dẫn các ảnh của thư mục trong catalog, đã sắp. Thư mục không có
     trong catalog -> (rỗng, false). Bản sao ảo trùng đường dẫn gốc: gộp một. ]]
function M.dsTrongCatalog(catalog, thuMuc, gomCon)
    local f = catalog:getFolderByPath(thuMuc)
    if not f or type(f.getPhotos) ~= "function" then return {}, false end
    local photos = f:getPhotos(gomCon) or {}
    local seen, ds = {}, {}
    local paths = nil
    if #photos > 0 and type(catalog.batchGetRawMetadata) == "function" then
        paths = catalog:batchGetRawMetadata(photos, { "path" })
    end
    for i = 1, #photos do
        local p
        if paths and paths[photos[i]] then
            p = paths[photos[i]].path
        else
            p = photos[i]:getRawMetadata("path")
        end
        if p and p ~= "" and not seen[p] then
            seen[p] = true
            ds[#ds + 1] = p
        end
        if i % 1000 == 0 then LrTasks.yield() end
    end
    table.sort(ds)
    return ds, true
end

local function ghiFile(dest, chu)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return false end
    fh:write(chu)
    fh:close()
    Core.try("dsCatalogDoiTen", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)
    return true
end

--[[ Gọi mỗi vòng lặp nền. Trả về true nếu vừa ghi file mới. ]]
function M.runTheoDoi(ep)
    local dir = Core.jobDir()
    local req = LrPathUtils.child(dir, M.YEU_CAU)
    if not LrFileUtils.exists(req) then
        daGhi = nil
        return false
    end
    local bayGio = os.time()
    if not ep and bayGio - lanCuoi < M.CACH_GIAY then return false end
    lanCuoi = bayGio
    local thuMuc, gomCon = M.docYeuCau(req)
    if not thuMuc then return false end
    local catalog = LrApplication.activeCatalog()
    local kq, err = Core.try("dsTrongCatalog", function()
        local ds, co = M.dsTrongCatalog(catalog, thuMuc, gomCon)
        return { ds = ds, co = co }
    end)
    if err or type(kq) ~= "table" then
        Core.log("danh sach catalog LOI: " .. tostring(err))
        return false
    end
    local kyMoi = thuMuc .. "|" .. tostring(gomCon) .. "|" .. tostring(kq.co) .. "|"
                  .. table.concat(kq.ds, "|")
    local dest = LrPathUtils.child(dir, M.FILE_DS)
    if kyMoi == daGhi and LrFileUtils.exists(dest) then return false end
    if ghiFile(dest, M.noiDung(thuMuc, kq.ds, kq.co, os.date("%Y-%m-%d %H:%M:%S"))) then
        if daGhi ~= nil then
            Core.log(string.format("danh sach catalog doi: %d anh trong %s",
                                   #kq.ds, LrPathUtils.leafName(thuMuc)))
        end
        daGhi = kyMoi
        return true
    end
    return false
end

--[[ CÂY THƯ MỤC CỦA CATALOG — 13/10.

     User 13/10: "thiết kế 1 cột liệt kê ra các ổ và các folder đã được thêm vào
     tool như Lightroom. Xem có lấy được luôn từ Lightroom ra hiển thị cũng đc".

     App ghi jobs/theo_doi_thu_muc.txt (ghi lại = xin làm mới ngay). Cứ ~2 phút
     (hoặc ngay khi file yêu cầu đổi giờ sửa) plugin đọc catalog:getFolders() —
     các thư mục gốc như panel Folders — đi xuống getChildren(), đếm ảnh RIÊNG
     từng thư mục (getPhotos(false)), CHỈ ghi jobs/thu_muc_catalog.tsv khi khác:

         #khi=<giờ>
         <đường dẫn>\t<thư mục cha, rỗng = gốc>\t<số ảnh riêng>

     App tự cộng số ảnh của thư mục con (Lightroom hiện số gộp). ]]
M.YC_THU_MUC = "theo_doi_thu_muc.txt"
M.FILE_THU_MUC = "thu_muc_catalog.tsv"
M.CACH_THU_MUC = 120          -- dem anh moi thu muc cua catalog lon ton vai giay

local lanThuMuc, kyThuMuc, mtYcThuMuc = 0, nil, nil

--[[ Các dòng "đường dẫn \t cha \t số ảnh" của cả cây thư mục catalog. ]]
function M.dongThuMuc(catalog)
    local ra = {}
    local function di(f, cha)
        local p = f:getPath()
        if not p or p == "" then return end
        local ds = f:getPhotos(false) or {}
        ra[#ra + 1] = p .. "\t" .. (cha or "") .. "\t" .. tostring(#ds)
        if #ra % 40 == 0 then LrTasks.yield() end
        local con = (type(f.getChildren) == "function" and f:getChildren()) or {}
        for i = 1, #con do di(con[i], p) end
    end
    local goc = catalog:getFolders() or {}
    for i = 1, #goc do di(goc[i], nil) end
    return ra
end

local function mtCua(path)
    if type(LrFileUtils.fileAttributes) ~= "function" then return nil end
    local a = LrFileUtils.fileAttributes(path)
    return a and a.fileModificationDate
end

function M.runThuMuc(ep)
    local dir = Core.jobDir()
    local req = LrPathUtils.child(dir, M.YC_THU_MUC)
    if not LrFileUtils.exists(req) then
        kyThuMuc = nil
        return false
    end
    local mt = mtCua(req)
    local moiXin = mt ~= nil and mt ~= mtYcThuMuc
    local bayGio = os.time()
    if not ep and not moiXin and bayGio - lanThuMuc < M.CACH_THU_MUC then return false end
    lanThuMuc, mtYcThuMuc = bayGio, mt
    local catalog = LrApplication.activeCatalog()
    local dong, err = Core.try("thuMucCatalog", function() return M.dongThuMuc(catalog) end)
    if err or type(dong) ~= "table" then
        Core.log("cay thu muc catalog LOI: " .. tostring(err))
        return false
    end
    local than = table.concat(dong, "\n")
    local dest = LrPathUtils.child(dir, M.FILE_THU_MUC)
    if than == kyThuMuc and LrFileUtils.exists(dest) and not moiXin then return false end
    if ghiFile(dest, "#khi=" .. os.date("%Y-%m-%d %H:%M:%S") .. "\n" .. than .. "\n") then
        kyThuMuc = than
        return true
    end
    return false
end

return M
