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

; THE ARCHITECTURE: x64, or arm64 for Windows on ARM (/DArch=arm64, which
; build-windows.ps1 passes when its Python is ARM64). Same AppId, same folder:
; an ARM PC that ran the x64 build under emulation moves to the native one at
; its next update. The x64 Setup keeps the name every earlier version looks for.
;
; .NET ON ARM. The ARM build draws its windows with Microsoft's .NET Desktop
; Runtime (version 8 or later), which Windows doesn't come with: where it is
; missing, the ARM Setup downloads Microsoft's installer for .NET 10 and runs
; it first, which asks for an administrator once (MedSearch itself needs none).
; Kept out of the Setup on purpose, to keep the Setup small (his pick, 22 Oct).
; An in-app update, which runs quietly, never gets here: MedSearch picks the
; ARM Setup only on a PC that has .NET already (app.py, _windows_setup_arch).
#ifndef Arch
  #define Arch "x64"
#endif

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
#if Arch == "arm64"
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
OutputBaseFilename=MedSearch-{#AppVersion}-Setup-arm64
#else
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=MedSearch-{#AppVersion}-Setup
#endif
OutputDir=..\dist
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
  DotnetDesktopMin = 8;
  DotnetDesktopSetup = 'https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-arm64.exe';

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

{ A .NET Desktop Runtime for the PC's own processor, DotnetDesktopMin or newer,
  no preview: a folder such as dotnet\shared\Microsoft.WindowsDesktop.App\10.0.13. }
function HasDotnetDesktop(): Boolean;
var
  Found: TFindRec;
begin
  Result := False;
  if FindFirst(ExpandConstant('{commonpf64}\dotnet\shared\Microsoft.WindowsDesktop.App\*'), Found) then
  try
    repeat
      if (Found.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0) and (Pos('-', Found.Name) = 0) and
         (StrToIntDef(Copy(Found.Name, 1, Pos('.', Found.Name) - 1), 0) >= DotnetDesktopMin) then
        Result := True;
    until Result or not FindNext(Found);
  finally
    FindClose(Found);
  end;
end;

{ The ARM build only: install .NET's Desktop Runtime when it is missing. False
  keeps Setup on its last page, where Install tries again. }
function InstallDotnetDesktop(): Boolean;
var
  ResultCode: Integer;
  Why: String;
begin
  Result := True;
#if Arch == "arm64"
  if HasDotnetDesktop() then
    Exit;
  Why := '';
  DownloadPage.Clear;
  DownloadPage.Add(DotnetDesktopSetup, 'windowsdesktop-runtime-win-arm64.exe', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      { Microsoft's installer asks for an administrator itself. ShellExec, not
        Exec, so that Windows lets it. }
      if not ShellExec('', ExpandConstant('{tmp}\windowsdesktop-runtime-win-arm64.exe'),
                       '/install /quiet /norestart', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
        Why := SysErrorMessage(ResultCode)
      else if (ResultCode <> 0) and (ResultCode <> 3010) then     { 3010: done, restart later }
        Why := 'its installer ended with code ' + IntToStr(ResultCode);
    except
      Why := GetExceptionMessage;
    end;
  finally
    DownloadPage.Hide;
  end;
  if HasDotnetDesktop() then
    Exit;
  if Why = '' then
    Why := 'it is still missing';
  SuppressibleMsgBox('MedSearch for Windows on ARM needs Microsoft''s .NET Desktop Runtime, ' +
    'which could not be installed: ' + Why + '.' + #13#10#13#10 + 'Press Install to try ' +
    'again (Windows asks for an administrator), or install ".NET Desktop Runtime" for Arm64 ' +
    'from dotnet.microsoft.com and run this Setup again.', mbError, MB_OK, IDOK);
  Result := False;
#endif
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if CurPageID <> wpReady then
    Exit;
  Result := InstallDotnetDesktop();
  if (not Result) or HasWebView2() then
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
