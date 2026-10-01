[Setup]
; 프로그램 기본 정보
AppName=Excel CSV Converter
AppVersion=1.0
AppPublisher=My Company
AppPublisherURL=https://github.com/
; 제어판에 표시될 기본 설치 경로 (C:\Program Files\Excel CSV Converter)
DefaultDirName={autopf}\Excel CSV Converter
DisableProgramGroupPage=yes
; 출력될 설치 파일 이름
OutputBaseFilename=ExcelCSVConverter_Setup
Compression=lzma
SolidCompression=yes
; 관리자 권한 요구 (Program Files 저장 및 레지스트리 등록을 위해 필수)
PrivilegesRequired=admin
; 제어판 아이콘 설정 (본 프로그램의 아이콘 사용)
SetupIconFile=compiler:SetupClassicIcon.ico
UninstallDisplayIcon={app}\Excel_CSV_Converter.exe

[Files]
; 👉 [중요] 아래 Source 경로를 실제 Excel_CSV_Converter.exe 가 있는 위치로 수정하세요!
Source: "C:\Excel_CSV_Converter.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 바탕화면 및 시작 메뉴에 바로가기 아이콘 생성
Name: "{autoprograms}\Excel CSV Converter"; Filename: "{app}\Excel_CSV_Converter.exe"
Name: "{autodesktop}\Excel CSV Converter"; Filename: "{app}\Excel_CSV_Converter.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 아이콘:"

[Registry]
; =======================================================================
; 1. 폴더를 우클릭했을 때 나타나는 메뉴
; =======================================================================
Root: HKCR; Subkey: "Directory\shell\ExcelCSVConverter"; ValueType: string; ValueName: ""; ValueData: "Open Excel CSV Converter Here"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\ExcelCSVConverter"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Excel_CSV_Converter.exe"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\ExcelCSVConverter\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Excel_CSV_Converter.exe"" ""%V"""; Flags: uninsdeletekey

; =======================================================================
; 2. 폴더 내부 빈 공간을 우클릭했을 때 나타나는 메뉴
; =======================================================================
Root: HKCR; Subkey: "Directory\Background\shell\ExcelCSVConverter"; ValueType: string; ValueName: ""; ValueData: "Open Excel CSV Converter Here"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\Background\shell\ExcelCSVConverter"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Excel_CSV_Converter.exe"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\Background\shell\ExcelCSVConverter\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Excel_CSV_Converter.exe"" ""%V"""; Flags: uninsdeletekey