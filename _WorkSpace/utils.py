import os
import json
import ctypes
import sys
from datetime import datetime

# 💡 [복구됨] 프로그램 중복 실행 방지 (Mutex) 로직
def check_single_instance():
    if os.name == 'nt':
        mutex_name = "Global\\CSV_DesignDB_Toolkit_Mutex"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
            return False
        # 핸들이 가비지 컬렉터에 의해 날아가지 않도록 sys 모듈에 안전하게 보관
        sys.prevent_gc_mutex = mutex
    return True

# 💡 [복구됨] Disabled 폴더 감시 무시 로직
def is_disabled_path(path):
    if not path:
        return False
    # 윈도우(\)와 맥/리눅스(/) 경로 구분자를 모두 호환 처리하여 'Disabled' 폴더가 있는지 검사
    parts = path.replace('\\', '/').split('/')
    return 'Disabled' in parts

def get_initial_dir():
    return os.getcwd()

def find_workspace_root(current_dir):
    d = os.path.abspath(current_dir)
    while True:
        try:
            files = os.listdir(d)
            # 1. 신형 확장자 우선 탐색 (.csvdesigndb)
            for f in files:
                if f.endswith('.csvdesigndb'):
                    return d, f
            # 2. 구형 확장자 탐색 (마이그레이션용 .root)
            for f in files:
                if f.endswith('.root'):
                    return d, f
        except Exception:
            pass
            
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None, None

def create_workspace_root(target_dir, proj_name):
    # 신형 JSON 확장자(.csvdesigndb) 적용
    filename = f"{proj_name}.csvdesigndb"
    filepath = os.path.join(target_dir, filename)
    
    config_data = {
        "projectName": proj_name,
        "toolkitVersion": "1.1.0",
        "settings": {
            "maxSuperkeyLength": 2,
            "includeSubDirectories": True
        },
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return target_dir, filename
    except Exception:
        return None, None
