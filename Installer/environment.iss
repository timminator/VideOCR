; environment.iss
; The code is kindly provided by Wojciech Mleczek in the answer on StackOverflow:
; https://stackoverflow.com/a/46609047/1240328
; Modified to be used at the current user level (if there are no administrator privileges) by georgy7 (https://github.com/georgy7/catframes/blob/main/installer/environment.iss).

[Code]
procedure SelectEnvKeys(var RootKey: integer; var EnvironmentKey: string);
begin
    if IsAdminInstallMode() then
    begin
      RootKey := HKEY_LOCAL_MACHINE;
      EnvironmentKey := 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
    end
    else
    begin
      RootKey := HKEY_CURRENT_USER;
      EnvironmentKey := 'Environment';
    end;
end;


function IsPathInList(Path: string; Paths: string): boolean;
var
    X, Tail: string;
    P: integer;
begin
    Result := false;

    Tail := Paths;
    while Length(Tail) > 0 do
    begin
        P := Pos(';', Tail);

        if P < 1 then
        begin
            X := Tail;
            Tail := '';
        end
        else
        begin
            X := Copy(Tail, 1, P-1);
            Tail := Copy(Tail, P+1, Length(Tail)-P);
        end;

        if SameStr(Uppercase(X), Uppercase(Path)) then
        begin
            Result := true;
            break;
        end;
    end;
end;


function StartsWith(S, Head: string): boolean;
begin
    Result := (1=Pos(Head, S));
end;


function EndsWith(S, Tail: string): boolean;
begin
    Result := SameStr(Tail, Copy(S, Length(S)+1-Length(Tail), Length(Tail)));
end;


function WithoutPathInternal(S, Path: string): string;
var
    Part: string;
    I: integer;
begin
    if SameStr(Uppercase(Path), Uppercase(S)) then Result := ''
    else
    begin
        Result := S;

        Part := ';'+Uppercase(Path)+';';
        repeat
            I := Pos(Part, Uppercase(Result));
            Delete(Result, I, Length(Part)-1);
        until 0=I;

        Part := Uppercase(Path)+';';
        if StartsWith(Uppercase(Result), Part) then
            Delete(Result, 1, Length(Part));

        Part := ';'+Uppercase(Path);
        if EndsWith(Uppercase(Result), Part) then
            Delete(Result, Length(Result)+1-Length(Part), Length(Part));

        if StartsWith(Result, ';') then
            Delete(Result, 1, 1);

        if EndsWith(Result, ';') then
            Delete(Result, Length(Result), 1);
    end;
end;


function WithoutPath(S, Path: string): string;
begin
    Result := WithoutPathInternal(S, Path);
    if EndsWith(Path, '\') then
        Result := WithoutPathInternal(Result, Copy(Path, 1, Length(Path)-1))
    else
        Result := WithoutPathInternal(Result, Path+'\');
end;


procedure EnvAddPath(Path: string);
var
    RootKey: integer;
    EnvironmentKey: string;
    Paths: string;
begin
    SelectEnvKeys(RootKey, EnvironmentKey);

    { Retrieve current path (use empty string if entry not exists) }
    if not RegQueryStringValue(RootKey, EnvironmentKey, 'Path', Paths)
    then Paths := '';

    if IsPathInList(Path, Paths) then exit;

    if 0 = Length(Paths) then
        Paths := Path
    else if EndsWith(Paths, ';') then
        Paths := Paths + Path
    else
        Paths := Paths + ';'+ Path;

    { Overwrite (or create if missing) path environment variable }
    if RegWriteStringValue(RootKey, EnvironmentKey, 'Path', Paths)
    then Log(Format('The [%s] added to PATH: [%s]', [Path, Paths]))
    else Log(Format('Error while adding the [%s] to PATH: [%s]', [Path, Paths]));
end;


procedure EnvRemovePath(Path: string);
var
    RootKey: integer;
    EnvironmentKey: string;
    Paths: string;
begin
    SelectEnvKeys(RootKey, EnvironmentKey);

    { Skip if registry entry not exists }
    if not RegQueryStringValue(RootKey, EnvironmentKey, 'Path', Paths) then
        exit;

    if not IsPathInList(Path, Paths) then exit;

    Paths := WithoutPath(Paths, Path);

    { Overwrite path environment variable }
    if RegWriteStringValue(RootKey, EnvironmentKey, 'Path', Paths)
    then Log(Format('The [%s] removed from PATH: [%s]', [Path, Paths]))
    else Log(Format('Error while removing the [%s] from PATH: [%s]', [Path, Paths]));
end;