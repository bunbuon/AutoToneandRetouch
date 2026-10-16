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
local LrFileUtils = import "LrFileUtils"

--[[ Ghi log TỐI THIỂU, không phụ thuộc AutoToneCore.

     Trước đây Init.lua chỉ ghi được log SAU khi require thành công. Nên khi
     require chết, plugin im lặng tuyệt đối: không dòng log nào, không menu nào,
     và nhìn từ ngoài không phân biệt được "plugin chưa nạp" với "plugin nạp
     rồi nhưng vòng lặp không chạy". Đã mất một vòng chẩn đoán vì chuyện này.

     Nay Init.lua tự ghi được, nên lần chạy nào cũng để lại dấu vết. ]]
local okTMJ, TMJ = pcall(require, "ThuMucJob")      -- 9/10: jobs_dir.txt (bản trong Modules)
local function rawLog(msg)
    local dir = (okTMJ and type(TMJ) == "table" and TMJ.jobDir and TMJ.jobDir())
                or LrPathUtils.child(_PLUGIN.path, "jobs")
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

--[[ ChupCore: chụp nguyên trạng thông số develop của một thư mục (CHỈ ĐỌC).
     Nạp riêng, cùng lý do với hai module trên. ]]
local okChup, Chup = pcall(require, "ChupCore")
if not okChup then
    rawLog("khong nap duoc ChupCore -> " .. tostring(Chup))
    Chup = nil
elseif type(Chup.runRequest) ~= "function" then
    rawLog("ChupCore thieu ham runRequest (ban cu con sot?)")
    Chup = nil
end

--[[ XemPresetCore (9/10): danh sách preset Lightroom + render cả lưới theo
     preset (áp TẠM -> render -> trả lại). Nạp riêng, cùng lý do ba module trên. ]]
local okXP, XemPreset = pcall(require, "XemPresetCore")
if not okXP then
    rawLog("khong nap duoc XemPresetCore -> " .. tostring(XemPreset))
    XemPreset = nil
elseif type(XemPreset.runRequest) ~= "function" then
    rawLog("XemPresetCore thieu ham runRequest (ban cu con sot?)")
    XemPreset = nil
end

--[[ DanhSachCore (13/10): danh sách ảnh của buổi trong catalog -> lưới của app
     chỉ hiện ảnh Lightroom đang có. Nạp riêng, cùng lý do các module trên. ]]
local okDS, DanhSach = pcall(require, "DanhSachCore")
if not okDS then
    rawLog("khong nap duoc DanhSachCore -> " .. tostring(DanhSach))
    DanhSach = nil
elseif type(DanhSach.runTheoDoi) ~= "function" then
    DanhSach = nil
end

--[[ SaoCore (14/10): app chấm sao 0–5 (jobs/request_sao.txt) -> rating trong
     Lightroom. Nạp riêng, cùng lý do các module trên. ]]
local okSao, Sao = pcall(require, "SaoCore")
if not okSao then
    rawLog("khong nap duoc SaoCore -> " .. tostring(Sao))
    Sao = nil
elseif type(Sao.runRequest) ~= "function" then
    Sao = nil
end

--[[ DenoiseCore (13/10): bật Denoise của Lightroom cho ảnh ISO cao — yêu cầu
     RIÊNG app gửi sau khi job áp xong. Nạp riêng, cùng lý do các module trên. ]]
local okDN, Denoise = pcall(require, "DenoiseCore")
if not okDN then
    rawLog("khong nap duoc DenoiseCore -> " .. tostring(Denoise))
    Denoise = nil
elseif type(Denoise.runRequest) ~= "function" then
    Denoise = nil
end

--[[ HocMauCore (14/10): học màu Lightroom trên ảnh RAW thật — áp TẠM biến thể ->
     dựng -> trả lại (như XemPresetCore). Nạp riêng, cùng lý do các module trên. ]]
local okHM, HocMau = pcall(require, "HocMauCore")
if not okHM then
    rawLog("khong nap duoc HocMauCore -> " .. tostring(HocMau))
    HocMau = nil
