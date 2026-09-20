--[[ DUYỆT NHANH — dựng ảnh JPEG nhỏ để soát màu, KHÔNG qua preview Lightroom.

     ============================================================
     VÌ SAO CÓ FILE NÀY, VÀ VÌ SAO NÓ NẰM RIÊNG
     ============================================================

     Bài toán: sau khi plugin áp thông số mới, người dùng phải soát lại cả buổi
     xem tấm nào chưa ổn rồi sửa, XONG mới Export. Soát trong Lightroom thì phải
     chờ Lightroom dựng preview — Standard preview cho hơn nghìn ảnh mất rất lâu,
     Smart Preview còn lâu hơn, và bật Smart Preview lúc Import làm Import chậm gấp
     nhiều lần.

     SDK Lua của Lightroom KHÔNG có API nào cho preview: không dựng được, không
     đọc được, không xoá được cache. Đây là giới hạn của Adobe, không phải chỗ
     chưa tìm ra. Ngày 6/9 đã thử photo:requestJpegThumbnail() — callback không
     bao giờ nổ: 0/39 ảnh, 126 lô hết giờ, 950 ảnh bị bỏ, hai job kẹt ở .running.

     Nhưng SDK CÓ LrExportSession — chính là bộ render thật của Lightroom, có
     tài liệu, chạy được từ plugin mà không cần mở hộp thoại, và dùng GPU khi
     người dùng bật "Use Graphics Processor for Export". Nên thay vì xin
     Lightroom "dựng preview" (không có cửa), ta bảo nó XUẤT ẢNH THẬT ở kích
     thước nhỏ. Ảnh JPEG thường thì app tự mở, mở tức thì, không dính preview
     cache của Lightroom chút nào.

     ============================================================
     KHÔNG BAO GIỜ ĐƯỢC GỌI TỪ applyJob
     ============================================================

     File này để RIÊNG, không nhét vào AutoToneCore.lua, và AutoToneCore.lua
     không require nó. Lý do là bài học ngày 6/9: warmPreviews được gắn thẳng
     vào đường áp thông số, nên khi nó hỏng thì nó kéo theo cả việc ghi màu —
     thứ vốn đang chạy đúng. Đường ghi màu phải sạch tuyệt đối.

     Kiểm tự động canh chuyện này: kiem_duyet.lua.

     ============================================================
     TÊN KHOÁ EXPORT LẤY TỪ ĐÂU
     ============================================================

     KHÔNG đoán. Lấy nguyên từ preset export thật của Lightroom trên máy:
       %APPDATA%\Adobe\Lightroom\Export Presets\Lightroom Presets\
           For Email (Hard Drive).lrtemplate

     Trong .lrtemplate các khoá không có tiền tố; đưa vào exportSettings thì
     thêm "LR_". Đáng chú ý nhất: exportServiceProvider của "ghi ra ổ cứng" là
     "com.adobe.ag.export.file" — KHÔNG phải "com.adobe.ai.export.hardDrive"
     như đoán ban đầu. Sai khoá này thì export không ra file nào.

     KHÔNG DÙNG pcall — xem đầu AutoToneCore.lua. Dùng Core.try().
]]

local LrApplication   = import "LrApplication"
local LrExportSession = import "LrExportSession"
local LrFileUtils     = import "LrFileUtils"
local LrPathUtils     = import "LrPathUtils"
local LrTasks         = import "LrTasks"

local Core = require "AutoToneCore"

local M = {}

-- Cạnh dài tối đa của ảnh duyệt. 1600 đủ để thấy sai màu và sai sáng trên màn
-- 2.5K mà vẫn nhẹ; ảnh gốc 6000px thì đây là 1/14 số điểm ảnh.
M.CANH = 1600
M.CHAT = 0.7          -- chất lượng JPEG, thang 0..1 giống trong .lrtemplate

