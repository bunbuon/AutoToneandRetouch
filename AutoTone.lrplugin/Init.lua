--[[ Chạy khi Lightroom nạp plugin: mở một tác vụ nền dò file job.

     Dò theo chu kỳ thay vì theo dõi hệ thống file vì SDK không có API theo dõi
     thư mục. 5 giây một lần chỉ là một lệnh liệt kê thư mục, không đáng kể.

     CHỐNG VÒNG LẶP CHỒNG VÒNG LẶP
     Init.lua chạy lại mỗi lần Lightroom nạp plugin — kể cả khi bấm Reload trong
     Plug-in Manager. Bản cũ mở vòng `while true` không có đường thoát, nên vòng
     của lần nạp trước vẫn sống tiếp: sau 3 lần reload là 3 vòng cùng dò một thư
     mục, cùng đọc một file job, cùng áp một loạt ảnh. Lightroom phải làm gấp ba
     việc và ba bên tranh nhau khoá ghi catalog — đúng lúc đó máy đứng hình.
     Nhìn plugin.log cũ là thấy: mỗi job in ra 2-3 dòng kết quả giống hệt nhau,
     có dòng còn theo định dạng của bản code cũ hơn.

     Cách chặn: mỗi lần nạp thì tăng một bộ đếm trong prefs (prefs sống chung
     cho cả tiến trình Lightroom, không phụ thuộc lần nạp nào). Vòng nào thấy bộ
     đếm đã khác số của mình thì tự thoát. Chỉ vòng mới nhất sống.

     Không dùng pcall quanh lời gọi SDK — xem đầu AutoToneCore.lua. ]]

local LrTasks     = import "LrTasks"
local LrPrefs     = import "LrPrefs"
local LrPathUtils = import "LrPathUtils"

--[[ Ghi log TỐI THIỂU, không phụ thuộc AutoToneCore.

     Trước đây Init.lua chỉ ghi được log SAU khi require thành công. Nên khi
     require chết, plugin im lặng tuyệt đối: không dòng log nào, không menu nào,
     và nhìn từ ngoài không phân biệt được "plugin chưa nạp" với "plugin nạp
     rồi nhưng vòng lặp không chạy". Đã mất một vòng chẩn đoán vì chuyện này.

     Nay Init.lua tự ghi được, nên lần chạy nào cũng để lại dấu vết. ]]
local function rawLog(msg)
    local dir = LrPathUtils.child(_PLUGIN.path, "jobs")
    local f = io.open(LrPathUtils.child(dir, "plugin.log"), "a")
    if f then
        f:write(os.date("%Y-%m-%d %H:%M:%S") .. "  [init] " .. tostring(msg) .. "\n")
        f:close()
    end
end

rawLog("Init.lua bat dau chay")

-- pcall ở đây AN TOÀN: nạp module không yield, khác hẳn các lời gọi SDK
-- (xem đầu AutoToneCore.lua về lý do cấm pcall quanh lời gọi catalog).
local okCore, Core = pcall(require, "AutoToneCore")
if not okCore then
    rawLog("KHONG NAP DUOC AutoToneCore -> " .. tostring(Core))
    return
end
for _, fn in ipairs({ "log", "try", "runPending", "runExportRequest", "recoverStale" }) do
    if type(Core[fn]) ~= "function" then
        rawLog("AutoToneCore THIEU ham: " .. fn .. " (ban cu con sot?)")
    end
end

--[[ DuyetCore nạp riêng, và KHÔNG được phép làm chết plugin nếu vắng.

     AutoToneCore.lua cố tình không require nó: đường ghi màu không được dính
     dáng gì tới đường dựng ảnh duyệt. Ở đây pcall là an toàn — nạp module
     không yield, khác hẳn lời gọi SDK (xem đầu AutoToneCore.lua). ]]
local okDuyet, Duyet = pcall(require, "DuyetCore")
if not okDuyet then
    rawLog("khong nap duoc DuyetCore -> " .. tostring(Duyet))
    Duyet = nil
elseif type(Duyet.runRequest) ~= "function" then
    rawLog("DuyetCore thieu ham runRequest (ban cu con sot?)")
    Duyet = nil
