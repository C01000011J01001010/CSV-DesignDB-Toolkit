version: 1.0.0

description:

설치파일을 통해 프로그램 설치 및 제거 가능

만약 설치파일을 제거했다면 제어판을 통해 제거 가능



\----------------------------------------------------  Git Bash로 본 프로그램 빌드

마우스 우클릭으로 Open Git Bash Here를 클릭 후 다음을 진행 (Copy, Paste)

pip install pandas openpyxl watchdog
pyinstaller --clean --noconsole --onefile Excel\_CSV\_Converter.py



\----------------------------------------------------  Inno Setup Compiler로 본 프로그램의 설치파일 빌드

Excel\_CSV\_Converter.exe가 정상적으로 만들어졌다면

Excel\_CSV\_Converter Setup.iss 파일을 열고 다음을 수정



Source: "C:\\Excel\_CSV\_Converter.exe"; DestDir: "{app}"; Flags: ignoreversion

\-> Source: "{실제 Excel\_CSV\_Converter.exe의 Path}" ; DestDir: "{app}"; Flags: ignoreversion



수정된 내용으로 빌드 시작

