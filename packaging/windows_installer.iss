; Inno Setup script: per-user installer (no administrator rights needed).
; Build after PyInstaller, from the repo root:
;   iscc /DAppVersion=0.0.1 packaging\windows_installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Statement Portfolio Tracker"
#define AppExe "StatementPortfolioTracker.exe"
#define AppUrl "https://github.com/TiDeane/Statement-Portfolio-Tracker"

[Setup]
; Never change AppId: Windows uses it to recognise upgrades of the same app.
AppId={{DA922E75-DDD4-487E-9D38-86D92494ECAE}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName} contributors
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=StatementPortfolioTracker-{#AppVersion}-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\StatementPortfolioTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
