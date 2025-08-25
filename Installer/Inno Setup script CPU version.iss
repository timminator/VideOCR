#define MyAppName "VideOCR"
#define MyAppVersion "1.3.2"
#define MyAppURL "https://github.com/timminator/VideOCR"
#define MyAppExeName "VideOCR.exe"
#define MyInstallerVersion "1.3.2.0"
#define MyAppCopyright "timminator"
#define SourceDir "..\VideOCR GUI\VideOCR-CPU-v1.3.2"

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
OutputBaseFilename={#MyAppName}-CPU-v{#MyAppVersion}-Beta-setup-x64
SetupIconFile=..\VideOCR.ico
Compression=lzma2/ultra64
InternalCompressLevel=ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=6
WizardStyle=classic
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64

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
Type: filesandordirs; Name: "{app}\videocr-cli-CPU-v1.3.0"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-CPU-v1.2.1"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-CPU-v1.2.0"
Type: filesandordirs; Name: "{app}\videocr-cli-sa-CPU-v1.1.0"

[UninstallDelete]
Type: files; Name: "{app}\videocr_gui_config.ini"
Type: filesandordirs; Name: "{localappdata}\VideOCR"

[Code]
// --- InnoDependencyInstaller Core ---
// Source: https://github.com/DomGries/InnoDependencyInstaller

type
  TDependency_Entry = record
    Filename: String;
    Parameters: String;
    Title: String;
    URL: String;
    Checksum: String;
    ForceSuccess: Boolean;
    RestartAfter: Boolean;
  end;

var
  Dependency_Memo: String;
  Dependency_List: array of TDependency_Entry;
  Dependency_NeedToRestart, Dependency_ForceX86: Boolean;
  Dependency_DownloadPage: TDownloadWizardPage;

procedure Dependency_Add(const Filename, Parameters, Title, URL, Checksum: String; const ForceSuccess, RestartAfter: Boolean);
var
  Dependency: TDependency_Entry;
  DependencyCount: Integer;
begin
  Dependency_Memo := Dependency_Memo + #13#10 + '%1' + Title;

  Dependency.Filename := Filename;
  Dependency.Parameters := Parameters;
  Dependency.Title := Title;
  if FileExists(ExpandConstant('{tmp}{\}') + Filename) then begin
    Dependency.URL := '';
  end else begin
    Dependency.URL := URL;
  end;

  Dependency.Checksum := Checksum;
  Dependency.ForceSuccess := ForceSuccess;
  Dependency.RestartAfter := RestartAfter;
  DependencyCount := GetArrayLength(Dependency_List);
  SetArrayLength(Dependency_List, DependencyCount + 1);
  Dependency_List[DependencyCount] := Dependency;
end;

<event('InitializeWizard')>
procedure Dependency_InitializeWizard;
begin
  Dependency_DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

<event('PrepareToInstall')>
function Dependency_PrepareToInstall(var NeedsRestart: Boolean): String;
var
  DependencyCount, DependencyIndex, ResultCode: Integer;
  Retry: Boolean;
  TempValue: String;
begin
  DependencyCount := GetArrayLength(Dependency_List);

  if DependencyCount > 0 then begin
    Dependency_DownloadPage.Show;
    for DependencyIndex := 0 to DependencyCount - 1 do begin
      if Dependency_List[DependencyIndex].URL <> '' then begin
        Dependency_DownloadPage.Clear;
        Dependency_DownloadPage.Add(Dependency_List[DependencyIndex].URL, Dependency_List[DependencyIndex].Filename, Dependency_List[DependencyIndex].Checksum);

        Retry := True;
        while Retry do begin
          Retry := False;
          try
            Dependency_DownloadPage.Download;
          except
            if Dependency_DownloadPage.AbortedByUser then begin
              Result := Dependency_List[DependencyIndex].Title;
              DependencyIndex := DependencyCount;
            end else begin
              case SuppressibleMsgBox(AddPeriod(GetExceptionMessage), mbError, MB_ABORTRETRYIGNORE, IDIGNORE) of
                IDABORT: begin
                  Result := Dependency_List[DependencyIndex].Title;
                  DependencyIndex := DependencyCount;
                end;
                IDRETRY: begin
                  Retry := True;
                end;
              end;
            end;
          end;
        end;
      end;
    end;

    if Result = '' then begin
      for DependencyIndex := 0 to DependencyCount - 1 do begin
        Dependency_DownloadPage.SetText(Dependency_List[DependencyIndex].Title, '');
        Dependency_DownloadPage.SetProgress(DependencyIndex + 1, DependencyCount + 1);

        while True do begin
          ResultCode := 0;
          if ShellExec('', ExpandConstant('{tmp}{\}') + Dependency_List[DependencyIndex].Filename, Dependency_List[DependencyIndex].Parameters, '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then begin
            if Dependency_List[DependencyIndex].RestartAfter then begin
              if DependencyIndex = DependencyCount - 1 then begin
                Dependency_NeedToRestart := True;
              end else begin
                NeedsRestart := True;
                Result := Dependency_List[DependencyIndex].Title;
              end;
              break;
            end else if (ResultCode = 0) or Dependency_List[DependencyIndex].ForceSuccess then begin // ERROR_SUCCESS (0)
              break;
            end else if ResultCode = 1641 then begin // ERROR_SUCCESS_REBOOT_INITIATED (1641)
              NeedsRestart := True;
              Result := Dependency_List[DependencyIndex].Title;
              break;
            end else if ResultCode = 3010 then begin // ERROR_SUCCESS_REBOOT_REQUIRED (3010)
              Dependency_NeedToRestart := True;
              break;
            end;
          end;

          case SuppressibleMsgBox(FmtMessage(SetupMessage(msgErrorFunctionFailed), [Dependency_List[DependencyIndex].Title, IntToStr(ResultCode)]), mbError, MB_ABORTRETRYIGNORE, IDIGNORE) of
            IDABORT: begin
              Result := Dependency_List[DependencyIndex].Title;
              break;
            end;
            IDIGNORE: begin
              break;
            end;
          end;
        end;

        if Result <> '' then begin
          break;
        end;
      end;

      if NeedsRestart then begin
        TempValue := '"' + ExpandConstant('{srcexe}') + '" /restart=1 /LANG="' + ExpandConstant('{language}') + '" /DIR="' + WizardDirValue + '" /GROUP="' + WizardGroupValue + '" /TYPE="' + WizardSetupType(False) + '" /COMPONENTS="' + WizardSelectedComponents(False) + '" /TASKS="' + WizardSelectedTasks(False) + '"';
        if WizardNoIcons then begin
          TempValue := TempValue + ' /NOICONS';
        end;
        RegWriteStringValue(HKA, 'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce', '{#SetupSetting("AppName")}', TempValue);
      end;
    end;

    Dependency_DownloadPage.Hide;
  end;
end;

<event('UpdateReadyMemo')>
function Dependency_UpdateReadyMemo(const Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := '';
  if MemoUserInfoInfo <> '' then begin
    Result := Result + MemoUserInfoInfo + Newline + NewLine;
  end;
  if MemoDirInfo <> '' then begin
    Result := Result + MemoDirInfo + Newline + NewLine;
  end;
  if MemoTypeInfo <> '' then begin
    Result := Result + MemoTypeInfo + Newline + NewLine;
  end;
  if MemoComponentsInfo <> '' then begin
    Result := Result + MemoComponentsInfo + Newline + NewLine;
  end;
  if MemoGroupInfo <> '' then begin
    Result := Result + MemoGroupInfo + Newline + NewLine;
  end;
  if MemoTasksInfo <> '' then begin
    Result := Result + MemoTasksInfo;
  end;
  if Dependency_Memo <> '' then begin
    if MemoTasksInfo = '' then begin
      Result := Result + SetupMessage(msgReadyMemoTasks);
    end;
    Result := Result + FmtMessage(Dependency_Memo, [Space]);
  end;
end;

<event('NeedRestart')>
function Dependency_NeedRestart: Boolean;
begin
  Result := Dependency_NeedToRestart;
end;

function Dependency_IsX64: Boolean;
begin
  Result := not Dependency_ForceX86 and Is64BitInstallMode;
end;

function Dependency_String(const x86, x64: String): String;
begin
  if Dependency_IsX64 then begin
    Result := x64;
  end else begin
    Result := x86;
  end;
end;

function Dependency_ArchTitle: String;
begin
  Result := Dependency_String(' (x86)', ' (x64)');
end;

// --- Required Dependency Functions ---

procedure Dependency_AddVC2015To2022;
begin
  // https://docs.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
  if not IsMsiProductInstalled(Dependency_String('{65E5BD06-6392-3027-8C26-853107D3CF1A}', '{36F68A90-239C-34DF-B58C-64B30153CE35}'), PackVersionComponents(14, 42, 34433, 0)) then begin
    Dependency_Add('vcredist2022' + Dependency_String('', '_x64') + '.exe',
      '/passive /norestart',
      'Visual C++ 2015-2022 Redistributable' + Dependency_ArchTitle,
      Dependency_String('https://aka.ms/vs/17/release/vc_redist.x86.exe', 'https://aka.ms/vs/17/release/vc_redist.x64.exe'),
      '', False, False);
  end;
end;

function InitializeSetup: Boolean;
begin
  Dependency_AddVC2015To2022;

  Result := True;
end;

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