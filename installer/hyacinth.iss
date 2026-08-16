; 风信子（Hyacinth）Windows 安装包脚本
;
; 编译（推荐用一键脚本，版本号自动取自 pyproject.toml）：
;   powershell -NoProfile -ExecutionPolicy Bypass -File installer\build_installer.ps1
; 手动编译（需自行传入版本号）：
;   ISCC.exe /DMyAppVersion=0.1.0 installer\hyacinth.iss
;
; 产物：installer\Output\Hyacinth-Setup-<版本>.exe
; 特性：中文向导、可选择安装目录（支持“仅我/所有用户”）、开始菜单 +
;       可勾选桌面快捷方式、安装完成直接启动、自带卸载程序。

#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif

#define MyAppNameZh "风信子"
#define MyAppNameEn "Hyacinth"
#define MyAppExeName "Hyacinth.exe"
#define MyAppPublisher "Hyacinth Project"

[Setup]
; AppId 固定不变，升级安装才能正确覆盖同一应用
AppId={{8F6C2E94-3D57-4A81-B9C6-7E2A1F5B4D38}
AppName={#MyAppNameZh} {#MyAppNameEn}
AppVersion={#MyAppVersion}
AppVerName={#MyAppNameZh} {#MyAppNameEn} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppNameZh} {#MyAppNameEn}
; 启动时询问“仅为我安装（免管理员）还是为所有用户安装”，目录随选择自适应
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; 用户可在向导中自由更换安装目录与开始菜单组名
DisableDirPage=no
DisableProgramGroupPage=no
UninstallDisplayName={#MyAppNameZh} {#MyAppNameEn}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=Hyacinth-Setup-{#MyAppVersion}
SetupIconFile=..\src\hyacinth\assets\app-icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Hyacinth\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppNameZh} {#MyAppNameEn}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppNameZh} {#MyAppNameEn}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppNameZh} {#MyAppNameEn}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppNameZh} {#MyAppNameEn}}"; Flags: nowait postinstall skipifsilent

; 注意：用户文件库位于 文档\Hyacinth，卸载绝不触碰，故无 [UninstallDelete]
