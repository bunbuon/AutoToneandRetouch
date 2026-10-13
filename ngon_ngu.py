"""Ngôn ngữ giao diện: Tiếng Việt (mã nguồn) / English — 13/10.

User 13/10: "chắc sẽ cần làm thêm 1 bản ngôn ngữ tiếng anh. Mặc định sẽ là tiếng anh
khi cài app lần đầu. Trong setting sẽ cho chọn ngôn ngữ".

CÁCH LÀM — DỊCH LÚC HIỂN THỊ, KHÔNG SỬA TỪNG CHỖ GỌI
  ~1.800 câu chữ tiếng Việt rải trên ~30 module, nhiều câu vừa là chữ hiển thị
  vừa là khoá nội bộ (nhãn ô chọn, lý do "không ghi" của ô lưới…). Bọc từng chuỗi
  bằng _() là hàng nghìn chỗ sửa và dễ làm hỏng logic so chuỗi. Nên: mã nguồn GIỮ
  tiếng Việt; khi ngôn ngữ là English, các móc (cai_moc) dịch ĐÚNG LÚC Tk nhận chữ:
    · tkinter.Misc._options — mọi text= / label= / title= của widget Tk / ttk, mục
      menu, chữ vẽ trên Canvas (create_text / itemconfigure);
    · tkinter.font.Font.measure — widget tự vẽ (NutTron, PhanDoan…) đo bề ngang
      bằng CHÍNH câu tiếng Anh sẽ vẽ, không bị cắt chữ;
    · Wm.title, messagebox, Text.insert, ttk.Treeview (insert / item / heading).
  Từ điển: ngon_ngu_en.py (TU_DIEN: câu Việt -> câu Anh; "{}" = chỗ trống của
  f-string). Tra: nguyên câu -> mẫu có chỗ trống (regex) -> thay từng cụm đã biết
  (bỏ qua đoạn trông như đường dẫn / tên file). Câu không có dấu tiếng Việt thì
  để nguyên — dịch hai lần vô hại.

CHỌN NGÔN NGỮ (thanh_luoi kv "ngon_ngu"): chưa chọn -> chạy mã nguồn = "vi" (bài kiểm
dựa trên chữ tiếng Việt); bản cài mà thư mục dữ liệu CHƯA có gì của app (cài lần
đầu) = "en"; máy đã dùng app trước đó = "vi". AUTOTONE_NGON_NGU ép (vi / en).
Đổi ngôn ngữ cần mở lại app (bảng nhãn dựng một lần lúc mở).
"""
from __future__ import annotations

import os
import re
import sys

KHOA_KV = "ngon_ngu"
DS = (("en", "English"), ("vi", "Tiếng Việt"))

VN = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
                re.I)
#  đoạn KHÔNG dịch trong lúc thay từng cụm: đường dẫn, tên file
_KHONG_DICH = re.compile(r"([A-Za-z]:[\\/][^\n·—|]*|\\\\[^\n·—|]*|/(?:Users|Volumes)/[^\n·—|]*"
                         r"|[\w\-. ]+\.(?:ARW|NEF|CR2|CR3|RAF|DNG|ORF|RW2|jpg|jpeg|JPG|xmp|tsv|"
                         r"json|lrcat|png|log|txt))")

_NGON_NGU: list = []
_TU: dict = {}
_MAU: list = []
_CUM = None
_CUM_TU: dict = {}             # cụm đã cắt khoảng trắng -> tiếng Anh đã cắt
#  chữ tiếng Việt KHÔNG DẤU trên giao diện (bộ lọc chỉ nhận ra tiếng Việt qua dấu)
_KHONG_DAU = {"Chung": "All", "Nam": "Male", "Nhanh": "Fast", "Da": "Skin", "DA": "SKIN",
              "Sau": "After", "Ra": "Output", "Vao": "Input", "Xem to": "View large",
              "HSL da": "Skin HSL", "Mo": "Open", "Dung": "Stop"}
_CUM_THEM = {"nhịp cuối": "last heartbeat", "ngày trước": "days ago", "giờ trước": "hours ago",
             "phút trước": "minutes ago", "giây trước": "seconds ago", "ảnh": "photos",
             "cảnh": "scenes", "buổi": "session", "ngày": "days", "giờ": "hours", "phút": "min",
             "giây": "s", "tấm": "photos", "lỗi": "errors", "còn": "left", "tháng": "months",
             "năm": "years"}
_DEM: dict = {}
_DA_MOC: list = []


# ---------------------------------------------------------------- chọn ngôn ngữ
def ngon_ngu() -> str:
    """"vi" hoặc "en" — quyết MỘT lần cho cả lần chạy app."""
    if not _NGON_NGU:
        _NGON_NGU.append(_quyet())
    return _NGON_NGU[0]