elseif type(HocMau.runRequest) ~= "function" then
    HocMau = nil
end

--[[ AutoCore (16/10): bấm Auto (bảng Basic) cho các ảnh — "Quy trình Auto Lightroom (thử
     nghiệm)". Yêu cầu RIÊNG app gửi trước khi tính / áp. Nạp riêng, cùng lý do các module trên. ]]
local okAU, AutoLr = pcall(require, "AutoCore")
if not okAU then
    rawLog("khong nap duoc AutoCore -> " .. tostring(AutoLr))
    AutoLr = nil
elseif type(AutoLr.runRequest) ~= "function" then
    AutoLr = nil
end

--[[ 2 giây (trước 5): mỗi vòng chỉ là vài lệnh kiểm file có tồn tại không. App
     nhờ xuất thì người dùng đang ngồi chờ — 5 giây là quá nửa thời gian chờ. ]]
local POLL_SECONDS = 2

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
    --[[ Lan truoc Lightroom tat / may sap giua mot lo "xem preset" (anh dang
         mang preset TAM) -> tra lai thong so goc theo so khoi phuc, TRUOC moi
         viec khac. ]]
    if XemPreset and type(XemPreset.khoiPhuc) == "function" then
        local _, errK = Core.try("xemPresetKhoiPhuc", XemPreset.khoiPhuc)
        if errK then Core.log("LOI khoi phuc xem preset: " .. tostring(errK)) end
    end
    --  14/10: cùng lý do — lượt học màu dở (ảnh đang mang biến thể TẠM)
    if HocMau and type(HocMau.khoiPhuc) == "function" then
        local _, errH = Core.try("hocMauKhoiPhuc", HocMau.khoiPhuc)
        if errH then Core.log("LOI khoi phuc hoc mau: " .. tostring(errH)) end
    end
    Core.log("plugin da nap (vong #" .. tostring(myGen) ..
             "), tu dong ap = " .. tostring(prefs.autoApply))
    while true do
        -- Có lần nạp mới hơn -> nhường chỗ, thoát hẳn
        if (tonumber(prefs.loopGen) or myGen) ~= myGen then
            Core.log("vong #" .. tostring(myGen) .. " dung lai (da co vong moi hon)")
            return
        end
        -- Nhịp cho app biết vòng lặp còn sống (xem Core.ghiNhip). Bản Core cũ
        -- chưa có hàm này thì bỏ qua, đừng làm chết vòng lặp.
        if type(Core.ghiNhip) == "function" then
            Core.try("nhip", function() return Core.ghiNhip(myGen) end)
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
            --[[ 13/10: luot 2 cua "Xu ly anh" (curve da / nen chay) — dung anh da ap
                 thong so cho app do. Chieu DOC (khong doi anh) nen chay bat ke autoApply;
                 viec GHI curve van di job ap thuong (runPending). ]]
            if type(Duyet.runRequestCurve) == "function" then
                local _, errCv = Core.try("autoDoCurve", Duyet.runRequestCurve)
                if errCv then Core.log("LOI yeu cau do curve: " .. tostring(errCv)) end
            end
            --  14/10: preview Lightroom cho lưới của tool sau khi áp (chỉ đọc)
            if type(Duyet.runRequestXem) == "function" then
                local _, errXm = Core.try("autoXemLr", Duyet.runRequestXem)
                if errXm then Core.log("LOI yeu cau xem preview: " .. tostring(errXm)) end
            end
            --  14/10: preview TRƯỚC khi áp cho chuỗi màu da một lượt (chỉ đọc)
            if type(Duyet.runRequestTruoc) == "function" then
                local _, errTr = Core.try("autoDoTruoc", Duyet.runRequestTruoc)
                if errTr then Core.log("LOI yeu cau preview truoc: " .. tostring(errTr)) end
            end
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

        --[[ Yêu cầu chụp nguyên trạng (jobs/request_chup.txt). Chiều ĐỌC như
             yêu cầu xuất, nên chạy bất kể autoApply. ]]
        if Chup then
            local _, errC = Core.try("autoChup", Chup.runRequest)
            if errC then Core.log("LOI yeu cau chup: " .. tostring(errC)) end
        end
        --[[ Xem truoc preset Lightroom (jobs/request_xempreset.txt) + danh
             sach preset. Moi lan goi chi lam toi ~15 giay roi tra ve — viec
             khac van duoc phuc vu xen giua cac lo. ]]
        if XemPreset then
            local _, errP = Core.try("autoXemPreset", XemPreset.runRequest)
            if errP then Core.log("LOI xem preset: " .. tostring(errP)) end
        end
        --[[ 13/10: danh sách ảnh của buổi trong catalog (~4 giây một lần, chỉ ghi
             khi đổi). Chiều ĐỌC, chạy bất kể autoApply. ]]
        if DanhSach then
            local _, errDS = Core.try("autoDanhSach", DanhSach.runTheoDoi)
            if errDS then Core.log("LOI danh sach catalog: " .. tostring(errDS)) end
            --  13/10: cây thư mục của catalog -> cột Thư mục của app (~2 phút, hoặc ngay khi app xin)
            if type(DanhSach.runThuMuc) == "function" then
                local _, errTM = Core.try("autoThuMuc", DanhSach.runThuMuc)
                if errTM then Core.log("LOI cay thu muc: " .. tostring(errTM)) end
            end
        end
        --[[ 13/10: Denoise ảnh ISO cao (jobs/request_denoise.txt). ĐỔI việc ảnh
             (thay module / vùng chọn của người dùng) nên chỉ chạy khi autoApply
             bật — tắt tự áp là người dùng không muốn plugin đụng vào ảnh. ]]
        --[[ 14/10: chấm sao từ app (jobs/request_sao.txt). Người dùng BẤM chấm từng
             lần, không phải việc tự động -> chạy bất kể autoApply. Đặt TRƯỚC
             Denoise: Denoise một lượt dài, sao thì người dùng đang nhìn chờ. ]]
        if Sao then
            local _, errS = Core.try("autoSao", Sao.runRequest)
            if errS then Core.log("LOI cham sao: " .. tostring(errS)) end
        end
        --[[ 14/10: học màu Lightroom (jobs/request_hocmau.txt). Người dùng BẤM chạy
             (HOC_MAU_LR) -> chạy bất kể autoApply; mỗi lượt ~20 giây rồi trả ảnh lại. ]]
        if HocMau then
            local _, errHM = Core.try("autoHocMau", HocMau.runRequest)
            if errHM then Core.log("LOI hoc mau: " .. tostring(errHM)) end
        end
        --  16/10: Auto (bảng Basic) — ĐỔI ảnh nên như Denoise chỉ chạy khi autoApply bật
        if AutoLr and prefs.autoApply then
            local _, errAU = Core.try("autoAutoLr", AutoLr.runRequest)
            if errAU then Core.log("LOI auto: " .. tostring(errAU)) end
        end
        if Denoise and prefs.autoApply then
            local _, errDN = Core.try("autoDenoise", Denoise.runRequest)
            if errDN then Core.log("LOI denoise: " .. tostring(errDN)) end
        end
        --[[ 10/10: ngủ từng nhịp 0,2 s, thức NGAY khi app xin xem preset (người
             dùng vừa bấm chọn preset / mở ảnh — đang ngồi chờ màu đổi); đang dở
             một lượt xem preset thì gần như không nghỉ. ]]
        if (XemPreset and XemPreset.dang) or (HocMau and HocMau.dang) then
            LrTasks.sleep(0.1)
        else
            local da = 0
            while da < POLL_SECONDS do
                LrTasks.sleep(0.2)
                da = da + 0.2
                if XemPreset and LrFileUtils.exists(LrPathUtils.child(Core.jobDir(),
                        XemPreset.YEU_CAU)) then
                    break
                end
                --  14/10: app vừa chấm sao -> làm ngay, đừng để người dùng chờ 2 giây
                if Sao and LrFileUtils.exists(LrPathUtils.child(Core.jobDir(),
                        Sao.YEU_CAU)) then
                    break
                end
            end
        end
    end
end)
