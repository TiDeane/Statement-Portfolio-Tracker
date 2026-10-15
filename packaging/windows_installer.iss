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

[InstallDelete]
; Remove the previous version's libraries before copying the new ones. Files a newer build no
; longer has would otherwise stay behind and be found by the new one: a leftover half of numpy,
; from a build that still had it, made openpyxl fail to load. The folder holds only the program;
; settings and saved prices are kept in the user's settings folder, elsewhere.
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
; What the app saved for the user: settings.json (listings, names, spreadsheet choice) and
; last_prices.json (last prices, values entered). Must match statement_tracker.settings.APP_FOLDER
; under platformdirs' local (not roaming) folder. Installing over an older version does not run
; the uninstaller, so upgrades keep it. Spreadsheets and their backups are the user's and stay.
Type: filesandordirs; Name: "{localappdata}\StatementPortfolioTracker"

[Files]
Source: "..\dist\StatementPortfolioTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