def la_en() -> bool:
    return ngon_ngu() == "en"


def _quyet() -> str:
    ep = (os.environ.get("AUTOTONE_NGON_NGU") or "").strip().lower()
    if ep in ("vi", "en"):
        return ep
    try:
        import thanh_luoi
        v = thanh_luoi.doc_kv(KHOA_KV)
    except Exception:                                        # noqa: BLE001
        thanh_luoi, v = None, None
    if v in ("vi", "en"):
        return v
    if not getattr(sys, "frozen", False):
        return "vi"
    try:
        import duong_dan as dd
        goc = dd.goc_du_lieu()
        da_dung = any((goc / x).exists() for x in
                      ("phan_tich", "anh_nho", "trang_thai", "xem_raw", "retouch_anh"))
    except Exception:                                        # noqa: BLE001
        da_dung = True
    v = "vi" if da_dung else "en"
    if thanh_luoi is not None:
        try:
            thanh_luoi.ghi_kv(KHOA_KV, v)
        except Exception:                                    # noqa: BLE001
            pass
    return v


def dat(ma: str) -> None:
    """Ghi lựa chọn ngôn ngữ (áp dụng ở lần mở app sau)."""
    if ma not in ("vi", "en"):
        return
    try:
        import thanh_luoi
        thanh_luoi.ghi_kv(KHOA_KV, ma)
    except Exception:                                        # noqa: BLE001
        pass


def da_chon() -> str:
    """Ngôn ngữ đã chọn cho lần mở sau (có thể khác lần chạy này)."""
    try:
        import thanh_luoi
        v = thanh_luoi.doc_kv(KHOA_KV)
    except Exception:                                        # noqa: BLE001
        v = None
    return v if v in ("vi", "en") else ngon_ngu()


# ---------------------------------------------------------------- từ điển
def _bo_thoat(s: str) -> str:
    return s.replace("{{", "{").replace("}}", "}")


def _nap():
    if _TU or _MAU:
        return
    try:
        from ngon_ngu_en import TU_DIEN
    except Exception:                                        # noqa: BLE001
        TU_DIEN = {}
    cum = []
    for vi, en in TU_DIEN.items():
        if not isinstance(vi, str) or not isinstance(en, str) or not en:
            continue
        if "{}" in vi.replace("{{", "").replace("}}", ""):
            pv = [_bo_thoat(x) for x in vi.split("{}")]
            pe = [_bo_thoat(x) for x in en.split("{}")]
            if len(pv) != len(pe):
                continue
            nghia = sum(len(x.strip()) for x in pv)
            if nghia < 3:
                continue
            #  so trên câu ĐÃ CẮT khoảng trắng hai đầu (mẫu "Buổi {} chưa gửi lần
            #  nào. " ghép với câu sau, khi tách câu thì mất dấu cách cuối)
            pv[0], pv[-1] = pv[0].lstrip(), pv[-1].rstrip()
            pe[0], pe[-1] = pe[0].lstrip(), pe[-1].rstrip()
            rx = re.compile("^" + "(.+?)".join(re.escape(x) for x in pv) + "$", re.S)
            #  lọc nhanh trước khi chạy regex: tiền tố, hậu tố, đoạn chữ dài nhất
            dai = max(pv, key=lambda x: len(x.strip())).strip()
            _MAU.append((nghia, rx, pe, pv[0], pv[-1], dai, sum(len(x) for x in pv)))
        else:
            v, e = _bo_thoat(vi), _bo_thoat(en)
            _TU[v] = e
            if "\n" in v and v.count("\n") == e.count("\n"):
                for lv, le in zip(v.split("\n"), e.split("\n")):
                    if lv.strip() and VN.search(lv):
                        _DONG.setdefault(lv.strip(), le.strip())
            if len(v.strip()) >= 3 and VN.search(v):
                cum.append(v.strip())
                _CUM_TU[v.strip()] = e.strip()
    #  từ đơn vị hay gặp trong câu ghép lúc chạy ("9.3 ngày trước", "221 ảnh")
    for v, e in _CUM_THEM.items():
        if v not in _CUM_TU:
            _CUM_TU[v] = e
            cum.append(v)
    _MAU.sort(key=lambda x: -x[0])
    global _CUM
    cum = sorted(set(cum), key=len, reverse=True)
    if cum:
        #  không thay BÊN TRONG chữ khác ("cảnh" chứa "ảnh")
        _CUM = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(x) for x in cum) + r")(?!\w)")


