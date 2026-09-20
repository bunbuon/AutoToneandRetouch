--[[ Menu: Library > Plug-in Extras > AutoTone: chẩn đoán

     Thử đọc 1 ảnh bằng mọi cách và báo cáo chính xác cái nào chạy, cái nào lỗi.
     Dùng khi phần xuất không ra ảnh nào — thay vì đoán, lấy sự thật. ]]

local LrApplication = import "LrApplication"
local LrDialogs     = import "LrDialogs"
local LrFileUtils   = import "LrFileUtils"
local LrPathUtils   = import "LrPathUtils"
local LrTasks       = import "LrTasks"
local Core          = require "AutoToneCore"

local KEYS = { "Exposure2012", "Highlights2012", "Shadows2012",
               "Temperature", "Tint", "AsShotTemperature", "AsShotTint",
               "WhiteBalance", "ProcessVersion" }

local function line(out, s)
    out[#out + 1] = s
    Core.log("[chan doan] " .. s)
end

LrTasks.startAsyncTask(function()
    local out = {}
    local catalog = LrApplication.activeCatalog()

    line(out, "Lightroom " .. tostring(LrApplication.versionString and
                                       LrApplication.versionString() or "?"))
    line(out, "Thu muc job: " .. Core.jobDir())

    local photos = catalog:getMultipleSelectedOrAllPhotos()
    line(out, "So anh lay duoc: " .. tostring(photos and #photos or 0))
    if not photos or #photos == 0 then
        LrDialogs.message("AutoTone: chẩn đoán", table.concat(out, "\n"), "info")
        return
    end

    local photo = photos[1]

    -- Dung Core.try chu KHONG dung pcall: pcall la ham C, khong yield xuyen qua
    -- duoc, ma cac ham SDK nay deu yield ben trong.

    -- 1. duong dan
    local path, errPath = Core.try("path", function()
        return photo:getRawMetadata("path")
    end)
    line(out, "getRawMetadata('path'): " .. (path and tostring(path)
                                             or "LOI -> " .. tostring(errPath)))

    -- 2. doc truc tiep
    local s1, err1 = Core.try("direct", function()
        return photo:getDevelopSettings()
    end)
    line(out, "getDevelopSettings() truc tiep: " ..
              (type(s1) == "table" and "OK" or "LOI -> " .. tostring(err1)))

    -- 3. doc trong read-access
    local s2, err2 = Core.try("readAccess", function()
        local s
        catalog:withReadAccessDo(function() s = photo:getDevelopSettings() end)
        return s
    end)
    line(out, "getDevelopSettings() trong withReadAccessDo: " ..
              (type(s2) == "table" and "OK" or "LOI -> " .. tostring(err2)))

    -- 4. gia tri thuc te doc duoc
    local s = (type(s1) == "table" and s1) or (type(s2) == "table" and s2) or nil
    if s then
        local n = 0
        for _ in pairs(s) do n = n + 1 end
        line(out, "Bang settings co " .. n .. " khoa. Gia tri quan tam:")
        for _, k in ipairs(KEYS) do
            line(out, "   " .. k .. " = " .. tostring(s[k]))
        end
    else
        line(out, "KHONG doc duoc settings bang ca hai cach.")
    end

    -- 5. thu ghi file vao thu muc job
    local probe = LrPathUtils.child(Core.jobDir(), "probe.txt")
    local fh, werr = io.open(probe, "w")
    if fh then
        fh:write("ok\n"); fh:close()
        --[[ os.remove KHONG TON TAI trong Lua cua Lightroom.
             Sandbox cua Lightroom cat bot thu vien os: os.date va os.time thi
             co, nhung os.remove va os.rename thi khong. Goi vao la loi
             "attempt to call field 'remove' (a nil value)" — da gap that ngay
             31/8/2026, dung chinh o dong nay.
             Xoa file phai dung LrFileUtils.delete. ]]
        LrFileUtils.delete(probe)
        line(out, "Ghi file vao thu muc job: OK")
    else
        line(out, "Ghi file vao thu muc job: LOI -> " .. tostring(werr))
    end

    line(out, "")
    line(out, "Toan bo da ghi vao: " .. Core.logPath())
    LrDialogs.message("AutoTone: chẩn đoán", table.concat(out, "\n"), "info")
end)
