import os
import time
import pandas as pd

def convert_xlsx_file(filepath):
    dir_name = os.path.dirname(filepath)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    csv_filepath = os.path.join(dir_name, f"{base_name}.csv")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            df = pd.read_excel(filepath, engine='openpyxl')
            df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
            return True, csv_filepath
        except PermissionError:
            time.sleep(1)
        except Exception as e:
            return False, str(e)
    return False, "파일 접근 권한 초과"

def convert_ansi_csv_to_utf8(filepath):
    encodings_to_try = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
    df = None
    used_encoding = None
    for enc in encodings_to_try:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            used_encoding = enc
            break
        except Exception:
            continue
    if df is not None:
        try:
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            if used_encoding in ['utf-8-sig', 'utf-8']:
                return True, "이미 UTF-8 형식입니다 (재저장 완료)"
            else:
                return True, f"변환 완료 ({used_encoding.upper()} ➔ UTF-8)"
        except Exception as e:
            return False, f"저장 실패: {str(e)}"
    else:
        return False, "지원하지 않는 인코딩이거나 파일을 읽을 수 없습니다."
