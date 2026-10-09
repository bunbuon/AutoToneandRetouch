; installer_win.iss — Inno Setup script đóng dist\AutoTone (onedir) thành Setup.exe
;
; VÌ SAO: người dùng muốn MỘT file cài đặt, không phải thư mục/zip. Setup.exe
; cài app vào Program Files, tạo shortcut Start Menu + Desktop, gắn icon, và có
; trình gỡ cài đặt — chuẩn Windows.
;
; THAM SỐ (truyền qua ISCC /D..., nên đổi tên/icon KHÔNG phải sửa file này):
;   /DTenApp="AutoTone"            tên hiển thị (shortcut, Add/Remove Programs)
;   /DPhienBan="2026.10.04"        phiên bản (Add/Remove Programs)
;   /DNguon="F:\...\dist\AutoTone" thư mục gói onedir (bắt buộc)
;   /DExe="AutoTone.exe"           tên file chạy trong gói
;   /DIcon="F:\...\icon.ico"       (tuỳ chọn) icon cho shortcut + Setup
;   /DRaDir="F:\...\dist"          thư mục xuất Setup.exe
;   /DPublisher="SAY MEDIA"        nhà phát hành
;
; DÙNG: xem dong_installer.py — nó dò ISCC.exe và truyền sẵn các tham số này.

#ifndef TenApp
  #define TenApp "AutoTone"
#endif
#ifndef PhienBan
  #define PhienBan "1.0"
#endif
#ifndef Exe
  #define Exe "AutoTone.exe"
#endif
#ifndef Publisher
  #define Publisher "SAY MEDIA"
#endif
#ifndef RaDir
  #define RaDir "."
#endif
; Nguon BAT BUOC — khong co thi bao loi ro.
#ifndef Nguon
  #error "Thieu /DNguon=<thu muc goi onedir>. Vi du: /DNguon=dist\AutoTone"
#endif

[Setup]
AppId={{B7A9E3C1-5A4D-4E2F-9B8C-AUTOTONE-SAYMEDIA}
AppName={#TenApp}
AppVersion={#PhienBan}
AppPublisher={#Publisher}
; TenFile = ten AN TOAN cho thu muc/ten file (khong co & / ky tu la). Mac dinh
; = TenApp neu khong truyen. Dung cho DefaultDirName + ten Setup.exe de tranh
; thu muc "Program Files\A&B" va file "A&B-Setup.exe" gay roi shell/URL.
#ifndef TenFile
  #define TenFile TenApp
#endif
; Cai vao Program Files\<TenFile>. {autopf} = Program Files dung bit may.
DefaultDirName={autopf}\{#TenFile}
DefaultGroupName={#TenApp}
; Khong bat chon thu muc (gon cho nguoi dung cuoi); bo dong nay neu muon cho chon.
DisableProgramGroupPage=yes
OutputDir={#RaDir}
OutputBaseFilename={#TenFile}-Setup
; NEN BANG ZIP (zlib) — KHONG dung islzma.
;
; VI SAO KHONG lzma/lzma2: islzma.dll cua Inno 6.7.3 SAP (Access violation)
; KHONG ON DINH tren may build nay — khong chi o model ma hoa (entropy cao) ma
; CA o AutoTone.exe (file PE thuong). Da gap: lan thi nen tron (v8 ra 1 GB), lan
; thi sap ngay file dau. Day la crash CHOP CHON (giong 0xC0000005 o PyInstaller/
; MSVC tren may nay), khong sua bang doi tham so lzma duoc.
;
; zip/9 dung ZLIB — trinh nen RIENG, on dinh, khong dung islzma -> KHONG sap.
; Nen kem lzma mot chut (torch_cpu.dll ~500 MB nen ~60% thay vi ~50%), Setup.exe
; to hon chut nhung CHAC CHAN build ra. Van bo cay mo_hinh (model ma hoa, entropy
; cao khong nen them duoc) o [Files] voi nocompression. KHONG SolidCompression
; (solid ep zlib giu ca stream trong RAM — khong can, va de loi hon).
Compression=zip/9
; 64-bit: app PyInstaller la x64.
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
; Cho phep cai khong can quyen admin neu nguoi dung chon (vao thu muc user);
; mac dinh admin de vao Program Files. "lowest" + dir Program Files se tu xin UAC.
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
#ifdef Icon
SetupIconFile={#Icon}
UninstallDisplayIcon={app}\{#Exe}
#else
UninstallDisplayIcon={app}\{#Exe}
#endif

[Languages]
; Default.isl (English) co san moi may build. Tieng Viet (Vietnamese.isl) KHONG
; nam trong ban Inno mac dinh — phai tai rieng va bo vao Languages\. Neu muon
; giao dien cai tieng Viet, tai Vietnamese.isl roi doi dong duoi.
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Chep TOAN BO goi onedir vao {app}, TRU cay _internal\mo_hinh (model ma hoa) —
; cai do chep rieng ben duoi voi nocompression de khong lam sap islzma.
;   recursesubdirs + createallsubdirs: giu nguyen cay thu muc _internal.
;   Excludes: bo cay mo_hinh khoi lan chep NEN nay (chep lai o dong sau).
Source: "{#Nguon}\*"; DestDir: "{app}"; Excludes: "_internal\mo_hinh\*"; \
  Flags: recursesubdirs createallsubdirs ignoreversion
; Model DA MA HOA: entropy cao, LZMA vua vo ich vua lam islzma SAP. Chep khong
; nen (nocompression), van giu cay con (insightface/, liquify/).
Source: "{#Nguon}\_internal\mo_hinh\*"; DestDir: "{app}\_internal\mo_hinh"; \
  Flags: recursesubdirs createallsubdirs ignoreversion nocompression

[Icons]
; Shortcut Start Menu + (tuy chon) Desktop, tro vao exe trong {app}.
Name: "{group}\{#TenApp}"; Filename: "{app}\{#Exe}"
Name: "{group}\Gỡ cài đặt {#TenApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#TenApp}"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[UninstallDelete]
; 9/10: app tu chep plugin vao thu muc Modules cua Lightroom (Lightroom tu nap
; plugin o do, khong can Plug-in Manager → Add — xem duong_dan.cai_vao_modules).
; Go app thi go luon ban do, khong de Lightroom nap mot plugin khong con app.
Type: filesandordirs; Name: "{userappdata}\Adobe\Lightroom\Modules\AutoTone.lrplugin"

[Run]
; Hoi mo app ngay sau khi cai xong.
; Mo QUA explorer.exe, KHONG chay thang {app}\{#Exe}: Inno Setup 6.5+ bat
; RedirectionGuard cho tien trinh Setup va app chay thang tu Setup KE THUA no
; (ca tien trinh con) -> khong di qua junction do nguoi dung tao (vd
; ~/.insightface tro sang o khac) -> WinError 448, retouch "khong thay khuon mat
; nao" (6/10). explorer.exe giao viec mo cho shell dang chay -> app sach guard.
Filename: "{win}\explorer.exe"; Parameters: """{app}\{#Exe}"""; Description: "{cm:LaunchProgram,{#TenApp}}"; Flags: nowait postinstall skipifsilent runasoriginaluser
