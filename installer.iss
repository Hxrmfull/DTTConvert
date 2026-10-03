; Установщик DTTConvert для Windows (Inno Setup 6).
;
; Собирается из папки dist\<вариант>\DTTConvert, которую готовит
; build_windows.ps1, — вызывать его напрямую не нужно:
;
;   .\build_windows.ps1 -Installer
;
; Версия и вариант сборки приходят из скрипта ключами /DAppVersion и
; /DVariant: так номер версии берётся из app_info.py и не расходится
; с заголовком окна.
;
; Вариантов два, как у архивов: with-ffmpeg — с вшитым FFmpeg, without-ffmpeg —
; для тех, у кого FFmpeg уже установлен. AppId у них общий: это одна
; программа, и один вариант ставится поверх другого, а не рядом.
;
; Ставится по умолчанию для одного пользователя (без запроса прав
; администратора) в %LOCALAPPDATA%\Programs. Кто хочет для всех — выбирает
; это в первом окне установщика.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Variant
  #define Variant "with-ffmpeg"
#endif

#define AppName "DTTConvert"
#define AppExe "DTTConvert.exe"
#define AppUrl "https://github.com/Hxrmfull/DTTConvert"
#define SourceDir "dist\" + Variant + "\" + AppName

[Setup]
; Постоянный идентификатор: по нему новая версия ставится поверх старой,
; а не рядом. Менять нельзя.
AppId={{5B7C1E8A-3F4D-4C2B-9A61-0D8E2F7B4C13}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename={#AppName}-{#AppVersion}-windows-x64-{#Variant}-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Программа может быть запущена во время обновления — предлагаем закрыть.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
