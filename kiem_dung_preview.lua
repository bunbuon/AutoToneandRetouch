--[[ kiem_preview.lua — kiem logic warmPreviews bang SDK gia lap.

     Khong co Lightroom o day, nhung cho de sai nhat khong phai SDK: la viec
     chia lo, dem callback va thoat khi het gio. Ba thu do kiem duoc bang tay.
]]

-- ---------------------------------------------------------------- gia lap SDK
local GIO = 0                      -- dong ho gia, tu tang khi sleep
local hangDoi = {}                 -- callback dang cho, {khi=, fn=, dulieu=}

local function batDauGio() GIO = 0; hangDoi = {} end

_G.import = function(ten)
    if ten == "LrTasks" then
        return {
            sleep = function(s)
                GIO = GIO + s
                -- callback nao toi han thi chay
                local con = {}
                for _, c in ipairs(hangDoi) do
                    if c.khi <= GIO then c.fn(c.dulieu) else con[#con+1] = c end
                end
                hangDoi = con
            end,
            yield = function() end,
        }
    end
    return setmetatable({}, {__index = function() return function() end end})
end

-- ------------------------------------------------- ban sao warmPreviews thu that
-- Doc thang tu file that, cat dung ham ra, de khong bao gio kiem mot ban chep.
--[[ Duong dan lay tu tham so, mac dinh la thu muc plugin trong ma nguon.
     Ban truoc go cung "/tmp/plug2/..." — thu muc tam cua mot lan chay tu lau,
     nen bai kiem nay nem loi ngay dong dau tren MOI may khac. Mot bai kiem
     khong chay duoc thi khong canh duoc gi. ]]
local GOC = (...) or arg[1] or "AutoTone.lrplugin"
local duong = GOC .. "/AutoToneCore.lua"
local fh = assert(io.open(duong), "khong doc duoc " .. duong)
local nguon = fh:read("*a")
fh:close()
local i = nguon:find("local PREVIEW_CANH", 1, true)
local j = nguon:find("\nlocal APPLY_CHUNK", i, true)
local hangSo = nguon:sub(i, j):gsub("PREVIEW_CANH  = 0",
                                     "PREVIEW_CANH  = 1440")
local a = nguon:find("function M.warmPreviews", 1, true)
local b = nguon:find("\nend\n", nguon:find("return { xong = xong", a, true), true)
local hamSrc = nguon:sub(a, b + 4)

local M = { log = function() end }
M.try = function(_, fn)
    local ok, r = pcall(fn)
    if ok then return r end
    return nil, r
end
local now = function() return GIO end
--[[ Nap doan ma trong moi truong rieng. Lua 5.1 va 5.4 khac chu ky ham nay:
     5.1 co loadstring + setfenv, 5.4 co load(...,"t",env). Lam ca hai duong de
     bai kiem chay duoc bang lua5.1 (dung ban Lightroom dung) lan lua5.4. ]]
local ma = hangSo .. "\n" .. hamSrc
local moi_truong = setmetatable(
    { M = M, now = now, LrTasks = import("LrTasks"),
      math = math, string = string, ipairs = ipairs },
    { __index = _G })
local chunk
if _VERSION == "Lua 5.1" then
    chunk = assert(loadstring(ma, "warm"))
    setfenv(chunk, moi_truong)
else
    chunk = assert(load(ma, "warm", "t", moi_truong))
end
chunk()

-- ------------------------------------------------------------------- bai kiem
local function anhGia(n, treKieu)
    local ds = {}
    for k = 1, n do
        ds[k] = {
            requestJpegThumbnail = function(_, _, _, cb)
                if treKieu == "hong" then error("gia vo hong") end
                if treKieu == "im" and k % 7 == 0 then return end   -- khong bao gio goi cb
                hangDoi[#hangDoi+1] = { khi = GIO + 0.1, fn = cb, dulieu = "JPEGDATA" }
            end
        }
    end
    return ds
end

-- ---------------------------------------------- phep kiem QUAN TRONG NHAT
--[[ Ngay 6/9 luot "dung san preview" tung nam TRONG applyJob va lam hong ca
     duong ap thong so: requestJpegThumbnail khong bao gio goi callback, moi lo
     cho du 20 giay, job 1030 anh ket o .running va Lightroom khong nhan duoc gi.
     Da go ra. Phep kiem nay canh khong cho ai dat lai vao. ]]
local loi = {}
do
    local a = nguon:find("function M.applyJob", 1, true)
    local b = nguon:find("\nfunction M%.", a + 10)
    local than = nguon:sub(a, b or #nguon)
    --[[ Tim LOI GOI that (co dau mo ngoac), khong phai chu "M.warmPreviews"
         nam trong dong ghi chu giai thich vi sao da go no ra. ]]
    if than:find("M.warmPreviews(", 1, true) then
        loi[#loi+1] = "applyJob GOI LAI warmPreviews - da tung lam ket ca hang doi job"
    else
        print(string.format("  %-38s %s", "applyJob khong goi warmPreviews",
                            "dung - luot 4 van o ngoai duong ap"))
    end
    if not nguon:find("PREVIEW_CANH  = 0", 1, true) then
        loi[#loi+1] = "PREVIEW_CANH khac 0 - luot dung preview dang BAT"
    else
        print(string.format("  %-38s %s", "PREVIEW_CANH = 0", "dang tat"))
    end
end
local function ktra(ten, dieuKien, mo)
    if not dieuKien then loi[#loi+1] = ten .. ": " .. mo
    else print(string.format("  %-38s %s", ten, mo)) end
end

-- 1. binh thuong: moi callback deu ve
batDauGio()
local r = M.warmPreviews(anhGia(25))
ktra("25 anh, callback deu ve", r.xong == 25 and r.loi == 0,
     string.format("xong=%d loi=%d", r.xong, r.loi))

-- 2. co anh khong bao gio goi callback -> phai het gio roi DI TIEP
batDauGio()
r = M.warmPreviews(anhGia(21, "im"))
ktra("co anh cam lang -> khong treo", r.xong + r.loi == 21 and r.loi >= 3,
     string.format("xong=%d loi=%d (khong ket dung)", r.xong, r.loi))

-- 3. SDK nem loi -> dem vao loi, khong treo, khong vo
batDauGio()
r = M.warmPreviews(anhGia(10, "hong"))
ktra("SDK nem loi -> dem loi, khong vo", r.xong == 0 and r.loi == 10,
     string.format("xong=%d loi=%d", r.xong, r.loi))

-- 4. danh sach rong
batDauGio()
r = M.warmPreviews({})
ktra("danh sach rong", r.xong == 0 and r.loi == 0, "khong lam gi")

-- 5. tien do goi du
batDauGio()
local moc = {}
r = M.warmPreviews(anhGia(20), function(d, t) moc[#moc+1] = d .. "/" .. t end)
ktra("bao tien do theo lo", #moc == math.ceil(20/8) and moc[#moc] == "20/20",
     table.concat(moc, " "))

print()
if #loi == 0 then print("TAT CA DAT")
else for _, m in ipairs(loi) do print("  [!] " .. m) end
     print(#loi .. " LOI") end
os.exit(#loi == 0 and 0 or 1)
