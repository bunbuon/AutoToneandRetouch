--[[ Menu: Library > Plug-in Extras > AutoTone: dựng ảnh duyệt nhanh

     Chạy tay, cho hai việc:
       1. CHẠY THỬ 50 ẢNH — đo tốc độ thật trước khi tin tính năng này. Bắt buộc
          làm một lần trên máy thật; không có số đo thì không biết nó nhanh hơn
          hay chậm hơn cách cuộn Library.
       2. Chạy cả vùng chọn khi không muốn qua app.

     Đường chính vẫn là app ghi jobs/request_duyet.txt rồi vòng lặp nền chạy —
     xem DuyetCore.runRequest.

     KHÔNG bọc pcall quanh lời gọi SDK — xem đầu AutoToneCore.lua. ]]

local LrApplication     = import "LrApplication"
local LrDialogs         = import "LrDialogs"
local LrFunctionContext = import "LrFunctionContext"
local LrPathUtils       = import "LrPathUtils"
local LrTasks           = import "LrTasks"

local Core  = require "AutoToneCore"
local Duyet = require "DuyetCore"

local THU = 50        -- số ảnh của lượt chạy thử (khớp duyet.GIOI_HAN_THU)

LrTasks.startAsyncTask(function()
    LrFunctionContext.callWithContext("AutoToneDuyet", function(context)
        context:addFailureHandler(function(_, message)
            Core.log("duyet (menu): LOI " .. tostring(message))
            LrDialogs.message("AutoTone: lỗi khi dựng ảnh duyệt",
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

        local chon = LrDialogs.confirm(
            "AutoTone: dựng ảnh duyệt nhanh",
            string.format(
                "Lightroom sẽ render %d ảnh JPEG cạnh %d px để soát màu, " ..
                "không đụng tới preview và không thêm ảnh nào vào catalog.\n\n" ..
                "Lần đầu nên chạy thử %d ảnh để đo tốc độ thật.",
                #photos, Duyet.CANH, THU),
            string.format("Chạy thử %d ảnh", THU),
            "Huỷ",
            "Chạy cả " .. #photos .. " ảnh")

        if chon == "cancel" then return end

        local danh = photos
        if chon == "ok" then                      -- nút chạy thử
            local nho = {}
            for i = 1, math.min(THU, #photos) do nho[i] = photos[i] end
            danh = nho
        end

        -- Thư mục đích: cạnh ảnh gốc, tên _duyet
        local goc = nil
        Core.try("duongDanAnhDau", function()
            goc = danh[1]:getRawMetadata("path")
            return true
        end)
        if not goc or goc == "" then
            LrDialogs.message("AutoTone",
                "Không đọc được đường dẫn của ảnh đầu tiên.", "critical")
            return
        end
        local dest = LrPathUtils.child(LrPathUtils.parent(goc), "_duyet")

        local progress = LrDialogs.showModalProgressDialog({
            title = "AutoTone: đang dựng ảnh duyệt",
            caption = string.format("%d ảnh", #danh),
            cannotCancel = true,     -- huỷ giữa chừng thì bảng ánh xạ dở dang
            functionContext = context,
        })

        local t0 = os.time()
        local res = Duyet.xuatDuyet(danh, dest, {}, function(xong, tong, coFile)
            progress:setPortionComplete(xong, tong)
            progress:setCaption(string.format("%d / %d ảnh · %d file đã ra",
                                              xong, tong, coFile))
        end)
        local giay = os.time() - t0

        local moiAnh = (#res.cap > 0) and (giay / #res.cap) or 0
        Core.log(string.format("duyet (menu): %d/%d anh, %d giay (%.2f s/anh) -> %s",
                               #res.cap, #danh, giay, moiAnh, dest))

        local msg = string.format(
            "Xong %d / %d ảnh trong %d giây (%.2f giây một ảnh).\n\n" ..
            "Ảnh duyệt nằm ở:\n%s\n\n" ..
            "Ước cho 1000 ảnh: khoảng %d phút.",
            #res.cap, #danh, giay, moiAnh, dest, math.floor(moiAnh * 1000 / 60 + 0.5))
        if res.loi > 0 then
            msg = msg .. string.format("\n\n%d ảnh KHÔNG ra file. Xem plugin.log.",
                                       res.loi)
        end
        LrDialogs.message("AutoTone: dựng ảnh duyệt", msg,
                          res.loi > 0 and "warning" or "info")
    end)
end)