end

--[[ XuatCore nạp riêng, cùng lý do với DuyetCore: đường xuất ảnh giao khách
     không được phép làm chết vòng lặp nếu file vắng mặt (bản plugin cũ). ]]
local okXuat, Xuat = pcall(require, "XuatCore")
if not okXuat then
    rawLog("khong nap duoc XuatCore -> " .. tostring(Xuat))
    Xuat = nil
elseif type(Xuat.runRequest) ~= "function" then
    rawLog("XuatCore thieu ham runRequest (ban cu con sot?)")
    Xuat = nil
end

local POLL_SECONDS = 5

local prefs = LrPrefs.prefsForPlugin()
if prefs.autoApply == nil then prefs.autoApply = true end   -- mặc định bật

prefs.loopGen = (tonumber(prefs.loopGen) or 0) + 1
local myGen = prefs.loopGen

LrTasks.startAsyncTask(function()
    -- Tra lai job bi ket o ten .running khi Lightroom tat giua chung.
    -- Chi an toan o day, luc chua vong nao chay.
    if type(Core.recoverStale) == "function" then
        Core.try("recoverStale", Core.recoverStale)
    end
    Core.log("plugin da nap (vong #" .. tostring(myGen) ..
             "), tu dong ap = " .. tostring(prefs.autoApply))
    while true do
        -- Có lần nạp mới hơn -> nhường chỗ, thoát hẳn
        if (tonumber(prefs.loopGen) or myGen) ~= myGen then
            Core.log("vong #" .. tostring(myGen) .. " dung lai (da co vong moi hon)")
            return
        end
        if prefs.autoApply then
            local _, err = Core.try("autoApply", Core.runPending)
            if err then Core.log("LOI vong lap: " .. tostring(err)) end
        end

        --[[ Yêu cầu xuất thông số do app ghi ra (jobs/request_export.txt).
             Chạy BẤT KỂ autoApply bật hay tắt: đây là chiều đọc, không đụng
             gì vào ảnh, nên không có lý do gì để người dùng phải bật thêm. ]]
        if type(Core.runExportRequest) == "function" then
            local _, errX = Core.try("autoExport", Core.runExportRequest)
            if errX then Core.log("LOI yeu cau xuat: " .. tostring(errX)) end
        end

        --[[ Yêu cầu dựng ảnh duyệt (jobs/request_duyet.txt) và yêu cầu đánh
             dấu ảnh cần sửa (jobs/request_danhdau.tsv).

             CÓ CHỦ Ý ĐỂ Ở ĐÂY, KHÔNG Ở TRONG runPending: đây là việc RIÊNG,
             chạy sau khi màu đã ghi xong. Ngày 6/9 warmPreviews được gắn thẳng
             vào đường áp thông số; nó hỏng và kéo sập luôn việc ghi màu vốn
             đang chạy đúng. Đường ghi màu phải sạch — hỏng ở đây thì chỉ mất
             ảnh duyệt, không ai mất thông số.

             Duyet nạp riêng và có thể vắng mặt (bản plugin cũ), nên phải kiểm
             trước khi gọi thay vì để vòng lặp chết. ]]
        if Duyet then
            local _, errD = Core.try("autoDuyet", Duyet.runRequest)
            if errD then Core.log("LOI yeu cau duyet: " .. tostring(errD)) end
            local _, errM = Core.try("autoDanhDau", Duyet.runDanhDau)
            if errM then Core.log("LOI yeu cau danh dau: " .. tostring(errM)) end
        end

        --[[ Yêu cầu xuất ảnh giao khách (jobs/request_xuatanh.txt).

             Cũng để RIÊNG như hai cái trên, không nhét vào runPending. Đây là
             việc nặng nhất trong cả plugin — cả nghìn ảnh cỡ gốc — nên nếu nó
             hỏng thì tuyệt đối không được kéo theo đường ghi màu. ]]
        if Xuat then
            local _, errE = Core.try("autoXuatAnh", Xuat.runRequest)
            if errE then Core.log("LOI yeu cau xuat anh: " .. tostring(errE)) end
        end
        LrTasks.sleep(POLL_SECONDS)
    end
end)
