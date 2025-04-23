#define MyAppName "VideOCR"
#define MyAppVersion "1.1.0"
#define MyAppURL "https://github.com/timminator/VideOCR"
#define MyAppExeName "VideOCR.exe"
#define MyInstallerVersion "1.1.0.0"
#define MyAppCopyright "timminator"

[Setup]
SignTool=signtool $f
AppId={{2A6F4779-ECD5-43F5-A6A1-34E72161AC02}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyInstallerVersion}
AppCopyright={#MyAppCopyright}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={commonpf64}\{#MyAppName}
UsePreviousAppDir=yes
LicenseFile=...\LICENSE
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputBaseFilename={#MyAppName}-GPU-v{#MyAppVersion}-setup-x64
SetupIconFile=...\VideOCR.ico
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

[Dirs]
Name: "{app}"; Permissions: everyone-full

[Files]
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_bz2.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_ctypes.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_decimal.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-CPU-v1.1.0\_elementtree.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_hashlib.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_lzma.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_queue.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_socket.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_ssl.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_tkinter.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_uuid.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\_wmi.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\libcrypto-3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\libffi-8.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\libssl-3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-CPU-v1.1.0\MediaInfo.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-CPU-v1.1.0\pyexpat.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\python3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\python312.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\select.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\tcl86t.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\tk86t.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\unicodedata.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\vcruntime140.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\vcruntime140_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\VideOCR.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\zlib1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\cv2\*"; DestDir: "{app}\cv2"; Flags: ignoreversion recursesubdirs
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\numpy\*"; DestDir: "{app}\numpy"; Flags: ignoreversion recursesubdirs
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\numpy.libs\*"; DestDir: "{app}\numpy.libs"; Flags: ignoreversion recursesubdirs
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\PIL\*"; DestDir: "{app}\PIL"; Flags: ignoreversion recursesubdirs
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\tcl\*"; DestDir: "{app}\tcl"; Flags: ignoreversion recursesubdirs
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\tcl8\*"; DestDir: "{app}\tcl8"; Flags: ignoreversion recursesubdirs
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\tk\*"; DestDir: "{app}\tk"; Flags: ignoreversion recursesubdirs
Source: "...\VideOCR GUI\VideOCR-GPU-v1.1.0\videocr-cli-sa-GPU-v1.1.0\*"; DestDir: "{app}\videocr-cli-sa-GPU-v1.1.0"; Flags: ignoreversion recursesubdirs

[Code]
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

[UninstallDelete]
Type: files; Name: "{app}\videocr_gui_config.ini"
Type: filesandordirs; Name: "{localappdata}\VideOCR"