def _tra_nguyen(x: str) -> str:
    """Chỗ trống của mẫu: CHỈ tra nguyên câu (không đệ quy vào mẫu — 13/10 một câu
    nhiều dấu · đệ quy qua 588 mẫu mất 2 phút)."""
    r = _TU.get(x)
    if r is None:
        g = x.strip()
        if g != x and g in _TU:
            r = x[:len(x) - len(x.lstrip())] + _TU[g] + x[len(x.rstrip()):]
    return x if r is None else r


def _dich_mau(s0: str):
    s = s0.strip()
    lead, trail = s0[:len(s0) - len(s0.lstrip())], s0[len(s0.rstrip()):]
    for _n, rx, pe, dau, duoi, dai, phu in _MAU:
        if (dau and not s.startswith(dau)) or (duoi and not s.endswith(duoi)) \
                or (dai and dai not in s):
            continue
        m = rx.match(s)
        if m:
            g = [_tra_nguyen(x) for x in m.groups()]
            #  mẫu QUÁ CHUNG ("Buổi {}") nuốt cả câu ghép: phần chữ cố định của mẫu
            #  ít (< 40% câu) mà chỗ trống còn CỤM tiếng Việt nhiều chữ (không tính
            #  đường dẫn / tên file) -> bỏ mẫu này, để bước tách câu lo.
            con_vn = [x for x in g if VN.search(_KHONG_DICH.sub("", x))
                      and len(_KHONG_DICH.sub("", x).split()) > 1]
            if con_vn and phu < 0.4 * len(s):
                continue
            #  chỗ trống còn tiếng Việt (vd. "10 tháng 0 ngày") -> thay từng cụm
            g = [_thay_cum(x) if VN.search(x) else x for x in g]
            out = pe[0]
            for i, x in enumerate(g):
                out += x + pe[i + 1]
            return lead + out + trail
    return None


_TACH = re.compile(r"(\s+·\s+|\s+—\s+|(?<=[.!?:;])\s+|\s+\|\s+)")


def _ghep(s: str):
    """Câu GHÉP lúc chạy ("A · B", "Câu 1. Câu 2", hay một f-string có trong từ điển
    rồi bị nối thêm đoạn sau): thử các DÃY mảnh liền nhau — dài nhất trước — bằng
    nguyên câu / mẫu, giữ dấu nối. None nếu không dãy nào dịch được."""
    phan = _TACH.split(s)
    tu, noi = phan[0::2], phan[1::2]
    n = len(tu)
    if n < 2 or n > 24:
        return None
    ra, i, doi = [], 0, False
    while i < n:
        thay = None
        for j in range(n - 1, i - 1, -1):
            seg = tu[i] + "".join(noi[k] + tu[k + 1] for k in range(i, j))
            if not seg or not VN.search(seg):
                continue
            r = _tra_nguyen(seg)
            if r == seg:
                r = _dich_mau(seg)
            if r and r != seg:
                thay = (j, r)
                break
        if thay:
            j, r = thay
            ra.append(r)
            doi = True
        else:
            j = i
            ra.append(tu[i])
        if j < n - 1:
            ra.append(noi[j])
        i = j + 1
    return "".join(ra) if doi else None


def _thay_cum(s: str) -> str:
    if _CUM is None:
        return s
    ra, i = [], 0
    for m in _KHONG_DICH.finditer(s):
        ra.append(_CUM.sub(lambda mm: _CUM_TU.get(mm.group(0), mm.group(0)), s[i:m.start()]))
        ra.append(m.group(0))
        i = m.end()
    ra.append(_CUM.sub(lambda mm: _CUM_TU.get(mm.group(0), mm.group(0)), s[i:]))
    return "".join(ra)


