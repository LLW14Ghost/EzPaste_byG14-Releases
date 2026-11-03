; EzPaste installer (Inno Setup 6). Same AppId as v0.1.7 / v0.1.8: updates replace the files in the
; existing folder and leave the data files next to EzPaste.exe alone. NEVER change the AppId.
;
; GitHub Actions passes the version and the PyInstaller folder:
;   ISCC /DMyAppVersion=0.1.9 /DDistDir=<repo>\dist\EzPaste installer\EzPaste.iss
; Building by hand from the repo folder works with the defaults below (after PyInstaller made dist\EzPaste).

#define MyAppName "EzPaste"
#ifndef MyAppVersion
  #define MyAppVersion "0.1.9"
#endif
#ifndef DistDir
  #define DistDir "..\dist\EzPaste"
#endif
#define MyAppExe "EzPaste.exe"

[Setup]
AppId={{D34A9A05-A3B1-4E87-9E00-1E09487E4F87}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=G14
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=EzPaste_Setup_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExe}
; Makes the installer ask the user to close a running EzPaste (uses the app's single-instance mutex)
AppMutex=EzPaste_SingleInstance_Mutex
CloseApplications=yes
SetupIconFile=EzPaste.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: checkedonce

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon; Check: ShouldCreateDesktopIcon

[Code]
var
  WasInstalledBefore: Boolean;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // Runs before files are copied: is EzPaste already in the chosen folder?
  WasInstalledBefore := FileExists(ExpandConstant('{app}\{#MyAppExe}'));
  Result := '';
end;

function ShouldCreateDesktopIcon(): Boolean;
begin
  Result := not WasInstalledBefore;
end;

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Launch EzPaste"; Flags: nowait postinstall
