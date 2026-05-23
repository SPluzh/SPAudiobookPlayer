; ============================================================
;  Inno Setup Script — SPAudiobookPlayer
; ============================================================

#define AppName      "SP Audiobook Player"
#ifndef AppVersion
  #define AppVersion   "1.0.0"          ; This will be overridden by the command line (/DAppVersion=X.X.X)
#endif
#define AppPublisher "SPluzh"
#define AppExeName   "SP Audiobook Player.exe"
#define SourceDir    "dist\SP Audiobook Player"

[Setup]
; -- Application Metadata --
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppId={{022C0FE7-5D0A-4A0A-A78A-34D285A18FAB}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup

; -- Installation Directory --
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; -- Output Directory and Filename --
OutputDir=.
OutputBaseFilename=SP_Audiobook_Player_Setup_v{#AppVersion}

; -- Compression Settings --
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=ultra64

; -- Installation Privilege Level --
; lowest: User-level installation (does not require administrator rights)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; -- Architecture Support --
ArchitecturesInstallIn64BitMode=x64compatible

; -- Modern Wizard Style --
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
; -- Desktop Shortcut Task --
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

; -- Start Menu Shortcut Task --
Name: "startmenuicon"; Description: "{cm:CreateStartMenuIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; -- Main Application Directory and Internal Dependencies --
; We exclude settings.ini, internal executable files, and data directories just like in the zip release.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "_internal\*.exe,settings.ini,data,data\*,_internal\data,_internal\data\*"

[Icons]
; -- Start Menu Shortcuts --
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"; Tasks: startmenuicon

; -- Desktop Shortcut --
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[CustomMessages]
english.CreateStartMenuIcon=Create a Start Menu shortcut
russian.CreateStartMenuIcon=Создать ярлык в меню Пуск
arabic.CreateStartMenuIcon=إنشاء اختصار في قائمة ابدأ
german.CreateStartMenuIcon=Verknüpfung im Startmenü erstellen
spanish.CreateStartMenuIcon=Crear un acceso directo en el menú Inicio
french.CreateStartMenuIcon=Créer un raccourci dans le menu Démarrer
japanese.CreateStartMenuIcon=スタートメニューにショートカットを作成する
korean.CreateStartMenuIcon=시작 메뉴에 바로 가기 만들기
portuguese.CreateStartMenuIcon=Criar um atalho no menu Iniciar
thai.CreateStartMenuIcon=สร้างทางลัดในเมนูเริ่ม
turkish.CreateStartMenuIcon=Başlat menüsünde bir kısayol oluştur