--[[ Số ảnh mỗi lô export.

     VÌ SAO CHIA LÔ chứ không đẩy cả nghìn ảnh vào một LrExportSession:
       1. doExportOnCurrentTask() chặn tới khi xong. Một session cho cả buổi =
          không có tiến trình nào để báo, người dùng ngồi nhìn màn hình đứng im
          — đúng cái bệnh đang muốn chữa.
       2. Chia lô thì ảnh lô đầu có mặt sau vài giây, app mở ra soát được NGAY
          trong lúc các lô sau còn đang render.
       3. Lô hỏng thì biết ngay lô nào, không mất cả buổi.
]]
M.LO = 25

M.TIEN_DO = "duyet_tiendo.txt"     -- plugin ghi, app đọc
M.YEU_CAU = "request_duyet.txt"    -- app ghi, plugin đọc
M.DANH_DAU = "request_danhdau.tsv" -- app ghi, plugin đọc
M.CO_DUNG = "request_duyet_dung.txt"   -- app ghi để xin dừng giữa chừng

--[[ XIN DỪNG GIỮA CHỪNG.

     Vì sao cần: thư mục 2000 ảnh mà lỡ bấm chạy cả buổi thì không có đường
     nào thoát — vòng lặp nền không có nút bấm, và tắt Lightroom giữa chừng là
     cách tệ nhất. Nay app chỉ cần đặt một file cờ; plugin kiểm GIỮA HAI LÔ.

     Kiểm giữa hai lô chứ không giữa chừng một lô: LrExportSession đã chạy thì
     phải để nó chạy hết lô đó, cắt ngang là để lại file dở trên đĩa. Lô 25 ảnh
     nên chậm nhất cũng chỉ chờ thêm một lô. ]]
function M.xinDung()
    return LrFileUtils.exists(LrPathUtils.child(Core.jobDir(), M.CO_DUNG))
end

function M.xoaCoDung()
    Core.try("xoaCoDung", function()
        LrFileUtils.delete(LrPathUtils.child(Core.jobDir(), M.CO_DUNG))
        return true
    end)
end

-- ---------------------------------------------------------------- tiến trình

--[[ Ghi trạng thái ra file cho app đọc. Ghi .part rồi đổi tên: app không bao
     giờ đọc phải file đang ghi dở (cùng quy ước với job áp). ]]
function M.ghiTienDo(bang)
    local dir = Core.jobDir()
    if not LrFileUtils.exists(dir) then
        LrFileUtils.createAllDirectories(dir)
    end
    local dest = LrPathUtils.child(dir, M.TIEN_DO)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return nil end
    for _, k in ipairs({ "trang_thai", "xong", "tong", "loi", "thu_muc", "tsv", "thong_bao" }) do
        if bang[k] ~= nil then
            fh:write(k .. "=" .. tostring(bang[k]) .. "\n")
        end
    end
    fh:close()
    Core.try("ghiTienDo", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)
    return dest
end

-- ------------------------------------------------------------ thông số export

