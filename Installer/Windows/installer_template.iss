#ifndef MyAppVersion
  #error "MyAppVersion must be defined on the command line."
#endif
#ifndef SourceDir
  #error "SourceDir must be defined on the command line."
#endif
#ifndef OutputBaseFilename
  #error "OutputBaseFilename must be defined on the command line."
#endif
#ifndef OutputDir
  #error "OutputDir must be defined on the command line."
#endif


#define MyAppName "VideOCR"
#define MyAppURL "https://github.com/timminator/VideOCR"
#define MyAppExeName "VideOCR.exe"
#define MyInstallerVersion MyAppVersion + ".0"
#define MyAppCopyright "timminator"

[Setup]
SignTool=signtool
AppId={{A8B0CA74-8EC9-4D6F-AB00-51C9BF6808B9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyInstallerVersion}
AppCopyright={#MyAppCopyright}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={commonpf64}\{#MyAppName}
DefaultGroupName={#MyAppName}
UsePreviousAppDir=yes
LicenseFile=..\..\LICENSE
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile=..\VideOCR.ico
Compression=lzma2/ultra64
InternalCompressLevel=ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=6
WizardStyle=classic
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "indonesian"; MessagesFile: "compiler:Languages\Indonesian.isl"
Name: "Thai"; MessagesFile: "compiler:Languages\Thai.isl"
Name: "Korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "vietnamese"; MessagesFile: "compiler:Languages\Vietnamese.isl"

[Dirs]
Name: "{app}"; Permissions: everyone-full

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*.*"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{commonprograms}\(Default)\VideOCR.lnk"
Type: dirifempty; Name: "{commonprograms}\(Default)"
Type: filesandordirs; Name: "{app}\win32com"
Type: files; Name: "{app}\win32api.pyd"
Type: files; Name: "{app}\win32gui.pyd"
Type: files; Name: "{app}\win32ui.pyd"
Type: files; Name: "{app}\pythoncom312.dll"
Type: files; Name: "{app}\pywintypes312.dll"
Type: files; Name: "{app}\mfc140u.dll"
Type: files; Name: "{app}\_win32sysloader.pyd"
Type: filesandordirs; Name: "{app}\videocr-cli-*"
Type: files; Name: "{app}\videocr_gui_config.ini"

[UninstallDelete]
Type: files; Name: "{app}\videocr_gui_config.ini"
Type: filesandordirs; Name: "{localappdata}\VideOCR"

[Code]
function GetToken(const S: string; Index: Integer): Integer;
var
  i, Count, StartPos: Integer;
  Part: string;
begin
  Count := 0;
  StartPos := 1;
  for i := 1 to Length(S) + 1 do
  begin
    if (i > Length(S)) or (S[i] = '.') then
    begin
      if Count = Index then
      begin
        Part := Copy(S, StartPos, i - StartPos);
        Result := StrToIntDef(Part, 0);
        Exit;
      end;
      Count := Count + 1;
      StartPos := i + 1;
    end;
  end;
  Result := 0;
end;

function VersionCompare(OldVersion, NewVersion: string): Integer;
var
  OldMajor, OldMinor, OldPatch: Integer;
  NewMajor, NewMinor, NewPatch: Integer;
begin
  OldMajor := GetToken(OldVersion, 0);
  OldMinor := GetToken(OldVersion, 1);
  OldPatch := GetToken(OldVersion, 2);

  NewMajor := GetToken(NewVersion, 0);
  NewMinor := GetToken(NewVersion, 1);
  NewPatch := GetToken(NewVersion, 2);

  if OldMajor <> NewMajor then
    Result := OldMajor - NewMajor
  else if OldMinor <> NewMinor then
    Result := OldMinor - NewMinor
  else
    Result := OldPatch - NewPatch;
end;

function GetInstalledVersion(): string;
var
  UninstallKey: string;
begin
  UninstallKey := 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{A8B0CA74-8EC9-4D6F-AB00-51C9BF6808B9}_is1';

  if RegQueryStringValue(HKEY_LOCAL_MACHINE, UninstallKey, 'DisplayVersion', Result) then
    Exit;
  if RegQueryStringValue(HKEY_CURRENT_USER, UninstallKey, 'DisplayVersion', Result) then
    Exit;

  Result := '0.0.0';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, OldVersion: string;
  SelectedLanguage: string;
begin
  if CurStep = ssInstall then
  begin
    OldVersion := GetInstalledVersion();

    if VersionCompare(OldVersion, '1.3.1') < 0 then
    begin
      ConfigPath := ExpandConstant('{app}\\videocr_gui_config.ini');
      if FileExists(ConfigPath) then
        DeleteFile(ConfigPath);
    end;
  end;

  if CurStep = ssPostInstall then
  begin
    ConfigPath := ExpandConstant('{app}\\videocr_gui_config.ini');

    if not FileExists(ConfigPath) then
    begin
      SelectedLanguage := ActiveLanguage();

      case SelectedLanguage of
        'german':            SetIniString('Settings', '--language', 'de', ConfigPath);
        'chinesesimplified': SetIniString('Settings', '--language', 'ch', ConfigPath);
        'spanish':           SetIniString('Settings', '--language', 'es', ConfigPath);
        'french':            SetIniString('Settings', '--language', 'fr', ConfigPath);
        'portuguese':        SetIniString('Settings', '--language', 'pt', ConfigPath);
        'italian':           SetIniString('Settings', '--language', 'it', ConfigPath);
        'arabic':            SetIniString('Settings', '--language', 'ar', ConfigPath);
        'russian':           SetIniString('Settings', '--language', 'ru', ConfigPath);
        'indonesian':        SetIniString('Settings', '--language', 'id', ConfigPath);
        'Thai':              SetIniString('Settings', '--language', 'th', ConfigPath);
        'Korean':            SetIniString('Settings', '--language', 'ko', ConfigPath);
        'japanese':          SetIniString('Settings', '--language', 'ja', ConfigPath);
        'vietnamese':        SetIniString('Settings', '--language', 'vi', ConfigPath);
      else
        SetIniString('Settings', '--language', 'en', ConfigPath);
      end;
    end;
  end;
end;

procedure DeleteTempFolders;
var
  FindRec: TFindRec;
  TempPath: string;
begin
  TempPath := GetTempDir;
  if FindFirst(TempPath + 'videocr_temp_*', FindRec) then
  begin
    try
      repeat
        DelTree(TempPath + FindRec.Name, True, True, True);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    DeleteTempFolders;
  end;
end;

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent