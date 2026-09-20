--[[ BẮT ĐƯỜNG DẪN EXPORT — ghi lại thư mục Lightroom đang xuất ảnh ra.

     ============================================================
     VÌ SAO CẦN
     ============================================================

     Khâu 5 của app trước nay phải hỏi tay "anh Export ra đâu?", vì Lightroom
     không để lại dấu vết nào đọc được từ ngoài. Hỏi tay thì có ngày nhập nhầm,
     và mọi khâu sau (Retouch, gói duyệt, học gu) đi theo cái sai đó.

     Lightroom KHÔNG phát sự kiện nào khi người dùng bấm Export — không có hook
     toàn cục để nghe. Đường duy nhất có tài liệu là plugin tự cắm vào chính
     luồng Export đó dưới dạng một Export Filter (Post-Process Action). Lúc đó
     SDK đưa cho ta nguyên bảng thông số người dùng vừa chọn trong hộp thoại,
     trong đó có LR_export_destinationPathPrefix.

     ============================================================
     VÌ SAO CHỈ KHAI shouldRenderPhoto, KHÔNG KHAI postProcessRenderedPhotos
     ============================================================

     Đây là quyết định về an toàn, không phải về tiện.

     postProcessRenderedPhotos đặt plugin NẰM CHẮN NGANG đường ảnh đi ra: khi
     khai hàm đó, Lightroom render ảnh vào thư mục tạm rồi giao cho ta, và
     CHÍNH TA có trách nhiệm chuyển từng file về đích. Buổi 2000 ảnh JPEG cỡ
     lớn, nếu thư mục tạm khác ổ thì đó là 2000 lần chép thật; và một lỗi trong
     đoạn đó là hỏng cả buổi giao khách. Không đáng, chỉ để biết một đường dẫn.

     shouldRenderPhoto chạy TRƯỚC khi render, nhận đủ exportSettings, và việc
     của nó chỉ là trả lời "ảnh này có xuất không". Ta trả lời true cho mọi ảnh
     — tức là không đổi gì hết — và nhân tiện chép lại đường dẫn. Không đụng
     vào một file ảnh nào. Hỏng ở đây thì cùng lắm là app không biết thư mục,
     ảnh của khách vẫn ra đủ.

     Hình dạng "chỉ có shouldRenderPhoto" là hình dạng có thật, không phải tự
     nghĩ ra: xem plugin lọc ảnh Rejected trên diễn đàn Adobe, bảng trả về của
     nó cũng chỉ có exportPresetFields / startDialog / sectionForFilterInDialog
     / shouldRenderPhoto.

     ============================================================
     Ở ĐÂY pcall LÀ ĐƯỢC PHÉP
     ============================================================

     Luật chung của dự án là không bọc pcall quanh lời gọi SDK (xem đầu
     AutoToneCore.lua) vì lời gọi SDK có thể yield và pcall nuốt mất. Ở đây
     KHÔNG có lời gọi nào như vậy: chỉ ghép chuỗi đường dẫn và io.open. Bọc
     pcall là đúng chỗ, vì mục tiêu số một là hàm này KHÔNG BAO GIỜ được làm
     hỏng một lần Export thật của người dùng — dù ổ đầy, dù thư mục jobs bị
     xoá, dù bất cứ chuyện gì.
]]

local LrPathUtils = import "LrPathUtils"
local LrFileUtils = import "LrFileUtils"
local LrView      = import "LrView"

--[[ CỐ TÌNH KHÔNG require "AutoToneCore".

     Filter này chạy bên trong tiến trình Export của người dùng. Nếu nó nạp
     AutoToneCore mà file đó lỗi (bản đang sửa dở chẳng hạn), Lightroom sẽ báo
     lỗi filter ngay giữa hộp thoại Export. Vài dòng lặp lại ở đây rẻ hơn nhiều
     so với việc đó. ]]
local function jobDir()
    return LrPathUtils.child(_PLUGIN.path, "jobs")
end

local TEN_FILE = "export_lr_duongdan.txt"

-- Ghi lại lần cuối đã ghi gì, để 2000 ảnh không thành 2000 lần ghi file.
local dauVetCuoi = nil
local lucCuoi = 0

