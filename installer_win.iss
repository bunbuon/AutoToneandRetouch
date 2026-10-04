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
; KHONG NEN (Compression=none).
;
; VI SAO: islzma.dll cua Inno 6.7.3 SAP (Access violation) khi nen file model
; DA MA HOA — model ma hoa la du lieu entropy cao, LZMA ep len no vua vo ich
; (khong nen duoc them) vua kich hoat bug trong islzma. Da thu lzma2/max va
; lzma2/normal 1 luong: deu sap o dung file mo_hinh/*.pt.
;
; Gia: Setup.exe to hon (~800 MB thay vi nen). Doi lai: build khong sap, cai
; nhanh (khong giai nen), va goi von da gon (torch tai sau, model da ma hoa).
Compression=none
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
; Chep TOAN BO thu muc goi onedir (exe + _internal + moi thu) vao {app}.
; recursesubdirs + createallsubdirs: giu nguyen cay thu muc _internal.
Source: "{#Nguon}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Shortcut Start Menu + (tuy chon) Desktop, tro vao exe trong {app}.
Name: "{group}\{#TenApp}"; Filename: "{app}\{#Exe}"
Name: "{group}\Gỡ cài đặt {#TenApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#TenApp}"; Filename: "{app}\{#Exe}"; Tasks: desktopicon

[Run]
; Hoi mo app ngay sau khi cai xong.
Filename: "{app}\{#Exe}"; Description: "{cm:LaunchProgram,{#TenApp}}"; Flags: nowait postinstall skipifsilent
