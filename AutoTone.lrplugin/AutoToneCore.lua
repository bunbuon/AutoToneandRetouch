--[[ Phần dùng chung: đọc job và áp vào catalog.

     KHÔNG DÙNG pcall Ở ĐÂY. Lua của Lightroom là 5.1, pcall là hàm C và không
     yield xuyên qua được. Hầu hết hàm SDK đụng tới catalog (getDevelopSettings,
     applyDevelopSettings...) đều yield bên trong, nên bọc pcall quanh chúng sẽ
     lỗi ngay: "Yielding is not allowed within a C or metamethod call".

     Muốn bắt lỗi thì dùng M.try() bên dưới — dựa trên LrFunctionContext, an toàn
     với yield. ]]

local LrApplication     = import "LrApplication"
local LrFileUtils       = import "LrFileUtils"
local LrFunctionContext = import "LrFunctionContext"
local LrPathUtils       = import "LrPathUtils"
local LrTasks           = import "LrTasks"   -- yield giua cac lo, xem applyJob

local M = {}

--[[ Thư mục job = <thư mục plugin>/jobs

     Cố tình KHÔNG dùng getStandardFilePath("appData"): tên thư mục chuẩn của
     Lightroom có thể trỏ %APPDATA% trong khi Python hiểu là %LOCALAPPDATA%, lệch
     một cái là plugin không bao giờ thấy job. Lấy theo thư mục plugin thì hai bên
     luôn chỉ về đúng một chỗ, dù cài plugin ở đâu. ]]
function M.jobDir()
    return LrPathUtils.child(_PLUGIN.path, "jobs")
end

function M.logPath()
    return LrPathUtils.child(M.jobDir(), "plugin.log")
end

function M.log(msg)
    local dir = M.jobDir()
    if not LrFileUtils.exists(dir) then
        LrFileUtils.createAllDirectories(dir)
    end
    local f = io.open(M.logPath(), "a")
    if f then
        f:write(os.date("%Y-%m-%d %H:%M:%S") .. "  " .. tostring(msg) .. "\n")
        f:close()
    end
end

--[[ Thay thế cho pcall, an toàn với yield.
     Trả về (kết quả, nil) nếu chạy được, hoặc (nil, thông báo lỗi).

     Ưu tiên pcallWithContext — đúng là bản pcall dành cho code có yield. Bản
     Lightroom nào không có thì lùi về callWithContext + addFailureHandler. ]]
local hasPcallWithContext = type(LrFunctionContext.pcallWithContext) == "function"

function M.try(name, fn)
    local tag = "AutoTone." .. name
    if hasPcallWithContext then
        local ok, res = LrFunctionContext.pcallWithContext(tag, function() return fn() end)
        if ok then return res, nil end
        return nil, tostring(res)
    end

    local result, errMsg
    LrFunctionContext.callWithContext(tag, function(ctx)
        ctx:addFailureHandler(function(_, message) errMsg = tostring(message) end)
        result = fn()
    end)
    return result, errMsg
end

