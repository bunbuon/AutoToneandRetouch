--[[ Menu: Library > Plug-in Extras > AutoTone: áp thông số mới nhất

     Không dùng pcall quanh lời gọi SDK — xem đầu AutoToneCore.lua. ]]

local LrTasks    = import "LrTasks"
local LrDialogs  = import "LrDialogs"
local LrDate     = import "LrDate"
local Core       = require "AutoToneCore"

LrTasks.startAsyncTask(function()
    local res, err = Core.try("applyNow", function()
        local nJobs, applied, missing, _skipped, _unver, previewed =
            Core.runPending()
        return { jobs = nJobs, applied = applied, missing = missing,
                 previewed = previewed }
    end)

    if not res then
        Core.log("ApplyNow that bai: " .. tostring(err))
        LrDialogs.message("AutoTone: lỗi",
            tostring(err) .. "\n\nĐã ghi vào:\n" .. Core.logPath(), "critical")
        return
    end

    if res.jobs == 0 then
        --[[ HÀNG ĐỢI RỖNG THƯỜNG LÀ TIN TỐT, KHÔNG PHẢI TIN XẤU.

             "Tự động áp" mặc định bật, nên plugin nuốt job trong vài giây kể từ
             lúc autotone ghi ra. Người dùng bấm Ghi rồi sang đây bấm tay thì
             hàng đợi rỗng THẬT — vì việc đã xong từ lúc nào rồi.

             Bản cũ nói "Chạy autotone (bấm 2 · Ghi) rồi quay lại đây", tức chỉ
             người ta đi làm lại đúng việc vừa xong. Ngày 4/9 người dùng bấm Ghi
             ba lần liên tiếp vì tưởng hỏng; nhật ký ghi lần đầu "ap 1031, 0 loi,
             kiem chung DU", hai lần sau "ap 0, bo qua 1031 (da dung san)".

             Nên: nhìn file .done gần nhất để tách hai trường hợp mà bản cũ gộp
             làm một — "vừa áp xong rồi" và "job đang rơi vào một thư mục khác". ]]
        local ten, khi = Core.lastDone()
        if ten then
            local gio = khi and LrDate.timeToUserFormat(khi, "%H:%M ngày %d/%m")
                            or "gần đây"
            LrDialogs.message("AutoTone",
                "Không còn gì đang chờ — thông số đã áp xong rồi.\n\n" ..
                "Lần áp gần nhất: " .. gio .. "\n(" .. ten .. ")\n\n" ..
                "“Tự động áp” đang bật, nên plugin nhận job ngay khi autotone " ..
                "ghi ra — anh không cần vào đây bấm tay.\n\n" ..
                "Số ảnh đã áp nằm ở dòng cuối file:\n" .. Core.logPath(), "info")
        else
            LrDialogs.message("AutoTone",
                "Không có thông số nào đang chờ, và thư mục job này cũng chưa " ..
                "từng có lần áp nào.\n\n" ..
                "Bên autotone bấm “3 · Đẩy vào Lightroom” rồi quay lại đây.\n\n" ..
                "Nếu vừa bấm rồi mà vẫn ra thông báo này thì app đang ghi job " ..
                "vào MỘT THƯ MỤC KHÁC. Thư mục plugin đang đọc là:\n" ..
                Core.jobDir(), "info")
        end
    else
        local msg = string.format("Đã áp thông số cho %d ảnh.", res.applied)
        if res.missing > 0 then
            msg = msg .. string.format("\n%d ảnh không tìm thấy trong catalog " ..
                                       "(chưa import, hoặc đã chuyển chỗ).", res.missing)
        end
        LrDialogs.message("AutoTone", msg, "info")
    end
end)
