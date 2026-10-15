import os
import sys
import subprocess

# 💡 수정됨: r""" 대신 r''' 를 사용하여 내부의 큰따옴표 충돌을 방지합니다.
ISS_TEMPLATE = r'''[Setup]
; 프로그램 기본 정보
AppName=CSV DesignDB Toolkit
AppVersion=__VERSION__
AppPublisher=YCJ
AppPublisherURL=https://github.com/C01000011J01001010/CSV-DesignDB-Toolkit

; 제어판에 표시될 기본 설치 경로
DefaultDirName={autopf}\CSV DesignDB Toolkit
DisableProgramGroupPage=yes

; 출력될 설치 파일 이름
OutputBaseFilename=CSV_DesignDB_Toolkit_Setup_v__VERSION__
Compression=lzma
SolidCompression=yes

; 관리자 권한 요구
PrivilegesRequired=admin

; 아이콘 설정 (기본 경로)
SetupIconFile=compiler:SetupClassicIcon.ico
UninstallDisplayIcon={app}\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe

[Files]
Source: "__BASE_DIR__\dist\CSV_DesignDB_Toolkit_Setup_v__VERSION__\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "__BASE_DIR__\dist\CSV_DesignDB_Toolkit_Setup_v__VERSION__\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 바탕화면 및 시작 메뉴 바로가기
Name: "{autoprograms}\CSV DesignDB Toolkit"; Filename: "{app}\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe"
Name: "{autodesktop}\CSV DesignDB Toolkit"; Filename: "{app}\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 아이콘:"

[Registry]
; 1. 폴더를 우클릭했을 때 나타나는 메뉴
Root: HKCR; Subkey: "Directory\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: ""; ValueData: "Open CSV DesignDB Toolkit Here"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\shell\CSVDesignDBToolkit\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe"" ""%V"""; Flags: uninsdeletekey

; 2. 폴더 내부 빈 공간을 우클릭했을 때 나타나는 메뉴
Root: HKCR; Subkey: "Directory\Background\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: ""; ValueData: "Open CSV DesignDB Toolkit Here"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\Background\shell\CSVDesignDBToolkit"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Directory\Background\shell\CSVDesignDBToolkit\command"; ValueType: string; ValueName: ""; ValueData: """{app}\CSV_DesignDB_Toolkit_Setup_v__VERSION__.exe"" ""%V"""; Flags: uninsdeletekey
'''

def main():
    print("="*50)
    print(" 🚀 CSV DesignDB Toolkit 배포 자동화 스크립트 🚀")
    print("="*50)
    
    # 1. 버전 입력 받기
    version = input("👉 출시할 버전을 입력하세요 (예: 1.4.0) : ").strip()
    if not version:
        print("❌ 버전이 입력되지 않아 종료합니다.")
        return

    exe_name = f"CSV_DesignDB_Toolkit_Setup_v{version}"
    base_dir = os.path.abspath(os.getcwd())

    # 2. PyInstaller 실행
    print(f"\n[1/3] PyInstaller 빌드 시작: {exe_name} ...")
    pyinstaller_cmd = ["pyinstaller", "-w", "-n", exe_name, "main.py"]
    
    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("✅ PyInstaller 빌드 성공!")
    except subprocess.CalledProcessError:
        print("❌ PyInstaller 빌드 중 오류가 발생했습니다.")
        sys.exit(1)

    # 3. Inno Setup 스크립트 동적 생성
    print("\n[2/3] Inno Setup 스크립트(.iss) 생성 중...")
    iss_content = ISS_TEMPLATE.replace("__VERSION__", version).replace("__BASE_DIR__", base_dir)
    iss_filename = f"build_setup_v{version}.iss"
    
    with open(iss_filename, "w", encoding="utf-8-sig") as f:
        f.write(iss_content)
    print(f"✅ {iss_filename} 생성 완료!")

    # 4. ISCC (Inno Setup Compiler) 실행
    print("\n[3/3] 설치 파일(Setup.exe) 컴파일 시작...")
    
    # Inno Setup 6 기본 설치 경로
    iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    
    # 설치 경로에 없으면 환경변수에 등록된 iscc 명령어를 시도
    if not os.path.exists(iscc_path):
        iscc_path = "iscc"
        
    try:
        subprocess.run([iscc_path, iss_filename], check=True)
        print("\n" + "="*50)
        print(f"🎉 성공적으로 자동화 빌드가 완료되었습니다!")
        print(f"📁 최종 설치 파일 위치: {os.path.join(base_dir, 'Output')}")
        print("="*50)
        
        os.remove(iss_filename)
        
    except FileNotFoundError:
        print("❌ Inno Setup 컴파일러(ISCC.exe)를 찾을 수 없습니다.")
        print(r"Inno Setup이 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' 에 설치되어 있는지 확인해주세요.")
    except subprocess.CalledProcessError:
        print("❌ Inno Setup 컴파일 중 오류가 발생했습니다.")

if __name__ == "__main__":
    main()