-- Tách một dòng TSV thành mảng, giữ nguyên ô rỗng
local function splitTab(line)
    local out, pos = {}, 1
    while true do
        local s, e = string.find(line, "\t", pos, true)
        if not s then
            out[#out + 1] = string.sub(line, pos)
            break
        end
        out[#out + 1] = string.sub(line, pos, s - 1)
        pos = e + 1
    end
    return out
end

--[[ Đọc file job.
     Dòng đầu là tiêu đề: path, Exposure2012, Highlights2012, Shadows2012,
     Temperature, Tint. Ô để trống nghĩa là "đừng đụng trường này". ]]
function M.readJob(path)
    local rows = {}
    local fh = io.open(path, "r")
    if not fh then return rows, "khong mo duoc file" end

    local header = fh:read("*l")
    if not header then fh:close(); return rows, "file rong" end
    local cols = splitTab(header)

    for line in fh:lines() do
        if line ~= "" then
            local v = splitTab(line)
            local rec = { path = v[1], settings = {} }
            for i = 2, #cols do
                local key, val = cols[i], v[i]
                if val ~= nil and val ~= "" then
                    if key == "Rating" then
                        -- Rating di duong rieng, khong phai develop setting
                        rec.rating = tonumber(val)
                    else
                        rec.settings[key] = tonumber(val)
                    end
                end
            end
            if rec.path and rec.path ~= "" then rows[#rows + 1] = rec end
        end
    end
    fh:close()
    return rows
end

--[[ So sánh giá trị muốn ghi với giá trị đang có trong catalog.

     VÌ SAO CẦN: autotone ghi giá trị TUYỆT ĐỐI nên job luôn liệt kê ĐỦ cả thư
     mục, kể cả ảnh không đổi gì (xem write_lr_job trong autotone.py). Trước đây
     plugin gọi applyDevelopSettings cho từng dòng, không cần biết có khác hay
     không. Mỗi lần gọi là Lightroom: thêm một bước history, huỷ preview cũ, dựng
     lại preview, và nếu Catalog Settings bật "Automatically write changes into
     XMP" thì ghi thêm một file .xmp ra đĩa. Chạy lại job cho 1455 ảnh mà chỉ
     vài chục ảnh đổi thì vẫn phải trả giá cho cả 1455 — đó là lúc Lightroom
     đứng hình.

     Nay so trước, khác mới ghi. Job chạy lần hai gần như không tốn gì. ]]
local EPS = 1e-4

local function sameNumber(a, b)
    if type(a) ~= "number" or type(b) ~= "number" then return false end
    local d = a - b
    if d < 0 then d = -d end
    return d < EPS
end

-- Trả về danh sách trường còn lệch (rỗng = ảnh đã đúng)
local function diffFields(cur, want)
    local bad = {}
    for key, val in pairs(want) do
        if not sameNumber(cur[key], val) then bad[#bad + 1] = key end
    end
    if (want.Temperature or want.Tint) and cur.WhiteBalance ~= "Custom" then
        bad[#bad + 1] = "WhiteBalance"
    end
    return bad
end

--[[ CHÌA KHOÁ ĐỂ KHÔNG SÓT ẢNH: bảng tra đường dẫn -> ảnh.

     catalog:findPhotoByPath() so chuỗi khá cứng. Đường dẫn trong job do Python
     quét từ hệ thống file (F:\Buoi chup\SAY-00001.ARW), còn Lightroom lưu đường
     dẫn của riêng nó — khác hoa/thường hoặc khác dấu gạch là trượt, và ảnh đó
     lặng lẽ bị bỏ qua. Trong plugin.log cũ chính là mấy dòng "9 khong co trong
     catalog", "14 khong co trong catalog".

     Nên: ảnh nào findPhotoByPath trượt thì dò lại bằng bảng tra chuẩn hoá
     (chữ thường + gạch chéo thuận). Bảng chỉ dựng khi THẬT SỰ có ảnh trượt, nên
     job khớp sạch không tốn thêm gì.

     Bản sao ảo (virtual copy) dùng chung đường dẫn với bản gốc nên không thể
     phân biệt bằng path. Bảng chỉ giữ bản gốc; số bản sao ảo được đếm riêng để
     báo cho người dùng biết chúng KHÔNG được áp. ]]
local INDEX_MAX = 300000
local INDEX_TTL = 120       -- giay: giu lai bang tra cho cac job di theo cum

local function normKey(p)
    return (string.gsub(string.lower(tostring(p)), "\\", "/"))
end

--[[ Bảng tra dựng lại thì phải duyệt cả catalog, catalog vài chục nghìn ảnh là
     mất mấy chục giây. autotone thường bắn liên tiếp mấy job cho cùng một buổi
     chụp, nên giữ bảng lại 2 phút thay vì dựng lại từng lần. Bảng cũ chỉ dùng
     cho những ảnh findPhotoByPath ĐÃ trượt, và ảnh đã bị xoá khỏi catalog thì
     lời gọi SDK sẽ lỗi và bị M.try bắt — nên rủi ro của bản hơi cũ là chấp nhận
     được, còn cái giá của việc dựng lại thì không. ]]
local indexCache = nil

function M.buildPathIndex(catalog)
    local idx, n, vcopies = {}, 0, 0
    local all = catalog:getAllPhotos()
    if not all then return idx, 0, 0 end
    if #all > INDEX_MAX then
        M.log(string.format("khong lap chi muc: catalog co %d anh, vuot muc %d",
                            #all, INDEX_MAX))
        return idx, 0, 0
    end
    for i = 1, #all do
        local photo = all[i]
        local p = photo:getRawMetadata("path")
        if p and p ~= "" then
            local k = normKey(p)
            if photo:getRawMetadata("isVirtualCopy") then
                if idx[k] ~= nil then vcopies = vcopies + 1 end
            elseif idx[k] == nil then
                idx[k] = photo
                n = n + 1
            end
        end
        -- Nhuong luot dinh ky, khong thi giao dien Lightroom dung hinh khi lap
        if i % 2000 == 0 then LrTasks.yield() end
    end
    return idx, n, vcopies
end

--[[ Áp một job vào catalog. Ba lượt:

       1. DÒ + SO   (chỉ đọc)  — tìm ảnh, đọc settings, quyết định ảnh nào cần ghi
       2. GHI       (chia lô)  — chỉ ghi những ảnh thật sự lệch
       3. KIỂM CHỨNG (chỉ đọc) — đọc lại và đối chiếu, ảnh nào chưa nhận thì ghi
                                 tên ra file verify_*.tsv

     Vì sao tách lượt 1 ra khỏi giao dịch ghi: getDevelopSettings chỉ cần quyền
     đọc. Để nó bên trong withWriteAccessDo là giữ khoá ghi catalog lâu gấp
     nhiều lần cần thiết, mà khoá ghi chính là thứ làm Lightroom đơ.

     Vì sao chia lô ở lượt 2: trước đây cả job nằm trong MỘT withWriteAccessDo
     timeout 60 giây. Thư mục 858 ảnh thì Lightroom chỉ kịp ghi phần đầu rồi
     giao dịch hết giờ — mà applyDevelopSettings đã gọi xong nên bộ đếm vẫn báo
     "áp 857 ảnh", trong khi catalog thực tế chỉ nhận được số ảnh đang hiển thị
     ở lưới Library. Đúng triệu chứng: ảnh đã cuộn tới thì đổi, ảnh chưa kéo tới
     thì không. Mỗi lô một giao dịch riêng nên không lô nào chạm timeout.

     Vì sao có lượt 3: đó là câu trả lời cho "làm sao chắc chắn TẤT CẢ ảnh đã
     nhận thông số". Đếm số lần gọi applyDevelopSettings không chứng minh được
     gì — lượt 3 đọc lại từ catalog nên nói đúng sự thật. ]]
--[[ DUNG SAN PREVIEW SAU KHI AP — vi sao co luot nay.

     Doi thong so xong thi MOI preview da dung cua nhung anh do thanh loi thoi.
     Sang Develop bam vao mot tam, Lightroom hien preview CU lam anh tam (day la
     luc thay mau cu), roi moi nap du lieu RAW day du, ap thong so moi va dung
     lai. Buoc dung lai do phai lam MOT LAN CHO MOI TAM sau bat ky lan doi thong
     so hang loat nao — do la ly do bam toi anh nao cung phai cho mot nhip.

     KHONG co ham "build previews" trong SDK. Nhung requestJpegThumbnail(w,h,cb)
     thi ep Lightroom dung anh o co yeu cau roi cat vao thap preview. Goi no cho
     tung anh ngay sau khi ap la don phan viec nang do ve LUC NAY, thay vi de
     nguoi dung ganh tung nhip khi ngoi chon anh.

     BA CHO PHAI CAN THAN
       1. Ban ra 741 yeu cau cung luc la lam nghen Lightroom. Phai chia lo va
          CHO CALLBACK cua lo truoc xong moi ban lo sau.
       2. Callback chi chay khi task nay nhuong CPU — nen phai LrTasks.sleep
          trong vong cho, khong duoc quay vong ban.
       3. Mot anh hong khong duoc lam dung ca luot: dem vao 'loi' roi di tiep.

     Co the tat han: dat PREVIEW_CANH = 0.
]]
--[[ CANH DAI PHAI >= CANH DAI MAN HINH, khong duoc nho hon.
     Man hinh may nay 2560x1440. Preview 1440 px THAP HON canh dai 2560, nen khi
     xem to trong Library, Lightroom van phai dung lai — dung san cung bang thua.
     2880 la muc chuan ke tiep cua Lightroom tren 2560.
     Doi man hinh thi doi so nay, va doi ca Catalog Settings > File Handling >
     Standard Preview Size cho khop. ]]
local PREVIEW_CANH  = 0      -- 0 = TAT. Xem ghi chu o luot 4 trong applyJob.
local PREVIEW_LO    = 8      -- so anh gui cung luc
local PREVIEW_CHO   = 20     -- giay cho toi da cho mot lo, roi bo qua di tiep

local APPLY_CHUNK = 100
local SCAN_CHUNK  = 400     -- luot chi doc: lo to hon duoc, khong giu khoa ghi
local CHUNK_BREATH = 0.15   -- giay nghi giua hai lo ghi, de UI Lightroom kip tho

--[[ Đồng hồ đo. os.time() chỉ tới giây, os.clock() đo thời gian CPU nên vô
     dụng ở đây (phần lớn thời gian là chờ Lightroom, không phải chạy Lua).
     LrDate.currentTime() trả về giây dạng số thực — đúng thứ cần. ]]
local LrDate = import "LrDate"
local function now()
    if LrDate and LrDate.currentTime then return LrDate.currentTime() end
    return os.time()
end

--[[ Dung san preview cho danh sach anh. Tra ve so anh dung duoc va so loi.

     photos: mang LrPhoto. tienDo(daXong, tong): goi sau moi lo, co the nil.
]]
function M.warmPreviews(photos, tienDo)
    if PREVIEW_CANH <= 0 or #photos == 0 then
        return { xong = 0, loi = 0, tat = true }
    end
    local xong, loi = 0, 0
    local idx = 1
    while idx <= #photos do
        local last = math.min(idx + PREVIEW_LO - 1, #photos)
        local cho = last - idx + 1
        local den = 0
        for i = idx, last do
            local ok = M.try("requestThumb", function()
                photos[i]:requestJpegThumbnail(PREVIEW_CANH, PREVIEW_CANH,
                    function(data)
                        den = den + 1
                        if data then xong = xong + 1 else loi = loi + 1 end
                    end)
                return true
            end)
            if not ok then
                --[[ Goi khong duoc thi khong bao gio co callback cho anh nay.
                     Phai tu tang bo dem, neu khong ca lo se cho het 20 giay. ]]
                den = den + 1
                loi = loi + 1
            end
        end
        --[[ Cho lo nay xong. sleep chu khong phai quay vong: callback cua
             requestJpegThumbnail chi chay duoc khi task nay nhuong CPU. ]]
        local t0 = now()
        while den < cho and (now() - t0) < PREVIEW_CHO do
            LrTasks.sleep(0.05)
        end
        if den < cho then
            --[[ Het gio thi coi phan con lai la loi va DI TIEP. Dung han o day
                 thi nhung anh phia sau mat luon phan dung san — te hon nhieu so
                 voi vai tam khong kip. ]]
            loi = loi + (cho - den)
            M.log(string.format("warmPreviews: lo %d-%d het %d giay, bo qua %d anh",
                                idx, last, PREVIEW_CHO, cho - den))
        end
        if tienDo then tienDo(math.min(last, #photos), #photos) end
        idx = last + 1
    end
    return { xong = xong, loi = loi, tat = false }
end


function M.applyJob(rows, jobName)
    local catalog = LrApplication.activeCatalog()
    local t0 = now()
    local tScan, tWrite, tVerify = 0, 0, 0
    local applied, failed, rated, skipped = 0, 0, 0, 0
    local resolved = {}     -- {photo=, rec=} — moi anh tim duoc trong catalog
    local notFound = {}     -- duong dan khong co trong catalog
    local todo = {}         -- {photo=, settings=, dev=, rating=}
    local vcopies = 0

    -- ---------------------------------------------------------- luot 1: do
    local pending = {}
    for i = 1, #rows do pending[#pending + 1] = rows[i] end

    local function resolveAll(lookup)
        local left = {}
        local idx = 1
        while idx <= #pending do
            local last = math.min(idx + SCAN_CHUNK - 1, #pending)
            M.try("resolveChunk", function()
                for i = idx, last do
                    local rec = pending[i]
                    local photo = lookup(rec.path)
                    if photo then
                        resolved[#resolved + 1] = { photo = photo, rec = rec }
                    else
                        left[#left + 1] = rec
                    end
                end
                return true
            end)
            LrTasks.yield()
            idx = last + 1
        end
        pending = left
    end

    resolveAll(function(p) return catalog:findPhotoByPath(p) end)

    -- Con anh truot -> dung bang tra chuan hoa roi do lai
    if #pending > 0 then
        local before = #pending
        local built
        if indexCache and (os.time() - indexCache.at) < INDEX_TTL then
            built = indexCache
        else
            local t0 = os.time()
            built = M.try("buildIndex", function()
                local idx, n, vc = M.buildPathIndex(catalog)
                return { idx = idx, n = n, vc = vc, at = os.time() }
            end)
            if built and built.n > 0 then
                indexCache = built
                M.log(string.format("lap bang tra %d anh trong catalog (%ds)",
                                    built.n, os.time() - t0))
            end
        end
        if built and built.n > 0 then
            vcopies = built.vc or 0
            resolveAll(function(p) return built.idx[normKey(p)] end)
            local rescued = before - #pending
            if rescued > 0 then
                M.log(string.format("bang tra cuu them %d anh ma findPhotoByPath " ..
                                    "khong thay (lech hoa/thuong hoac dau gach)",
                                    rescued))
            end
        end
    end
    for i = 1, #pending do notFound[#notFound + 1] = pending[i].path end

    -- ------------------------------------------------ luot 1b: so, chon viec
    local idx = 1
    while idx <= #resolved do
        local last = math.min(idx + SCAN_CHUNK - 1, #resolved)
        M.try("scanChunk", function()
            for i = idx, last do
                local photo, rec = resolved[i].photo, resolved[i].rec
                local s = photo:getDevelopSettings()
                if type(s) ~= "table" then
                    failed = failed + 1
                    resolved[i].skip = true
                else
                    local bad = diffFields(s, rec.settings)
                    local wantDev = #bad > 0
                    local wantRating = false
                    if rec.rating and rec.rating > 0 then
                        wantRating = (tonumber(photo:getRawMetadata("rating")) or 0)
                                     ~= rec.rating
                    end
                    if wantDev or wantRating then
                        for key, val in pairs(rec.settings) do s[key] = val end
                        if rec.settings.Temperature or rec.settings.Tint then
                            s.WhiteBalance = "Custom"
                        end
                        todo[#todo + 1] = { photo = photo, settings = s, dev = wantDev,
                                            rating = wantRating and rec.rating or nil }
                    else
                        skipped = skipped + 1
                    end
                end
            end
            return true
        end)
        LrTasks.yield()
        idx = last + 1
    end

    -- --------------------------------------------------------- luot 2: ghi
    tScan = now() - t0
    local tw = now()
    idx = 1
    while idx <= #todo do
        local last = math.min(idx + APPLY_CHUNK - 1, #todo)
        local beforeApplied, beforeRated = applied, rated
        local okChunk, errChunk = M.try("applyChunk", function()
            catalog:withWriteAccessDo("AutoTone", function()
                for i = idx, last do
                    local t = todo[i]
                    if t.dev then
                        t.photo:applyDevelopSettings(t.settings, "AutoTone")
                        applied = applied + 1
                    end
                    --[[ Rating KHONG phai develop setting. applyDevelopSettings
                         khong ghi duoc, phai dung setRawMetadata rieng. ]]
                    if t.rating then
                        t.photo:setRawMetadata("rating", t.rating)
                        rated = rated + 1
                    end
                end
            end, { timeout = 30 })
            return true
        end)

        if not okChunk then
            -- Giao dich hong thi Lightroom huy CA lo, ke ca may anh vua dem la
            -- xong — phai tra bo dem ve moc dau lo roi moi tinh la loi.
            applied, rated = beforeApplied, beforeRated
            failed = failed + (last - idx + 1)
            M.log(string.format("LOI lo %d-%d: %s", idx, last, tostring(errChunk)))
        end

        if last < #todo then LrTasks.sleep(CHUNK_BREATH) end
        idx = last + 1
    end

    -- ------------------------------------------------- luot 3: kiem chung
    tWrite = now() - tw
    local tv = now()
    local bad = {}
    idx = 1
    while idx <= #resolved do
        local last = math.min(idx + SCAN_CHUNK - 1, #resolved)
        M.try("verifyChunk", function()
            for i = idx, last do
                if not resolved[i].skip then
                    local photo, rec = resolved[i].photo, resolved[i].rec
                    local s = photo:getDevelopSettings()
                    if type(s) ~= "table" then
                        bad[#bad + 1] = { path = rec.path, why = "khong-doc-duoc" }
                    else
                        local d = diffFields(s, rec.settings)
                        if #d > 0 then
                            bad[#bad + 1] = { path = rec.path,
                                              why = table.concat(d, ",") }
                        end
                    end
                end
            end
            return true
        end)
        LrTasks.yield()
        idx = last + 1
    end

    -- Chi ghi file khi CO van de — khong rac them file vao thu muc jobs
    if #bad > 0 or #notFound > 0 then
        M.writeVerify(jobName, bad, notFound)
    end

    tVerify = now() - tv

    --[[ LUOT 4 (dung san preview) DA BI GO KHOI DAY. DUNG DAT LAI VAO.

         DO THAT ngay 6/9 tren buoi PUBGDay1:
             dung san preview: 0 xong, 39 loi, 100.1 giay
             ... 126 lo "het 20 giay, bo qua 8 anh", 950 anh bi bo qua
             hai job 1030 anh ket o .running, khong bao gio markDone

         requestJpegThumbnail KHONG BAO GIO goi callback trong ngu canh nay —
         0 thanh cong tren 39 anh, khong phai "cham", ma la khong chay. Moi lo
         cho du 20 giay roi bo qua: 1030 anh = 129 lo = ~43 phut cho MOI job, va
         hai job chay chong nhau.

         Hau qua nang hon nhieu so voi cai no dinh sua: applyJob khong ket thuc
         -> job khong duoc danh dau xong -> cac job sau xep hang -> Lightroom
         KHONG NHAN DUOC THONG SO NAO CA. Nguoi dung bao "muc 3 bao da ghi xong
         nhung Lightroom chua nhan duoc".

         BAI HOC, ghi o day de lan sau khong lap: mot tinh nang KHONG THU DUOC
         tren Lightroom that thi khong duoc dat vao duong di chinh cua viec ap
         thong so. Muon lam lai thi lam thanh mot lenh RIENG trong menu, nguoi
         dung tu bam, hong thi chi hong mot minh no.

         M.warmPreviews van con ben duoi de sau nay lam lai cho tu te, nhung
         PREVIEW_CANH da dat ve 0 nen goi no cung khong lam gi.
    ]]

    return { applied = applied, skipped = skipped, failed = failed, rated = rated,
             previewed = 0, previewFailed = 0, previewOff = true,
             tPreview = 0,
             missing = #notFound, unverified = #bad, vcopies = vcopies,
             total = #rows,
             -- Do rieng tung luot: chi co so lieu moi biet cho nao that su ton
             -- thoi gian, khong phai doan. Luot ghi la luot giu khoa catalog.
             tScan = tScan, tWrite = tWrite, tVerify = tVerify }
end

--[[ Ghi danh sách ảnh chưa nhận được thông số, để autotone/giao diện đọc lại.
     Có tên cụ thể thì còn sửa được; chỉ có con số thì chỉ biết ngồi đoán. ]]
function M.writeVerify(jobName, bad, notFound)
    local base = tostring(jobName or "job")
    base = string.gsub(base, "^apply_", "")
    base = string.gsub(base, "%.tsv$", "")
    local dest = LrPathUtils.child(M.jobDir(), "verify_" .. base .. ".tsv")
    local fh = io.open(dest, "w")
    if not fh then return nil end
    fh:write("path\tvande\n")
    for _, r in ipairs(notFound) do
        fh:write(tostring(r) .. "\tkhong-co-trong-catalog\n")
    end
    for _, r in ipairs(bad) do
        fh:write(tostring(r.path) .. "\tchua-nhan:" .. tostring(r.why) .. "\n")
    end
    fh:close()
    return dest
end

--[[ ============================================================
     XUẤT THÔNG SỐ THEO YÊU CẦU TỪ APP

     Trước đây phải vào Lightroom bấm menu "xuất thông số" bằng tay. Nay app
     ghi ra jobs/request_export.txt (dòng đầu = đường dẫn thư mục), vòng lặp
     nền thấy thì tự chạy. Cùng cơ chế với job áp, chỉ ngược chiều — không
     thêm công nghệ mới nào.

     KHÁC BIỆT QUAN TRỌNG so với đường menu: lấy ảnh theo THƯ MỤC chứ không
     theo vùng chọn. Chạy từ nền thì không có vùng chọn nào đáng tin — người
     dùng có thể đang bấm ở đâu đó khác, hoặc không chọn gì.
     ============================================================ ]]

local EXPORT_FIELDS = { "Exposure2012", "Highlights2012", "Shadows2012",
                        "Temperature", "Tint", "AsShotTemperature", "AsShotTint" }
-- Rating KHONG phai develop setting nen phai lay rieng bang getRawMetadata,
-- xem cho ghi tung dong ben duoi. Can de doi chieu voi nhan loc anh cua nguoi dung.

local function numOrEmpty(v)
    if type(v) == "number" then
        return string.format("%.14g", v)   -- du chu so, khong sinh duoi .0 thua
    elseif type(v) == "string" and tonumber(v) then
        return v
    end
    return ""
end

--[[ Ảnh trong một thư mục.

     Đường chính là getFolderByPath + getPhotos. Có đường DỰ PHÒNG quét cả
     catalog rồi lọc theo tiền tố đường dẫn, vì getFolderByPath được biết là
     trả về nil với ổ mạng chưa ánh xạ và vài loại thư mục khác — thà chậm
     còn hơn im lặng trả về rỗng rồi người dùng tưởng thư mục không có ảnh. ]]
function M.photosInFolder(catalog, path)
    local photos = M.try("folderPhotos", function()
        local f = catalog:getFolderByPath(path)
        if not f or type(f.getPhotos) ~= "function" then return nil end
        return f:getPhotos()
    end)
    if type(photos) == "table" and #photos > 0 then
        return photos, "theo thu muc"
    end

    local want = normKey(path)
    if string.sub(want, -1) ~= "/" then want = want .. "/" end
    local out = {}
    local all = catalog:getAllPhotos()
    if all then
        for i = 1, #all do
            local p = all[i]:getRawMetadata("path")
            if p and string.sub(normKey(p), 1, #want) == want then
                out[#out + 1] = all[i]
            end
            if i % 2000 == 0 then LrTasks.yield() end
        end
    end
    return out, "quet ca catalog"
end

--[[ Ghi bản xuất thông số hiện tại của một danh sách ảnh.

     Chia lô 200: mỗi lô một khối read-access ngắn, giữa các lô thì yield.
     Bọc cả vài nghìn ảnh trong một khối read-access sẽ treo giao diện thật. ]]
local EXPORT_CHUNK = 200

--[[ opts.skipRating: bỏ qua ảnh có đúng số sao này (thường là 1 = ảnh đã loại).

     VÌ SAO: người dùng lọc ảnh trước khi xử lý, gán 1 sao cho ảnh bỏ. Xuất cả
     ảnh 1 sao thì vừa chậm vừa làm loãng dữ liệu học gu — ảnh đã loại thì
     không ai sửa, nên bộ thu thập sẽ đếm chúng là "tool làm đúng" dù người
     dùng chưa từng nhìn tới. Cùng quy ước với burst_reject_rating của autotone.

     Lọc BÊN TRONG vòng thu thập chứ không lọc trước: đọc rating cũng cần
     read-access y như đọc develop settings, để chung một khối cho gọn. ]]
function M.writeExport(catalog, photos, onProgress, opts)
    if not photos or #photos == 0 then return 0, nil, "khong co anh nao" end
    opts = opts or {}
    --[[ 0 nghĩa là KHÔNG lọc gì. Phải quy về nil vì trong Lua số 0 vẫn là giá
         trị đúng — để nguyên thì `skipRating and rating == skipRating` sẽ khớp
         mọi ảnh chưa gán sao và lặng lẽ vứt gần hết bản xuất. ]]
    local skipRating = tonumber(opts.skipRating)
    if skipRating == 0 then skipRating = nil end
    local skipped = 0

    -- Thu mot anh de biet co phai boc read-access khong
    local direct = M.try("probeDirect", function()
        return photos[1]:getDevelopSettings()
    end)
    local needRead = type(direct) ~= "table"

    local lines = { "path\t" .. table.concat(EXPORT_FIELDS, "\t") .. "\tRating" }
    local noPath, noSettings = 0, 0

    local function collectRange(from, to)
        for i = from, to do
            local photo = photos[i]
            local path = photo:getRawMetadata("path")
            local rating = tonumber(photo:getRawMetadata("rating")) or 0
            if skipRating and rating == skipRating then
                skipped = skipped + 1
            elseif not path or path == "" then
                noPath = noPath + 1
            else
                local s = photo:getDevelopSettings()
                if type(s) == "table" then
                    local row = { path }
                    for _, key in ipairs(EXPORT_FIELDS) do
                        row[#row + 1] = numOrEmpty(s[key])
                    end
                    row[#row + 1] = numOrEmpty(rating)
                    lines[#lines + 1] = table.concat(row, "\t")
                else
                    noSettings = noSettings + 1
                end
            end
        end
    end

    local idx = 1
    while idx <= #photos do
        local last = math.min(idx + EXPORT_CHUNK - 1, #photos)
        if needRead then
            catalog:withReadAccessDo(function() collectRange(idx, last) end)
        else
            collectRange(idx, last)
        end
        if onProgress then onProgress(last, #photos) end
        LrTasks.yield()
        idx = last + 1
    end

    if #lines == 1 then
        if skipped > 0 then
            return 0, nil, string.format("ca %d anh deu bi bo vi %d sao", skipped, skipRating)
        end
        return 0, nil, string.format("%d anh thieu duong dan, %d anh khong doc duoc thong so",
                                     noPath, noSettings)
    end

    local dir = M.jobDir()
    if not LrFileUtils.exists(dir) then LrFileUtils.createAllDirectories(dir) end
    local dest = LrPathUtils.child(dir, "export_" .. os.date("%Y%m%d_%H%M%S") .. ".tsv")
    local tmp = dest .. ".part"
    local fh, err = io.open(tmp, "w")
    if not fh then return 0, nil, tostring(err) end
    fh:write(table.concat(lines, "\n") .. "\n")
    fh:close()
    -- .part roi doi ten: app khong bao gio doc phai file dang ghi do
    M.try("replaceExport", function()
        LrFileUtils.delete(dest)
        LrFileUtils.move(tmp, dest)
    end)

    -- chi giu ban moi nhat cho do rac
    M.try("cleanupExports", function()
        for p in LrFileUtils.files(dir) do
            local name = LrPathUtils.leafName(p)
            if p ~= dest and string.sub(name, 1, 7) == "export_"
               and string.sub(name, -4) == ".tsv" then
                LrFileUtils.delete(p)
            end
        end
    end)

    return #lines - 1, dest, nil, skipped
end

--[[ Xử lý yêu cầu xuất do app ghi ra. Trả về số ảnh đã xuất, hoặc 0. ]]
function M.runExportRequest()
    local req = LrPathUtils.child(M.jobDir(), "request_export.txt")
    if not LrFileUtils.exists(req) then return 0 end

    -- Giành y như job áp, để hai vòng lặp khong cung lam
    local claimed = M.claim(req)
    if not claimed then return 0 end

    --[[ Dòng đầu = đường dẫn thư mục. Các dòng sau dạng khoa=gia_tri.
         Giữ dòng đầu là đường dẫn để bản cũ của app vẫn chạy được. ]]
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
    M.try("dropRequest", function() LrFileUtils.delete(claimed) end)

    if not folder or folder == "" then
        M.log("yeu cau xuat: thieu duong dan thu muc")
        return 0
    end
    folder = string.gsub(folder, "^%s*(.-)%s*$", "%1")

    local catalog = LrApplication.activeCatalog()
    local photos, how = M.photosInFolder(catalog, folder)
    if not photos or #photos == 0 then
        M.log("yeu cau xuat: khong thay anh nao trong " .. folder)
        return 0
    end

    local n, dest, err, skipped = M.writeExport(catalog, photos, nil,
                                               { skipRating = opts.skip_rating })
    if err then
        M.log("yeu cau xuat LOI: " .. tostring(err))
        return 0
    end
    local msg = string.format("yeu cau tu app: xuat %d anh (%s)", n, how)
    if (skipped or 0) > 0 then
        msg = msg .. string.format(", bo %d anh %s sao", skipped, tostring(opts.skip_rating))
    end
    M.log(msg .. " -> " .. LrPathUtils.leafName(dest))
    return n
end

--[[ Danh sách job chưa xử lý, cũ trước mới sau.

     Chỉ nhận file tên "apply_*.tsv". Thư mục này còn chứa "export_*.tsv" là chiều
     ngược lại (catalog -> autotone); vơ luôn cả hai thì plugin sẽ đem
     AsShotTemperature áp thành thông số develop, hỏng ảnh. ]]
function M.pendingJobs()
    local dir, out = M.jobDir(), {}
    if not LrFileUtils.exists(dir) then return out end
    for p in LrFileUtils.files(dir) do
        local name = LrPathUtils.leafName(p)
        if string.sub(name, 1, 6) == "apply_" and string.sub(name, -4) == ".tsv" then
            out[#out + 1] = p
        end
    end
    table.sort(out)
    return out
end

--[[ Giành lấy một job trước khi đọc, bằng cách đổi tên .tsv -> .tsv.running.

     VÌ SAO: vòng lặp nền và menu "áp thông số mới nhất" có thể chạy cùng lúc,
     và mỗi lần bấm Reload trong Plug-in Manager lại sinh thêm một vòng lặp nữa
     (xem Init.lua). Hai bên cùng thấy một file, cùng áp cả job — Lightroom phải
     làm gấp đôi, gấp ba việc, và khoá ghi catalog bị tranh liên tục. Nhìn log
     cũ là thấy: mỗi job in ra 2-3 dòng kết quả giống hệt nhau.

     Đổi tên là thao tác nguyên tử của hệ thống file: chỉ một bên đổi được, bên
     kia thấy file biến mất và bỏ qua. ]]
--[[ Mã nhận dạng riêng của LẦN NẠP này.

     tostring({}) trả về địa chỉ của một bảng mới, khác nhau ở mỗi bản nạp
     plugin. Cần thứ này vì os.time() chỉ tới giây và math.random không gieo
     hạt thì hai vòng lặp khởi động cùng lúc sẽ sinh ra tên file GIỐNG HỆT
     nhau — đúng thứ phá cơ chế giành job bên dưới. ]]
local STATE_ID = string.gsub(tostring({}), "[^%w]", "")
local claimSeq = 0

function M.claim(path)
    --[[ Giành job bằng cách đổi tên sang một cái tên KHÔNG AI ĐOÁN ĐƯỢC.

         Bản trước đặt tên cố định `<job>.running` rồi kiểm `exists(running)`.
         Sai: khi hai vòng cùng chạy, bên thua move thất bại nhưng vẫn thấy
         file `.running` (do bên thắng vừa tạo) nên CŨNG tưởng mình giành
         được — hai bên cùng áp một job.

         Đo thật trong plugin.log ngày 31/8: một job in ra hai dòng kết quả
         giống hệt, và bảng tra catalog bị dựng hai lần trong cùng một giây
         dù có bộ nhớ đệm 120 giây (đệm nằm trong từng bản nạp, hai bản nạp
         là hai đệm).

         Tên duy nhất thì chỉ bên move thành công mới thấy file CỦA MÌNH tồn
         tại. Bên thua kiểm tên riêng của nó, thấy không có, và bỏ qua. ]]
    claimSeq = claimSeq + 1
    local running = string.format("%s.%s-%d-%d.running",
                                  path, STATE_ID, os.time(), claimSeq)
    M.try("claim", function()
        LrFileUtils.move(path, running)
        return true
    end)
    if LrFileUtils.exists(running) and not LrFileUtils.exists(path) then
        return running
    end
    return nil
end

--[[ Trả lại các job bị bỏ dở của lần chạy trước.

     Lightroom tắt giữa chừng thì file còn kẹt ở tên `.running` và không bao
     giờ được xử lý nữa. Gọi lúc nạp plugin, khi chắc chắn chưa vòng nào đang
     chạy — không gọi trong vòng lặp, vì như vậy sẽ cướp job của vòng kia. ]]
function M.recoverStale()
    local dir = M.jobDir()
    if not LrFileUtils.exists(dir) then return 0 end
    local n = 0
    for p in LrFileUtils.files(dir) do
        local name = LrPathUtils.leafName(p)
        if string.sub(name, -8) == ".running" then
            local back = string.gsub(p, "%.[^.]*%.running$", "")
            if back == p then back = string.gsub(p, "%.running$", "") end
            M.try("recoverStale", function() LrFileUtils.move(p, back) end)
            n = n + 1
        end
    end
    if n > 0 then M.log("tra lai " .. n .. " job bo do cua lan chay truoc") end
    return n
end

-- Xử lý xong thì đổi đuôi thành .done để lần sau không đọc lại
function M.markDone(path)
    -- Bo phan duoi cua ten giu cho: "<job>.tsv.<ma-rieng>.running"
    local base = string.gsub(path, "%.[^.]*%.running$", "")
    if base == path then base = string.gsub(path, "%.running$", "") end
    local dest = string.gsub(base, "%.tsv$", "") .. ".done"
    M.try("markDone", function()
        LrFileUtils.delete(dest)             -- lần chạy trước có thể còn sót
        LrFileUtils.move(path, dest)
    end)
    -- Nếu vẫn không đổi tên được thì phải xoá, không thì vòng lặp áp đi áp lại
    if LrFileUtils.exists(path) then
        M.try("markDoneDelete", function() LrFileUtils.delete(path) end)
    end
end

--[[ Dọn bớt file .done cũ. Thư mục jobs được liệt kê mỗi 5 giây; để nó phình
     tới hàng nghìn file thì mỗi nhịp dò lại là một lần quét đĩa vô ích. ]]
local KEEP_DONE = 30

function M.pruneDone()
    local dir = M.jobDir()
    if not LrFileUtils.exists(dir) then return 0 end
    local files = {}
    for p in LrFileUtils.files(dir) do
        local name = LrPathUtils.leafName(p)
        if string.sub(name, -5) == ".done" then files[#files + 1] = p end
    end
    if #files <= KEEP_DONE then return 0 end
    table.sort(files)                      -- ten co timestamp -> cu dung truoc
    local n = 0
    for i = 1, #files - KEEP_DONE do
        M.try("pruneDone", function() LrFileUtils.delete(files[i]) end)
        n = n + 1
    end
    return n
end

--[[ Job GẦN NHẤT đã áp xong, đọc từ chính file .done trong thư mục job.

     VÌ SAO CẦN: "tự động áp" mặc định BẬT, nên plugin nuốt job trong vài giây kể
     từ lúc autotone ghi ra. Người dùng bấm Ghi bên app rồi sang Lightroom bấm
     "áp thông số mới nhất" thì hàng đợi đã rỗng THẬT — vì việc đã xong.

     Bản cũ chỉ nói "Không có thông số mới nào đang chờ. Chạy autotone (bấm 2 ·
     Ghi) rồi quay lại đây." Câu đó đúng về mặt chữ nhưng đọc như báo lỗi, và
     còn chỉ sai đường: bảo người ta đi làm lại đúng việc VỪA XONG. Ngày 4/9
     người dùng bấm Ghi ba lần liên tiếp vì tưởng hỏng — nhật ký ghi rõ lần đầu
     "ap 1031, 0 loi, kiem chung DU", hai lần sau "ap 0, bo qua 1031 (da dung
     san)". Không có gì hỏng cả; chỉ có câu thông báo là sai.

     Trả về (tên job, thời điểm) hoặc nil. ]]
function M.lastDone()
    local dir = M.jobDir()
    if not LrFileUtils.exists(dir) then return nil end
    local moi, moi_t = nil, nil
    for p in LrFileUtils.files(dir) do
        local name = LrPathUtils.leafName(p)
        if string.sub(name, -5) == ".done" then
            local a = LrFileUtils.fileAttributes(p)
            local t = a and (a.fileModificationDate or a.fileCreationDate)
            if t and (moi_t == nil or t > moi_t) then
                moi, moi_t = name, t
            end
        end
    end
    if not moi then return nil end
    return moi, moi_t
end


function M.runPending()
    local jobs = M.pendingJobs()
    local done, applied, missing, skipped, unverified = 0, 0, 0, 0, 0
    local previewed = 0
    for _, jp in ipairs(jobs) do
        local name = LrPathUtils.leafName(jp)
        local claimed = M.claim(jp)
        if claimed then                     -- ai gianh duoc thi nguoi do lam
            done = done + 1
            local rows, err = M.readJob(claimed)
            if err then
                M.log("bo qua " .. name .. ": " .. err)
            else
                local res, applyErr = M.try("applyJob", function()
                    return M.applyJob(rows, name)
                end)
                if res then
                    applied    = applied + res.applied
                    missing    = missing + res.missing
                    skipped    = skipped + res.skipped
                    unverified = unverified + res.unverified
                    previewed  = previewed + (res.previewed or 0)
                    -- Ghi CA so dong trong job: lech nhau la biet ngay co anh
                    -- khong vao duoc catalog, khong phai ngoi doan nhu truoc.
                    local line = string.format(
                        "%s: ap %d, bo qua %d (da dung san), tong %d dong; " ..
                        "%d khong co trong catalog, %d loi, %d gan sao",
                        name, res.applied, res.skipped, res.total,
                        res.missing, res.failed, res.rated)
                    if res.unverified > 0 then
                        line = line .. string.format("; CHUA NHAN %d anh (xem verify_*.tsv)",
                                                     res.unverified)
                    else
                        line = line .. "; kiem chung DU"
                    end
                    if res.vcopies > 0 then
                        line = line .. string.format("; %d ban sao ao KHONG duoc ap",
                                                     res.vcopies)
                    end
                    line = line .. string.format(
                        " | do %.1fs, ghi %.1fs, kiem chung %.1fs",
                        res.tScan or 0, res.tWrite or 0, res.tVerify or 0)
                    M.log(line)
                else
                    M.log("LOI khi ap " .. name .. ": " .. tostring(applyErr))
                end
            end
            M.markDone(claimed)
        end
    end
    if done > 0 then M.pruneDone() end
    return done, applied, missing, skipped, unverified, previewed
end

return M
