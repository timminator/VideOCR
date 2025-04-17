#define MyAppName "VideOCR-CPU"
#define MyAppVersion "1.0.0"
#define MyAppURL "https://github.com/timminator/VideOCR"
#define MyAppExeName "videocr.exe"
#define MyInstallerVersion "1.0.0.0"
#define MyAppCopyright "timminator"

#include "environment.iss"

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
OutputBaseFilename={#MyAppName}-v{#MyAppVersion}-setup-x64
SetupIconFile=...\icon.ico
Compression=lzma2/ultra64
InternalCompressLevel=ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=6
WizardStyle=classic
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Dirs]
Name: "{app}"; Permissions: everyone-full

[Files]
Source: "...\Standalone\VideOCR-CPU-v1.0.0\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\_bz2.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\_ctypes.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\_decimal.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\_hashlib.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\_lzma.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\_socket.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\_ssl.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\libcrypto-1_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\libffi-7.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\libssl-1_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\python3.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\python310.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\select.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\unicodedata.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\vcruntime140.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\vcruntime140_1.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\videocr.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "...\Standalone\VideOCR-CPU-v1.0.0\cv2\*"; DestDir: "{app}\cv2"; Flags: ignoreversion recursesubdirs
Source: "...\Standalone\VideOCR-CPU-v1.0.0\numpy\*"; DestDir: "{app}\numpy"; Flags: ignoreversion recursesubdirs
Source: "...\Standalone\VideOCR-CPU-v1.0.0\numpy.libs\*"; DestDir: "{app}\numpy.libs"; Flags: ignoreversion recursesubdirs
Source: "...\Standalone\VideOCR-CPU-v1.0.0\PaddleOCR.PP-OCRv4.support.files\*"; DestDir: "{app}\PaddleOCR.PP-OCRv4.support.files"; Flags: ignoreversion recursesubdirs
Source: "...\Standalone\VideOCR-CPU-v1.0.0\PaddleOCR-CPU-v1.0.0\*"; DestDir: "{app}\PaddleOCR-CPU-v1.0.0"; Flags: ignoreversion recursesubdirs
Source: "...\Standalone\VideOCR-CPU-v1.0.0\rapidfuzz\*"; DestDir: "{app}\rapidfuzz"; Flags: ignoreversion recursesubdirs

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
    if (CurStep = ssPostInstall) and WizardIsTaskSelected('envPath')
    then EnvAddPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
    if CurUninstallStep = usPostUninstall
    then EnvRemovePath(ExpandConstant('{app}'));
end;

[Tasks]
Name: envPath; Description: "Add to PATH variable"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"