--[[ Bảng exportSettings cho một lần xuất ảnh duyệt.

     Mọi khoá đều có mặt kể cả khoá "mặc định cũng đúng". Cố ý: bệnh kinh điển
     của LrExportSession là thiếu khoá kích thước thì Lightroom xuất ra ảnh 1
     điểm ảnh mà không báo lỗi gì. Liệt kê đủ thì không bao giờ rơi vào đó.
]]
function M.thongSo(dest, canh, chat)
    canh = tonumber(canh) or M.CANH
    chat = tonumber(chat) or M.CHAT
    return {
        LR_exportServiceProvider      = "com.adobe.ag.export.file",
        LR_exportServiceProviderTitle = "Hard Drive",

        LR_export_destinationType       = "specificFolder",
        LR_export_destinationPathPrefix = dest,
        LR_export_destinationPathSuffix = "",
        LR_export_useSubfolder          = false,
        --[[ "doNothing": tuyệt đối không mở Explorer sau mỗi lô. Preset mẫu của
             Adobe để "revealInFinder" — với 40 lô thì đó là 40 cửa sổ. ]]
        LR_export_postProcessing        = "doNothing",
        LR_export_colorSpace            = "sRGB",

        LR_format            = "JPEG",
        LR_jpeg_quality      = chat,
        LR_jpeg_useLimitSize = false,
        LR_jpeg_limitSize    = 100,
        LR_extensionCase     = "lowercase",

        --[[ Ghi đè, không hỏi. "ask" (mặc định của preset Adobe) sẽ dựng hộp
             thoại giữa chừng và treo cả vòng lặp nền — không ai bấm được. ]]
        LR_collisionHandling = "overwrite",

        --[[ tokens = {{image_name}} + extensionCase = lowercase
             => tên ra = <tên gốc không đuôi>.jpg, ĐOÁN TRƯỚC ĐƯỢC.
             Nhờ vậy app biết chắc ảnh nào ứng với ảnh nào mà không phải dò. ]]
        LR_renamingTokensOn     = false,
        LR_tokens               = "{{image_name}}",
        LR_tokenCustomString    = "",
        LR_initialSequenceNumber = 1,

        LR_size_doConstrain        = true,
        LR_size_doNotEnlarge       = true,
        LR_size_maxWidth           = canh,
        LR_size_maxHeight          = canh,
        LR_size_resizeType         = "wh",   -- lọt trong khung canh x canh
        LR_size_units              = "pixels",
        LR_size_resolution         = 72,
        LR_size_resolutionUnits    = "inch",
        LR_size_userWantsConstrain = true,

        -- Không làm nét đầu ra: đây là ảnh để soi màu, thêm nét chỉ tốn thời gian
        LR_outputSharpeningOn     = false,
        LR_outputSharpeningLevel  = 2,
        LR_outputSharpeningMedia  = "screen",

        LR_metadata_keywordOptions   = "flat",
        LR_minimizeEmbeddedMetadata  = true,
        LR_removeLocationMetadata    = false,

        LR_includeVideoFiles         = false,
        LR_useWatermark              = false,

        --[[ Đưa ảnh vừa xuất trở lại catalog thì mỗi lần duyệt lại thêm cả
             nghìn ảnh rác vào thư viện. Tuyệt đối không. ]]
        LR_reimportExportedPhoto        = false,
        LR_reimport_stackWithOriginal   = false,
    }
end

--[[ Tên file JPEG mà Lightroom sẽ tạo cho một ảnh gốc.

     Tính được vì đã ép LR_tokens="{{image_name}}" và extensionCase="lowercase".
     Vẫn có kiểm tra tồn tại ở nơi gọi, không tin suông. ]]
function M.tenRa(dest, srcPath)
    local base = LrPathUtils.removeExtension(LrPathUtils.leafName(srcPath))
    return LrPathUtils.child(dest, base .. ".jpg")
end

-- ------------------------------------------------------------------- xuất ảnh