def t(s, chat: bool = False):
    """Dịch một chuỗi hiển thị (English); tiếng Việt / không phải chuỗi -> nguyên.
    chat=True: chỉ nguyên câu / mẫu, không thay từng cụm (log, bảng số)."""
    if not isinstance(s, str) or not s or not la_en():
        return s
    if not VN.search(s):
        return _KHONG_DAU.get(s, s)
    k = (s, chat)
    r = _DEM.get(k)
    if r is not None:
        return r
    _nap()
    r = _TU.get(s)
    if r is None:
        g = s.strip()
        if g != s and g in _TU:
            dau = s[:len(s) - len(s.lstrip())]
            duoi = s[len(s.rstrip()):]
            r = dau + _TU[g] + duoi
        elif g in _DONG:
            #  một DÒNG của câu nhiều dòng trong từ điển (nhãn tách tiêu đề / thân)
            r = s[:len(s) - len(s.lstrip())] + _DONG[g] + s[len(s.rstrip()):]
    if r is None and "\n" in s:
        dong = s.split("\n")
        if len(dong) > 1:
            dd = [t(x, chat=True) if x.strip() else x for x in dong]
            if any(a != b for a, b in zip(dd, dong)):
                r = "\n".join(dd)
                if VN.search(r) and not chat:
                    r = _thay_cum(r)
    if r is None and s.isupper() and len(s) < 40:
        #  tiêu đề in hoa ("MẮT", "CƠ THỂ") — từ điển có dạng thường
        _nap_hoa()
        e = _HOA.get(s.strip())
        if e is not None:
            r = s[:len(s) - len(s.lstrip())] + e.upper() + s[len(s.rstrip()):]
    if r is None:
        r = _dich_mau(s)
    if r is None:
        r = _ghep(s)
        if r is not None and not chat and VN.search(r):
            r = _thay_cum(r)
    if r is None:
        r = s if chat else _thay_cum(s)
    if len(_DEM) > 20000:
        _DEM.clear()
    _DEM[k] = r
    return r


_HOA: dict = {}
_DONG: dict = {}               # một dòng của câu nhiều dòng -> dòng tiếng Anh tương ứng


def _nap_hoa():
    if not _HOA:
        for k, v in _TU.items():
            if len(k) < 40:
                _HOA.setdefault(k.strip().upper(), v.strip())
        _HOA["_"] = "_"


def dich_bang(bang: list) -> list:
    """[(nhãn, mã), …] -> nhãn đã dịch (mã giữ nguyên) — bảng ô chọn mà giá trị biến
    chính là nhãn (MODES, METERS…). Dịch Ở NGUỒN để nhãn hiện ra và nhãn đem tra
    dict(bảng) là một."""
    if not la_en():
        return bang
    return [(t(a), *rest) for a, *rest in bang]


# ---------------------------------------------------------------- móc vào Tk
def cai_moc() -> None:
    """Gắn các móc dịch (chỉ khi English). Gọi trước khi dựng cửa sổ."""
    if not la_en() or _DA_MOC:
        return
    _DA_MOC.append(True)
    _nap()
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import messagebox, ttk

    goc_options = tk.Misc._options

    def _options(self, cnf, kw=None):
        def dich(d):
            if isinstance(d, dict) and any(k in d for k in ("text", "label", "title")):
                d = dict(d)
                for k in ("text", "label", "title"):
                    if isinstance(d.get(k), str):
                        d[k] = t(d[k])
            return d
        return goc_options(self, dich(cnf), dich(kw))
    tk.Misc._options = _options

    goc_measure = tkfont.Font.measure

    def measure(self, text, displayof=None):
        return goc_measure(self, t(text) if isinstance(text, str) else text, displayof)
    tkfont.Font.measure = measure

    goc_title = tk.Wm.wm_title

    def wm_title(self, string=None):
        return goc_title(self, t(string) if isinstance(string, str) else string)
    tk.Wm.wm_title = wm_title
    tk.Wm.title = wm_title

    goc_show = messagebox._show

    def _show(title=None, message=None, _icon=None, _type=None, **options):
        if "detail" in options and isinstance(options["detail"], str):
            options["detail"] = t(options["detail"])
        return goc_show(t(title) if isinstance(title, str) else title,
                        t(message) if isinstance(message, str) else message,
                        _icon, _type, **options)
    messagebox._show = _show

    goc_insert = tk.Text.insert

    def text_insert(self, index, chars, *args):
        return goc_insert(self, index, t(chars, chat=True) if isinstance(chars, str) else chars,
                          *args)
    tk.Text.insert = text_insert

    def _kw_cay(kw):
        if "text" in kw and isinstance(kw["text"], str):
            kw["text"] = t(kw["text"], chat=True)
        if "values" in kw and isinstance(kw["values"], (list, tuple)):
            kw["values"] = [t(v, chat=True) if isinstance(v, str) else v for v in kw["values"]]
        return kw

    goc_tv_insert = ttk.Treeview.insert

    def tv_insert(self, parent, index, iid=None, **kw):
        return goc_tv_insert(self, parent, index, iid, **_kw_cay(kw))
    ttk.Treeview.insert = tv_insert

    goc_tv_item = ttk.Treeview.item

    def tv_item(self, item, option=None, **kw):
        return goc_tv_item(self, item, option, **_kw_cay(kw))
    ttk.Treeview.item = tv_item

    goc_tv_heading = ttk.Treeview.heading

    def tv_heading(self, column, option=None, **kw):
        return goc_tv_heading(self, column, option, **_kw_cay(kw))
    ttk.Treeview.heading = tv_heading
