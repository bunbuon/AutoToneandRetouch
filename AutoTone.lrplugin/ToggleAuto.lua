--[[ Menu: bật/tắt chế độ tự động áp ngay khi autotone chạy xong. ]]

local LrTasks   = import "LrTasks"
local LrDialogs = import "LrDialogs"
local LrPrefs   = import "LrPrefs"

LrTasks.startAsyncTask(function()
    local prefs = LrPrefs.prefsForPlugin()
    prefs.autoApply = not prefs.autoApply
    if prefs.autoApply then
        LrDialogs.message("AutoTone",
            "ĐÃ BẬT tự động áp.\n\nTừ giờ mỗi khi autotone ghi xong, Lightroom tự " ..
            "cập nhật thông số trong vòng vài giây, không phải bấm gì nữa.", "info")
    else
        LrDialogs.message("AutoTone",
            "ĐÃ TẮT tự động áp.\n\nMuốn cập nhật thì vào\n" ..
            "Library > Plug-in Extras > AutoTone: áp thông số mới nhất.", "info")
    end
end)