--[[ Xuất một lô. Trả về mảng {src=, jpg=} của những ảnh ra được file.

     Đọc kết quả theo HAI đường, đường nào có thì lấy:
       1. session:renditions() -> rendition.destinationPath. Chuẩn nhất, do
          chính Lightroom trả về.
       2. Suy từ tên gốc (M.tenRa) rồi kiểm tồn tại trên đĩa.
     Có đường 2 vì renditions() sau khi export xong là chỗ tài liệu SDK không
     nói rõ; không muốn cả tính năng phụ thuộc vào một chỗ chưa chắc.
]]
local function xuatMotLo(photos, dest, thongSo)
    -- đường dẫn gốc phải lấy TRƯỚC khi export, lúc còn chắc chắn đọc được
    local goc = {}
    Core.try("docDuongDan", function()
        for i = 1, #photos do
            goc[i] = photos[i]:getRawMetadata("path")
        end
        return true
    end)

    local session = LrExportSession({
        photosToExport = photos,
        exportSettings = thongSo,
    })

    local _, errX = Core.try("doExport", function()
        session:doExportOnCurrentTask()
        return true
    end)
    if errX then
        Core.log("duyet: LOI export mot lo -> " .. tostring(errX))
    end

    -- đường 1: hỏi thẳng Lightroom
    local theoLR = {}
    Core.try("docRenditions", function()
        for _, r in session:renditions() do
            local p = r.destinationPath
            if p and p ~= "" then theoLR[#theoLR + 1] = p end
        end
        return true
    end)

    local cap = {}
    for i = 1, #photos do
        local src = goc[i]
        if src and src ~= "" then
            local jpg = M.tenRa(dest, src)
            if not LrFileUtils.exists(jpg) then
                --[[ Suy sai (tên gốc có ký tự Lightroom phải đổi chẳng hạn) thì
                     lùi về danh sách Lightroom trả về, khớp theo tên không đuôi. ]]
                local base = LrPathUtils.removeExtension(LrPathUtils.leafName(src))
                for _, p in ipairs(theoLR) do
                    if LrPathUtils.removeExtension(LrPathUtils.leafName(p)) == base then
                        jpg = p
                        break
                    end
                end
            end
            if LrFileUtils.exists(jpg) then
                cap[#cap + 1] = { src = src, jpg = jpg }
            end
        end
    end
    return cap
end

--[[ Xuất ảnh duyệt cho cả danh sách. tienDo(daXong, tong) gọi sau mỗi lô.

     Trả về bảng { cap = {{src,jpg}}, loi = <số ảnh không ra file>, tsv = <đường
     dẫn bảng ánh xạ> }. ]]
function M.xuatDuyet(photos, dest, opts, tienDo)
    opts = opts or {}
    local canh = tonumber(opts.canh) or M.CANH
    local chat = tonumber(opts.chat) or M.CHAT
    local lo   = tonumber(opts.lo) or M.LO
    if lo < 1 then lo = 1 end

    if not LrFileUtils.exists(dest) then
        LrFileUtils.createAllDirectories(dest)
    end
    local thongSo = M.thongSo(dest, canh, chat)

    local cap = {}
    local idx = 1
    while idx <= #photos do
        local last = math.min(idx + lo - 1, #photos)
        local nhom = {}
        for i = idx, last do nhom[#nhom + 1] = photos[i] end

        local phan = xuatMotLo(nhom, dest, thongSo)
        for _, c in ipairs(phan) do cap[#cap + 1] = c end

        --[[ Ghi bảng ánh xạ SAU MỖI LÔ chứ không đợi hết. Nhờ vậy app mở ra
             soát được ngay khi lô đầu xong, không phải chờ cả buổi. ]]
        M.ghiBang(cap, dest)
        if tienDo then tienDo(last, #photos, #cap) end
        M.ghiTienDo({ trang_thai = "dang_chay", xong = last, tong = #photos,
                      loi = last - #cap, thu_muc = dest })
        LrTasks.yield()
        idx = last + 1

        if M.xinDung() then
            M.xoaCoDung()
            Core.log(string.format("duyet: nguoi dung xin dung o anh %d/%d",
                                   last, #photos))
            local tsv_dung = M.ghiBang(cap, dest)
            --[[ da_dung = true, va 'loi' tinh trên SỐ ĐÃ LÀM chứ không trên
                 tổng: dừng giữa chừng thì mấy ảnh chưa tới lượt không phải
                 là lỗi. Đếm chúng vào lỗi là báo động giả. ]]
            return { cap = cap, loi = last - #cap, tsv = tsv_dung,
                     da_dung = true, da_lam = last }
        end
    end

    local tsv = M.ghiBang(cap, dest)
    return { cap = cap, loi = #photos - #cap, tsv = tsv, da_dung = false,
             da_lam = #photos }
end

--[[ Bảng ánh xạ ảnh gốc -> ảnh duyệt, để app biết mở file nào cho tấm nào. ]]
function M.ghiBang(cap, dest)
    local d = Core.jobDir()
    if not LrFileUtils.exists(d) then LrFileUtils.createAllDirectories(d) end
    local path = LrPathUtils.child(d, "duyet_anh.tsv")
    local tmp = path .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return nil end
    fh:write("path\tjpg\n")
    for _, c in ipairs(cap) do
        fh:write(tostring(c.src) .. "\t" .. tostring(c.jpg) .. "\n")
    end
    fh:close()
    Core.try("ghiBang", function()
        LrFileUtils.delete(path)
        LrFileUtils.move(tmp, path)
    end)
    return path
end

-- ------------------------------------------------------- lọc ảnh theo số sao

--[[ Bỏ ảnh đã bị loại (thường 1 sao). Cùng quy ước với writeExport và với
     burst_reject_rating của autotone: ảnh 1 sao không xuất, không retouch. ]]
function M.locSao(photos, boSao)
    boSao = tonumber(boSao)
    -- 0 nghĩa là KHÔNG lọc. Phải quy về nil: trong Lua số 0 vẫn là giá trị đúng,
    -- để nguyên thì mọi ảnh chưa gán sao đều khớp và bảng ra gần như rỗng.
    if not boSao or boSao == 0 then return photos, 0 end
    local out, bo = {}, 0
    local catalog = LrApplication.activeCatalog()
    local i = 1
    while i <= #photos do
        local last = math.min(i + 199, #photos)
        catalog:withReadAccessDo(function()
            for k = i, last do
                local r = photos[k]:getRawMetadata("rating")
                if tonumber(r) == boSao then bo = bo + 1
                else out[#out + 1] = photos[k] end
            end
        end)
        LrTasks.yield()
        i = last + 1
    end
    return out, bo
end

-- --------------------------------------------------- yêu cầu duyệt từ phía app

--[[ jobs/request_duyet.txt do app ghi:
         dòng 1  = thư mục ảnh gốc
         các dòng sau, dạng khoa=gia_tri:
             dest=<thư mục chứa ảnh duyệt>   (mặc định <goc>/_duyet)
             canh=1600  chat=70  lo=25  bo_sao=1  gioi_han=20

     gioi_han: chỉ xuất N ảnh đầu. Đây là đường CHẠY THỬ — đo tốc độ thật trên
     một nhúm ảnh trước khi cho chạy cả buổi. ]]
function M.runRequest()
    local req = LrPathUtils.child(Core.jobDir(), M.YEU_CAU)
    if not LrFileUtils.exists(req) then return 0 end

    local claimed = Core.claim(req)      -- cùng cơ chế giành với job áp
    if not claimed then return 0 end

    local folder, opts = nil, {}
    local fh = io.open(claimed, "r")
    if fh then
        folder = fh:read("*l")
        for line in fh:lines() do
            local k, v = string.match(line, "^%s*([%w_]+)%s*=%s*(.-)%s*$")
            if k then opts[k] = v end
        end
        fh:close()
    end
    Core.try("boYeuCauDuyet", function() LrFileUtils.delete(claimed) end)

    if not folder or folder == "" then
        Core.log("duyet: thieu duong dan thu muc")
        M.ghiTienDo({ trang_thai = "loi", thong_bao = "thieu duong dan" })
        return 0
    end
    folder = string.gsub(folder, "^%s*(.-)%s*$", "%1")

    local dest = opts.dest
    if not dest or dest == "" then
        dest = LrPathUtils.child(folder, "_duyet")
    end

    local catalog = LrApplication.activeCatalog()
    local photos, how = Core.photosInFolder(catalog, folder)
    if not photos or #photos == 0 then
        Core.log("duyet: khong thay anh nao trong " .. folder)
        M.ghiTienDo({ trang_thai = "loi", thong_bao = "khong thay anh nao" })
        return 0
    end

    local boSao
    local loc, boQua = M.locSao(photos, opts.bo_sao)
    photos, boSao = loc, boQua

    local gioi = tonumber(opts.gioi_han)
    if gioi and gioi > 0 and gioi < #photos then
        local nho = {}
        for i = 1, gioi do nho[i] = photos[i] end
        photos = nho
    end

    if #photos == 0 then
        M.ghiTienDo({ trang_thai = "loi", thong_bao = "loc xong khong con anh nao" })
        return 0
    end

    --[[ Xoá cờ dừng CŨ trước khi chạy. Còn sót cờ của lần trước thì lượt mới
         dừng ngay sau lô đầu mà không ai hiểu vì sao. ]]
    M.xoaCoDung()

    local t0 = os.time()
    M.ghiTienDo({ trang_thai = "dang_chay", xong = 0, tong = #photos, thu_muc = dest })

    local canh = tonumber(opts.canh)
    local chat = tonumber(opts.chat)
    if chat and chat > 1 then chat = chat / 100 end   -- app gửi 70, SDK cần 0.7

    local res, err = Core.try("xuatDuyet", function()
        return M.xuatDuyet(photos, dest, { canh = canh, chat = chat,
                                           lo = tonumber(opts.lo) })
    end)
    if not res then
        Core.log("duyet: LOI -> " .. tostring(err))
        M.ghiTienDo({ trang_thai = "loi", thong_bao = tostring(err) })
        return 0
    end

    local giay = os.time() - t0
    local moi_anh = (#res.cap > 0) and (giay / #res.cap) or 0
    M.ghiTienDo({ trang_thai = res.da_dung and "dung" or "xong",
                  xong = #res.cap, tong = res.da_lam or #photos,
                  loi = res.loi, thu_muc = dest, tsv = res.tsv,
                  thong_bao = string.format("%d giay, %.2f giay/anh",
                                            giay, moi_anh) })
    Core.log(string.format(
        "duyet: %s %d/%d anh (%s), bo %d anh %s sao, %d giay (%.2f s/anh) -> %s",
        res.da_dung and "DUNG GIUA CHUNG sau" or "xuat",
        #res.cap, #photos, how, boSao or 0, tostring(opts.bo_sao),
        giay, moi_anh, dest))
    return #res.cap
end

-- ------------------------------------------------------- đánh dấu ảnh cần sửa

--[[ Hàm tra ảnh theo đường dẫn.

     Cùng chiến thuật hai tầng với applyJob: findPhotoByPath trước (nhanh, không
     phải quét gì), trượt thì mới lập bảng tra chuẩn hoá cả catalog — cần vì
     đường dẫn Windows lệch hoa/thường hoặc lệch dấu gạch là findPhotoByPath
     trả về nil dù ảnh có thật.

     Bảng chỉ lập MỘT LẦN, và chỉ lập khi thực sự có ảnh trượt. ]]
function M.dungBangTra(catalog)
    local idx = nil
    local daLap = false
    return function(p)
        local photo = catalog:findPhotoByPath(p)
        if photo then return photo end
        if not daLap then
            daLap = true
            local built = Core.try("duyetBangTra", function()
                local t, n = Core.buildPathIndex(catalog)
                return (n and n > 0) and t or nil
            end)
            idx = built
        end
        if not idx then return nil end
        return idx[(string.gsub(string.lower(tostring(p)), "\\", "/"))]
    end
end

--[[ jobs/request_danhdau.tsv do app ghi sau khi người dùng soát xong:
         path<TAB>nhan<TAB>sao
     nhan: red / yellow / green / blue / purple / none. sao: số, để trống = không đụng.

     VÌ SAO CẦN: soát xong mà chỉ có một danh sách tên file thì vẫn phải ngồi
     dò từng tấm trong Lightroom. Gắn nhãn màu thì trong Library bấm lọc theo
     nhãn là ra đúng mấy tấm cần sửa, mở Develop sửa liền. ]]
function M.runDanhDau()
    local req = LrPathUtils.child(Core.jobDir(), M.DANH_DAU)
    if not LrFileUtils.exists(req) then return 0 end

    local claimed = Core.claim(req)
    if not claimed then return 0 end

    --[[ Đọc file. Dòng bắt đầu bằng # là tuỳ chọn dạng khoa=gia_tri; dòng
         không phải # đầu tiên là tiêu đề cột; còn lại là dữ liệu. ]]
    local rows, opts = {}, {}
    local fh = io.open(claimed, "r")
    if fh then
        local daQuaTieuDe = false
        for line in fh:lines() do
            if string.sub(line, 1, 1) == "#" then
                local k, v = string.match(line, "^#%s*([%w_]+)%s*=%s*(.-)%s*$")
                if k then opts[k] = v end
            elseif not daQuaTieuDe then
                daQuaTieuDe = true                   -- dòng tiêu đề cột
            elseif line ~= "" then
                local a, b, c = string.match(line, "^([^\t]*)\t?([^\t]*)\t?([^\t]*)$")
                if a and a ~= "" then
                    rows[#rows + 1] = { path = a, nhan = b, sao = tonumber(c) }
                end
            end
        end
        fh:close()
    end
    Core.try("boYeuCauDanhDau", function() LrFileUtils.delete(claimed) end)
    if #rows == 0 then return 0 end

    local catalog = LrApplication.activeCatalog()
    local lookup = M.dungBangTra(catalog)
    local xong, thieu = 0, 0
    local danhSach = {}          -- LrPhoto để bỏ vào bộ sưu tập

    local idx = 1
    while idx <= #rows do
        local last = math.min(idx + 99, #rows)
        local _, err = Core.try("danhDauLo", function()
            catalog:withWriteAccessDo("AutoTone: danh dau anh can sua", function()
                for i = idx, last do
                    local r = rows[i]
                    local photo = lookup(r.path)
                    if photo then
                        if r.nhan and r.nhan ~= "" and r.nhan ~= "none" then
                            photo:setRawMetadata("colorNameForLabel", r.nhan)
                        end
                        if r.sao then
                            photo:setRawMetadata("rating", r.sao)
                        end
                        danhSach[#danhSach + 1] = photo
                        xong = xong + 1
                    else
                        thieu = thieu + 1
                    end
                end
            end, { timeout = 30 })
            return true
        end)
        if err then Core.log("danh dau: LOI lo " .. idx .. " -> " .. tostring(err)) end
        LrTasks.yield()
        idx = last + 1
    end

    --[[ ============================================================
         BỘ SƯU TẬP — đây mới là đường tìm lại ảnh, không phải nhãn màu.

         Nhãn màu lọc được (Library Filter Bar > Attribute), nhưng nó có ba
         chỗ dở: thanh lọc hay bị ẩn hoặc đang ở "Filters Off" nên nhìn như
         không có; nhãn đè lên hệ thống nhãn riêng của người dùng; và lọc
         xong vẫn phải nhớ tắt lọc đi.

         Bộ sưu tập thì nằm sẵn ở cột trái, bấm một cái là ra đúng danh sách,
         không đụng gì tới nhãn hay sao của ảnh, và tự mất đi khi xoá.

         createCollection(ten, cha, canReturnPrior) — canReturnPrior = true
         nên chạy lại lần hai KHÔNG lỗi mà trả về đúng bộ cũ. removeAllPhotos()
         trước khi thêm: bộ sưu tập luôn phản ánh LẦN SOÁT MỚI NHẤT, không
         cộng dồn các lần trước lại với nhau.
         ============================================================ ]]
    local ten_bst = opts.bo_suu_tap
    local vao_bst = 0
    if ten_bst and ten_bst ~= "" and #danhSach > 0 then
        local _, errB = Core.try("boSuuTap", function()
            catalog:withWriteAccessDo("AutoTone: bo suu tap anh can sua", function()
                local bst = catalog:createCollection(ten_bst, nil, true)
                if bst then
                    bst:removeAllPhotos()
                    bst:addPhotos(danhSach)
                    vao_bst = #danhSach
                end
            end, { timeout = 60 })
            return true
        end)
        if errB then
            --[[ Bộ sưu tập hỏng thì KHÔNG được kéo theo phần nhãn đã ghi
                 xong ở trên. Ghi log rồi đi tiếp. ]]
            Core.log("danh dau: khong tao duoc bo suu tap -> " .. tostring(errB))
        end
    end

    Core.log(string.format(
        "danh dau: %d anh, %d khong co trong catalog%s",
        xong, thieu,
        vao_bst > 0 and string.format(", %d anh vao bo suu tap \"%s\"",
                                      vao_bst, tostring(ten_bst)) or ""))
    return xong
end

return M
