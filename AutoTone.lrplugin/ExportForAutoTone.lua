--[[ Menu: Library > Plug-in Extras > AutoTone: xuất thông số cho autotone

     Xuất thông số develop hiện tại của ảnh đang chọn (hoặc toàn bộ ảnh trong
     thư mục đang xem) ra file TSV để autotone đọc.

     Nhờ bước này KHÔNG cần bấm Ctrl+S (Save Metadata to File) nữa. Trên thư mục
     vài nghìn ảnh, Ctrl+S phải ghi từng ấy file .xmp ra đĩa, rất lâu và trông
     như Lightroom bị treo. Đọc thẳng từ catalog thì chỉ mất vài giây.

     LƯU Ý: tuyệt đối không bọc pcall quanh lời gọi SDK ở đây — xem đầu file
     AutoToneCore.lua. Cần bắt lỗi thì dùng Core.try(). ]]

local LrApplication     = import "LrApplication"
local LrDialogs         = import "LrDialogs"
local LrFileUtils       = import "LrFileUtils"
local LrFunctionContext = import "LrFunctionContext"
local LrPathUtils       = import "LrPathUtils"
local LrTasks           = import "LrTasks"
local Core              = require "AutoToneCore"

local FIELDS = { "Exposure2012", "Highlights2012", "Shadows2012",
                 "Temperature", "Tint", "AsShotTemperature", "AsShotTint" }

local CHUNK = 200

local function numOrEmpty(v)
    if type(v) == "number" then
        -- %.14g: giữ đủ chữ số mà không sinh đuôi .0 thừa
        return string.format("%.14g", v)
    elseif type(v) == "string" and tonumber(v) then
        return v
    end
    return ""
end

LrTasks.startAsyncTask(function()
    LrFunctionContext.callWithContext("AutoToneExport", function(context)
        context:addFailureHandler(function(_, message)
            Core.log("LOI khi xuat: " .. tostring(message))
            LrDialogs.message("AutoTone: lỗi khi xuất",
                tostring(message) .. "\n\nĐã ghi vào:\n" .. Core.logPath(), "critical")
        end)

        local catalog = LrApplication.activeCatalog()
        local photos = catalog:getMultipleSelectedOrAllPhotos()

        if not photos or #photos == 0 then
            LrDialogs.message("AutoTone",
                "Không có ảnh nào. Vào Library, mở thư mục buổi chụp rồi chạy lại.",
                "info")
            return
        end

        -- Thử một ảnh để biết có phải bọc read-access không. Dùng Core.try chứ
        -- không dùng pcall, vì getDevelopSettings yield bên trong.
        local direct = Core.try("probeDirect", function()
            return photos[1]:getDevelopSettings()
        end)
        local needReadAccess = type(direct) ~= "table"

        if needReadAccess then
            local viaRead, errRead = Core.try("probeRead", function()
                local s
                catalog:withReadAccessDo(function() s = photos[1]:getDevelopSettings() end)
                return s
            end)
            if type(viaRead) ~= "table" then
                Core.log("probe read-access that bai: " .. tostring(errRead))
                LrDialogs.message("AutoTone: không đọc được thông số",
                    "Lightroom từ chối trả về develop settings kể cả trong " ..
                    "read-access.\n\n" .. tostring(errRead) ..
                    "\n\nĐã ghi vào plugin.log. Gửi nội dung này để sửa.", "critical")
                return
            end
            Core.log("dung che do read-access")
        end

        local progress = LrDialogs.showModalProgressDialog({
            title = "AutoTone: đang đọc thông số",
            caption = string.format("%d ảnh", #photos),
            cannotCancel = false,
            functionContext = context,
        })

        local dir = Core.jobDir()
        if not LrFileUtils.exists(dir) then
            LrFileUtils.createAllDirectories(dir)
        end

        local lines = { "path\t" .. table.concat(FIELDS, "\t") }
        local noPath, noSettings = 0, 0

        -- Đếm riêng từng nguyên nhân: "bỏ qua" gộp chung thì không sửa được gì
        local function collectRange(from, to)
            for i = from, to do
                local photo = photos[i]
                local path = photo:getRawMetadata("path")
                if not path or path == "" then
                    noPath = noPath + 1
                else
                    local s = photo:getDevelopSettings()
                    if type(s) == "table" then
                        local row = { path }
                        for _, key in ipairs(FIELDS) do
                            row[#row + 1] = numOrEmpty(s[key])
                        end
                        lines[#lines + 1] = table.concat(row, "\t")
                    else
                        noSettings = noSettings + 1
                    end
                end
            end
        end

        --[[ Chia lô 200 ảnh: mỗi lô một khối read-access ngắn, giữa các lô thì yield
             để Lightroom còn vẽ được thanh tiến trình và nhận nút Cancel. Bọc cả
             vài nghìn ảnh trong một khối read-access sẽ làm treo giao diện thật. ]]
        local idx = 1
        while idx <= #photos do
            local last = math.min(idx + CHUNK - 1, #photos)
            if needReadAccess then
                catalog:withReadAccessDo(function() collectRange(idx, last) end)
            else
                collectRange(idx, last)
            end
            progress:setPortionComplete(last, #photos)
            progress:setCaption(string.format("%d / %d ảnh", last, #photos))
            LrTasks.yield()
            if progress:isCanceled() then break end
            idx = last + 1
        end

        if #lines == 1 then
            Core.log(string.format("khong xuat duoc anh nao: %d thieu path, %d thieu settings",
                                   noPath, noSettings))
            LrDialogs.message("AutoTone: không xuất được ảnh nào",
                string.format("%d ảnh không lấy được đường dẫn, %d ảnh không đọc " ..
                              "được thông số.\n\nĐã ghi vào:\n%s",
                              noPath, noSettings, Core.logPath()), "critical")
            return
        end

        -- ghi ra .part rồi đổi tên: autotone không bao giờ đọc phải file dở
        local stamp = os.date("%Y%m%d_%H%M%S")
        local dest = LrPathUtils.child(dir, "export_" .. stamp .. ".tsv")
        local tmp = dest .. ".part"

        local fh, err = io.open(tmp, "w")
        if not fh then
            LrDialogs.message("AutoTone: không ghi được file", tostring(err), "critical")
            return
        end
        fh:write(table.concat(lines, "\n") .. "\n")
        fh:close()
        Core.try("replaceExport", function()
            LrFileUtils.delete(dest)
            LrFileUtils.move(tmp, dest)
        end)

        -- chỉ giữ lại bản mới nhất cho đỡ rác
        Core.try("cleanupExports", function()
            for p in LrFileUtils.files(dir) do
                local name = LrPathUtils.leafName(p)
                if p ~= dest and string.sub(name, 1, 7) == "export_"
                   and string.sub(name, -4) == ".tsv" then
                    LrFileUtils.delete(p)
                end
            end
        end)

        Core.log(string.format("xuat %d anh -> %s", #lines - 1, dest))
        local msg = string.format("Đã xuất thông số của %d ảnh.\n\n" ..
                                  "Giờ mở autotone, chọn nguồn “Lightroom catalog” " ..
                                  "rồi bấm Phân tích.", #lines - 1)
        if noPath + noSettings > 0 then
            msg = msg .. string.format("\n\n(%d ảnh bỏ qua: %d thiếu đường dẫn, " ..
                                       "%d không đọc được thông số.)",
                                       noPath + noSettings, noPath, noSettings)
        end
        LrDialogs.message("AutoTone", msg, "info")
    end)
end)
