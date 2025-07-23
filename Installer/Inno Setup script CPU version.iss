#define MyAppName "VideOCR"
#define MyAppVersion "1.3.0"
#define MyAppURL "https://github.com/timminator/VideOCR"
#define MyAppExeName "VideOCR.exe"
#define MyInstallerVersion "1.3.0.0"
#define MyAppCopyright "timminator"

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
OutputBaseFilename={#MyAppName}-CPU-v{#MyAppVersion}-setup-x64
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

[Dirs]
Name: "{app}"; Permissions: everyone-full

[Files]
Source: "..\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_bz2.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_ctypes.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_decimal.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_elementtree.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_hashlib.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_lzma.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_multiprocessing.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_queue.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_socket.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_ssl.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_tkinter.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_uuid.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_win32sysloader.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\_wmi.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\libcrypto-3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\libffi-8.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\libssl-3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\mfc140u.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\pyexpat.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\python3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\python312.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\pythoncom312.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\pywintypes312.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\select.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\tcl86t.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\tk86t.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\unicodedata.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\vcruntime140.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\vcruntime140_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VideOCR.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VideOCR.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\win32api.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\win32gui.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\win32ui.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\zlib1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\cv2\*"; DestDir: "{app}\cv2"; Flags: ignoreversion recursesubdirs
Source: "..\numpy\*"; DestDir: "{app}\numpy"; Flags: ignoreversion recursesubdirs
Source: "..\numpy.libs\*"; DestDir: "{app}\numpy.libs"; Flags: ignoreversion recursesubdirs
Source: "..\PIL\*"; DestDir: "{app}\PIL"; Flags: ignoreversion recursesubdirs
Source: "..\pymediainfo\*"; DestDir: "{app}\pymediainfo"; Flags: ignoreversion recursesubdirs
Source: "..\PyTaskbar\*"; DestDir: "{app}\PyTaskbar"; Flags: ignoreversion recursesubdirs
Source: "..\tcl\*"; DestDir: "{app}\tcl"; Flags: ignoreversion recursesubdirs
Source: "..\tcl8\*"; DestDir: "{app}\tcl8"; Flags: ignoreversion recursesubdirs
Source: "..\tk\*"; DestDir: "{app}\tk"; Flags: ignoreversion recursesubdirs
Source: "..\win32com\*"; DestDir: "{app}\win32com"; Flags: ignoreversion recursesubdirs
Source: "..\videocr-cli-CPU-v1.3.0\*"; DestDir: "{app}\videocr-cli-CPU-v1.3.0"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{commonprograms}\(Default)\VideOCR.lnk"
Type: dirifempty; Name: "{commonprograms}\(Default)"
Type: files; Name: "{app}\videocr_gui_config.ini"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-CPU-v1.2.1"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-CPU-v1.2.0"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-CPU-v1.1.0"

[UninstallDelete]
Type: files; Name: "{app}\videocr_gui_config.ini"
Type: filesandordirs; Name: "{localappdata}\VideOCR"

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