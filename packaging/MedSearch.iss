; MedSearch — the Windows installer (Inno Setup 6).
; Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
;
; Installs dist\MedSearch (PyInstaller's build from MedSearch.spec) for the
; person running it: into their own Programs folder, with no administrator
; rights, a Start menu entry, and a Desktop icon unless they untick it (his
; choice, 30 Sep). Built by packaging\build-windows.ps1.
;
; EDGE'S WEB ENGINE (WebView2) draws MedSearch's windows. Windows 11 has it, and
; so do nearly all Windows 10 PCs; where it is missing, Setup downloads
; Microsoft's own installer for it and runs that first.
;
; AN UPDATE IS THIS SETUP RUN AGAIN: it closes a running MedSearch, clears the
; old program files and puts the new ones in place. The settings and keys are
; not in the program folder (they are in the user's .medsearch folder and in
; Credential Manager), so an update or an uninstall leaves them alone.

#define VersionFile AddBackslash(SourcePath) + "..\VERSION"
#define VersionHandle FileOpen(VersionFile)
#define AppVersion Trim(FileRead(VersionHandle))
#expr FileClose(VersionHandle)

[Setup]
; Never change the AppId: it is how Windows knows a new Setup updates this app.
AppId={{517922D8-2BE5-492D-9FA3-42779BACA2AC}
AppName=MedSearch
AppVersion={#AppVersion}
AppVerName=MedSearch {#AppVersion}
AppPublisher=Riccardo Nevoso
AppPublisherURL=https://github.com/H4lBarAd11/MedSearch
AppSupportURL=https://github.com/H4lBarAd11/MedSearch/issues
DefaultDirName={autopf}\MedSearch
DefaultGroupName=MedSearch
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=MedSearch-{#AppVersion}-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\MedSearch.exe
UninstallDisplayName=MedSearch
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; The old program files go first: a module the new version no longer has must not linger.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\MedSearch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MedSearch"; Filename: "{app}\MedSearch.exe"
Name: "{autodesktop}\MedSearch"; Filename: "{app}\MedSearch.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MedSearch.exe"; Description: "{cm:LaunchProgram,MedSearch}"; Flags: nowait postinstall skipifsilent
; An in-app update runs Setup quietly with /RELAUNCH=1: MedSearch opens again when it is done.
Filename: "{app}\MedSearch.exe"; Parameters: "--relaunch"; Flags: nowait; Check: Relaunching

[Code]
const
  WebView2Client = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Setup = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';
  RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';

var
  DownloadPage: TDownloadWizardPage;

function Relaunching(): Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;

function Installed(Root: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, WebView2Client, 'pv', Version)
            and (Version <> '') and (Version <> '0.0.0.0');
end;

{ Where Microsoft says to look: for all users (either registry view), or for this user. }
function HasWebView2(): Boolean;
begin
  Result := Installed(HKLM32) or (IsWin64 and Installed(HKLM64)) or Installed(HKCU);
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing),
                                     SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if (CurPageID <> wpReady) or HasWebView2() then
    Exit;
  DownloadPage.Clear;
  DownloadPage.Add(WebView2Setup, 'MicrosoftEdgeWebview2Setup.exe', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '',
           SW_HIDE, ewWaitUntilTerminated, ResultCode);
    except
      SuppressibleMsgBox('MedSearch needs Microsoft Edge WebView2, which could not be ' +
        'installed: ' + GetExceptionMessage + #13#10#13#10 + 'Setup will go on. If ' +
        'MedSearch then shows an empty window, install "WebView2 Runtime" from ' +
        'microsoft.com and open MedSearch again.', mbError, MB_OK, IDOK);
    end;
  finally
    DownloadPage.Hide;
  end;
end;

{ Open at login is MedSearch's own entry under the Run key: it goes with the app. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKCU, RunKey, 'MedSearch');
end;
