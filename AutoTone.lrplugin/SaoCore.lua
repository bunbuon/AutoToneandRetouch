--[[ CHẤM SAO TỪ APP — 14/10.

     User 14/10: "Thêm tính năng nhận diện ảnh rate theo mức trong lightroom. Bên
     ngoài preview cũng thêm tính năng rate ảnh 1-5 sao như Lr".

     App ghi jobs/request_sao.txt:
         #ma=<mã lượt>
         <số sao 0–5>\t<đường dẫn ảnh>      (mỗi dòng một ảnh)
     Plugin đặt rating trong Lightroom (setRawMetadata — rating không phải develop
     setting), ghi jobs/ketqua_sao.txt (ma, tong, xong, khong_thay, loi, khi). App đọc
     lại số sao THẬT thẳng từ catalog (catalog_lr.py), không tin file kết quả.

     Số sao 0 = bỏ sao. Lightroom nào không nhận 0 thì thử lại với nil.
     KHÔNG pcall quanh lời gọi SDK — dùng Core.try (xem đầu AutoToneCore.lua). ]]

local LrApplication = import "LrApplication"
local LrFileUtils   = import "LrFileUtils"
local LrPathUtils   = import "LrPathUtils"

local Core = require "AutoToneCore"

local M = {}

M.YEU_CAU = "request_sao.txt"
M.KET_QUA = "ketqua_sao.txt"

--[[ Hàm THUẦN: (mã, {{p=đường dẫn, sao=0..5}}) từ nội dung file yêu cầu. ]]
function M.phanTich(chu)
    local ma, ds = "", {}
    for dong in string.gmatch(chu or "", "[^\r\n]+") do
        local m = string.match(dong, "^#ma=(.*)$")
        if m then
            ma = m
        elseif string.sub(dong, 1, 1) ~= "#" then
            local n, p = string.match(dong, "^%s*(%d)%s*\t(.+)$")
            n = tonumber(n)
            if n and p and n >= 0 and n <= 5 then
                ds[#ds + 1] = { p = string.gsub(p, "%s+$", ""), sao = n }
            end
        end
    end
    return ma, ds
end

local function ghiKetQua(t)
    local dest = LrPathUtils.child(Core.jobDir(), M.KET_QUA)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return end
    for _, k in ipairs({ "ma", "tong", "xong", "khong_thay", "loi", "khi" }) do
        if t[k] ~= nil then fh:write(k .. "=" .. tostring(t[k]) .. "\n") end
    end
    fh:close()
    Core.try("saoGhi", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)
end

local function datSao(catalog, viec, khongDungSo0)
    return Core.try("saoDat", function()
        catalog:withWriteAccessDo("AutoTone: chấm sao", function()
            for _, v in ipairs(viec) do
                local gt = v.sao
                if gt == 0 and khongDungSo0 then gt = nil end
                v.photo:setRawMetadata("rating", gt)
            end
        end, { timeout = 10 })
        return true
    end)
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
    Core.try("saoXoaYc", function() LrFileUtils.delete(claimed) end)
    local ma, ds = M.phanTich(chu)
    local kq = { ma = ma, tong = #ds, xong = 0, khong_thay = 0, loi = 0 }
    local catalog = LrApplication.activeCatalog()
    local viec = {}
    for i = 1, #ds do
        local p = Core.try("saoTim", function() return catalog:findPhotoByPath(ds[i].p) end)
        if p then
            viec[#viec + 1] = { photo = p, sao = ds[i].sao }
        else
            kq.khong_thay = kq.khong_thay + 1
        end
    end
    if #viec > 0 then
        local _, err = datSao(catalog, viec, false)
        if err then
            local co0 = false
            for _, v in ipairs(viec) do if v.sao == 0 then co0 = true end end
            if co0 then
                Core.log("cham sao: Lightroom khong nhan rating 0 -> thu nil: " .. tostring(err))
                _, err = datSao(catalog, viec, true)
            end
        end
        if err then
            kq.loi = #viec
            Core.log("LOI cham sao: " .. tostring(err))
        else
            kq.xong = #viec
        end
    end
    kq.khi = os.date("%Y-%m-%d %H:%M:%S")
    ghiKetQua(kq)
    Core.log(string.format("cham sao: %d anh (%d khong thay, %d loi)", kq.xong,
                           kq.khong_thay, kq.loi))
    return kq.xong
end

return M
