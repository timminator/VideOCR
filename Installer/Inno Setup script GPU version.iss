#define MyAppName "VideOCR"
#define MyAppVersion "1.3.1"
#define MyAppURL "https://github.com/timminator/VideOCR"
#define MyAppExeName "VideOCR.exe"
#define MyInstallerVersion "1.3.1.0"
#define MyAppCopyright "timminator"
#define SourceDir "..\VideOCR GUI\VideOCR-GPU-v1.3.1"

[Setup]
SignTool=signtool $f
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
LicenseFile=..\LICENSE
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputBaseFilename={#MyAppName}-GPU-v{#MyAppVersion}-setup-x64
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

[Dirs]
Name: "{app}"; Permissions: everyone-full

[Files]
Source: "{#SourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*.*"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{commonprograms}\(Default)\VideOCR.lnk"
Type: dirifempty; Name: "{commonprograms}\(Default)"
Type: files; Name: "{app}\videocr_gui_config.ini"
Type: filesandordirs; Name: "{app}\win32com"
Type: files; Name: "{app}\win32api.pyd"
Type: files; Name: "{app}\win32gui.pyd"
Type: files; Name: "{app}\win32ui.pyd"
Type: files; Name: "{app}\pythoncom312.dll"
Type: files; Name: "{app}\pywintypes312.dll"
Type: files; Name: "{app}\mfc140u.dll"
Type: files; Name: "{app}\_win32sysloader.pyd"
Type: filesandordirs; Name: "{app}\videocr-cli-GPU-v1.3.0"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-GPU-v1.2.1"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-GPU-v1.2.0"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-GPU-v1.1.0"

[UninstallDelete]
Type: files; Name: "{app}\videocr_gui_config.ini"
Type: filesandordirs; Name: "{localappdata}\VideOCR"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath: string;
  SelectedLanguage: string;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigPath := ExpandConstant('{app}\videocr_gui_config.ini');

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