--[[ Số giây tối thiểu giữa hai lần ghi cùng một đường dẫn.

     Vì sao vẫn ghi lại dù đường dẫn không đổi: người dùng hay Export hai lần
     vào cùng thư mục (lần hai để bù mấy tấm sửa thêm). Nếu chỉ ghi khi đường
     dẫn ĐỔI thì lần hai không để lại dấu, và app tưởng bản Export là bản cũ —
     đúng cái bẫy đã làm 2032/2087 ảnh bị bỏ qua trong im lặng hôm 7/9. Mốc
     thời gian phải mới thì cảnh báo "bản Export cũ hơn lần ghi" mới đúng. ]]
local NGHI = 30

local function ghi(bang)
    local dir = jobDir()
    if not LrFileUtils.exists(dir) then
        LrFileUtils.createAllDirectories(dir)
    end
    local dest = LrPathUtils.child(dir, TEN_FILE)
    local tmp = dest .. ".part"
    local fh = io.open(tmp, "w")
    if not fh then return end
    for _, k in ipairs({ "thu_muc", "kieu", "thu_muc_con", "dinh_dang",
                         "tem", "nguon" }) do
        if bang[k] ~= nil then
            fh:write(k .. "=" .. tostring(bang[k]) .. "\n")
        end
    end
    fh:close()
    --[[ .part rồi đổi tên: app không bao giờ đọc phải file đang ghi dở. Cùng
         quy ước với job áp và với duyet_tiendo.txt. ]]
    LrFileUtils.delete(dest)
    LrFileUtils.move(tmp, dest)
end

--[[ Rút thư mục đích ra khỏi bảng thông số Export.

     LR_export_destinationType nói người dùng chọn kiểu nào:
       "specificFolder"  -> LR_export_destinationPathPrefix là thư mục đích
       "sourceFolder"    -> ảnh ra nằm cạnh ảnh gốc, prefix rỗng
     Có bật "Put in Subfolder" thì tên thư mục con nằm ở
     LR_export_destinationPathSuffix và đích thật là prefix\suffix.

     Tách riêng thành hàm thuần để bài kiểm gọi thẳng được, không cần Lightroom.
]]
local function tinhThuMuc(st)
    local kieu = st.LR_export_destinationType
    local goc = st.LR_export_destinationPathPrefix
    if type(goc) ~= "string" or goc == "" then return nil, kieu end
    local con = st.LR_export_destinationPathSuffix
    if st.LR_export_useSubfolder and type(con) == "string" and con ~= "" then
        return LrPathUtils.child(goc, con), kieu
    end
    return goc, kieu
end

local M = {}

M.tinhThuMuc = tinhThuMuc          -- lộ ra cho bài kiểm

--[[ Một dòng chữ trong hộp thoại Export, để người dùng thấy filter đang bật.

     Không có ô chỉnh nào: filter này không có gì để chỉnh, và mọi ô thừa đều
     là một chỗ để bấm nhầm. ]]
function M.sectionForFilterInDialog(f, _propertyTable)
    return {
        title = "AutoTone — ghi lại thư mục Export",
        f:static_text {
            title = "Không đổi gì trong lần Export này. Chỉ chép lại thư mục\n" ..
                    "anh vừa chọn, để khâu 5 của app tự điền, khỏi phải nhập tay.",
            fill_horizontal = 1,
        },
    }
end

--[[ Lightroom hỏi từng ảnh trước khi render. Ta luôn trả lời true.

     KHÔNG BAO GIỜ trả về false: trả false là RÚT ẢNH ĐÓ ra khỏi lượt Export.
     Filter này không có quyền quyết định ảnh nào được giao cho khách. ]]
function M.shouldRenderPhoto(exportSettings, _photo)
    pcall(function()
        if type(exportSettings) ~= "table" then return end
        local thu_muc, kieu = tinhThuMuc(exportSettings)
        if not thu_muc then return end
        local now = os.time()
        if dauVetCuoi == thu_muc and (now - lucCuoi) < NGHI then return end
        dauVetCuoi = thu_muc
        lucCuoi = now
        ghi({
            thu_muc = thu_muc,
            kieu = kieu or "",
            thu_muc_con = exportSettings.LR_export_useSubfolder
                          and (exportSettings.LR_export_destinationPathSuffix or "")
                          or "",
            dinh_dang = exportSettings.LR_format or "",
            tem = os.date("%Y-%m-%d %H:%M:%S"),
            nguon = "filter",
        })
    end)
    return true
end

return M
