; Inno Setup script for Hammer File Maker
; Build on Windows with Inno Setup Compiler (ISCC.exe)

#define MyAppName "Hammer File Maker"
#define MyAppPublisher "Hammer File Maker"
#define MyAppExeName "Hammer File Maker.exe"

[Setup]
AppId={{E2DAED13-36DD-42BA-BD43-7E8BD8691E22}
AppName={#MyAppName}
AppVersion=1.0.0
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Hammer File Maker
DisableProgramGroupPage=yes
OutputDir=dist\installers
OutputBaseFilename=Hammer-File-Maker-Windows-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Files]
Source: "dist\Hammer File Maker\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"; GroupDescription: "Zusatzoptionen:"; Flags: checkedonce

[Icons]
Name: "{autodesktop}\Hammer File Maker"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{cmd}"; Parameters: "/C winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements"; StatusMsg: "Installiere FFmpeg..."; Flags: runhidden waituntilterminated; Check: WingetAvailable
Filename: "{cmd}"; Parameters: "/C winget install --id TheDocumentFoundation.LibreOffice -e --accept-package-agreements --accept-source-agreements"; StatusMsg: "Installiere LibreOffice..."; Flags: runhidden waituntilterminated; Check: WingetAvailable
Filename: "{cmd}"; Parameters: "/C winget install --id Inkscape.Inkscape -e --accept-package-agreements --accept-source-agreements"; StatusMsg: "Installiere Inkscape..."; Flags: runhidden waituntilterminated; Check: WingetAvailable
Filename: "{app}\{#MyAppExeName}"; Description: "Hammer File Maker starten"; Flags: nowait postinstall skipifsilent

[Code]
function WingetAvailable: Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(
    ExpandConstant('{cmd}'),
    '/C where winget >nul 2>&1',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) and (ResultCode = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and not WingetAvailable then
  begin
    MsgBox(
      'winget wurde nicht gefunden. Bitte FFmpeg, LibreOffice und Inkscape manuell installieren.',
      mbInformation,
      MB_OK
    );
  end;
end;
