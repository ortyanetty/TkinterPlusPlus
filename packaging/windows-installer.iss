; Build with scripts/build_installer.ps1 after building the portable executable.
#ifndef AppVersion
  #define AppVersion "0.4.0"
#endif
#define AppExe "TkinterPlusPlus.exe"

[Setup]
AppId={{9273D4AC-62C8-47A6-A37F-5352BD06F83E}
AppName=Tkinter++
AppVersion={#AppVersion}
AppPublisher=ortyanetty
AppPublisherURL=https://github.com/ortyanetty/TkinterPlusPlus
AppSupportURL=https://github.com/ortyanetty/TkinterPlusPlus/issues
AppUpdatesURL=https://github.com/ortyanetty/TkinterPlusPlus/releases
DefaultDirName={localappdata}\Programs\TkinterPlusPlus
DefaultGroupName=Tkinter++
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=..\dist
OutputBaseFilename=TkinterPlusPlus-{#AppVersion}-setup-windows-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern dynamic windows11
LicenseFile=..\LICENSE
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\TkinterPlusPlus-{#AppVersion}-windows-x64.exe"; DestDir: "{app}"; DestName: "{#AppExe}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\library-guide.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\Tkinter++"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\Руководство по библиотеке"; Filename: "https://github.com/ortyanetty/TkinterPlusPlus/blob/v{#AppVersion}/docs/library-guide.md"
Name: "{autodesktop}\Tkinter++"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,Tkinter++}"; Flags: nowait postinstall skipifsilent
