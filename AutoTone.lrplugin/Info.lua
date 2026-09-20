--[[
  AutoTone — plugin Lightroom Classic cho autotone.py

  Đọc file "job" do autotone ghi ra rồi áp thẳng thông số vào catalog, thay cho
  thao tác tay Metadata > Read Metadata from File.

  Vì sao làm kiểu này thay vì đọc XMP:
    - SDK Lightroom KHÔNG có hàm "read metadata from file", nên không tự động hoá
      được thao tác đó từ bên ngoài.
    - Ngược lại, SDK có photo:getDevelopSettings() và photo:applyDevelopSettings(),
      cho phép sửa ĐÚNG mấy trường tone và giữ nguyên phần còn lại của ảnh trong
      catalog. An toàn hơn hẳn Read Metadata from File (thao tác đó ghi đè toàn bộ
      chỉnh sửa đang có).
]]

return {
    LrSdkVersion = 10.0,
    LrSdkMinimumVersion = 6.0,

    LrToolkitIdentifier = "vn.saymedia.autotone",
    LrPluginName = "AutoTone (SAY Media)",

    LrInitPlugin = "Init.lua",

    --[[ Export Filter: cắm vào chính luồng Export của người dùng để đọc thư
         mục đích. Người dùng phải tích nó MỘT LẦN trong hộp thoại Export, mục
         "Post-Process Actions", rồi lưu vào preset — sau đó mọi lần Export
         bằng preset ấy (kể cả Export with Previous) đều tự ghi lại.

         Không có cách nào tự bật hộ: Lightroom không cho plugin sửa preset
         Export của người dùng, và cũng không phát sự kiện Export nào để nghe
         từ ngoài. Xem đầu BatDuongDan.lua. ]]
    LrExportFilterProvider = {
        title = "AutoTone: ghi lại thư mục Export",
        file = "BatDuongDan.lua",
        id = "vn.saymedia.autotone.batduongdan",
    },

    LrLibraryMenuItems = {
        {
            title = "AutoTone: xuất thông số cho autotone",
            file = "ExportForAutoTone.lua",
        },
        {
            title = "AutoTone: áp thông số mới nhất",
            file = "ApplyNow.lua",
        },
        {
            title = "AutoTone: dựng ảnh duyệt nhanh",
            file = "DuyetNhanh.lua",
        },
        {
            title = "AutoTone: bật/tắt tự động áp",
            file = "ToggleAuto.lua",
        },
        {
            title = "AutoTone: chẩn đoán",
            file = "Diagnose.lua",
        },
    },

    VERSION = { major = 1, minor = 0, revision = 0 },
}
