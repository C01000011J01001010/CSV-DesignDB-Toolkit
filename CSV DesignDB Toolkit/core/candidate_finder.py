import os
import time
import math
import json
import pandas as pd
from itertools import combinations

def find_candidate_keys(target_dir, max_len, include_subdirs, on_log, on_progress):
    csv_files = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
        if not include_subdirs: dirs.clear()
        for file in files:
            if file.startswith('Disabled'): continue
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        on_log("❌ 탐색할 CSV 파일을 찾을 수 없습니다.")
        return

    for csv_file in csv_files:
        on_log(f"\n\n\n▶ 파일 탐색: {os.path.basename(csv_file)}")
        try:
            try: df = pd.read_csv(csv_file, encoding='utf-8')
            except UnicodeDecodeError: df = pd.read_csv(csv_file, encoding='cp949')
        except Exception as e:
            on_log(f"  └ ❌ 읽기 실패: {e}")
            continue

        total_rows = len(df)
        valid_columns = []
        ex_constraint_info, ex_null, ex_special = [], [], []
        new_columns = {}
        
        for old_col in df.columns:
            col_str = str(old_col).strip()
            clean_col = col_str
            c_type = ""
            
            if col_str.startswith('{') and col_str.endswith('}'):
                parts = [p.strip() for p in col_str[1:-1].split('/')]
                if parts:
                    clean_col = parts[0]
                    if len(parts) > 1: c_type = parts[1].lower()

            new_columns[old_col] = clean_col
            
            if "[]" in c_type or c_type == 'float':
                ex_constraint_info.append(f"'{clean_col}' ({c_type} 키 배제)")
                continue

            if df[old_col].isna().any() or (df[old_col].dropna().astype(str).str.strip() == '').any():
                ex_null.append(clean_col)
                continue
                
            if df[old_col].dropna().astype(str).str.contains(r'[|_]', regex=True).any():
                ex_special.append(clean_col)
                continue
                
            valid_columns.append(clean_col)

        df = df.rename(columns=new_columns)

        if ex_constraint_info: on_log(f"  └ 🚫 제외됨 (타입 제한) : {', '.join(ex_constraint_info)}")
        if ex_null: on_log(f"  └ 🚫 제외됨 (빈 값/NaN) : {ex_null}")
        if ex_special: on_log(f"  └ 🚫 제외됨 ('|' 또는 '_'): {ex_special}")
        
        n_cols = len(valid_columns)
        if n_cols == 0:
            on_log("  └ 탐색할 유효한 컬럼이 없습니다.")
            continue

        actual_max = min(n_cols, max_len)
        total_combos = sum(math.comb(n_cols, r) for r in range(1, actual_max + 1))
        candidate_keys = []
        processed = 0

        for r in range(1, actual_max + 1):
            for combo in combinations(valid_columns, r):
                time.sleep(0.001) 
                combo_set = set(combo)
                
                is_minimal = True
                for ck in candidate_keys:
                    if set(ck).issubset(combo_set):
                        is_minimal = False
                        break
                
                if is_minimal and len(df[list(combo)].drop_duplicates()) == total_rows:
                    candidate_keys.append(list(combo))
                    on_log(f"  └ ✅ [후보키] {combo}")
                
                processed += 1
                progress = (processed / total_combos) * 100
                on_progress(progress)

        on_log(f"▷ 총 {len(candidate_keys)}개의 후보키 발견 완료.")

        json_path = os.path.splitext(csv_file)[0] + ".json"
        meta_data = {
            "csvFileName": os.path.basename(csv_file),
            "primaryKey": [],
            "foreignKeys": {},
            "candidateKeys": candidate_keys
        }
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as jf:
                    existing = json.load(jf)
                    if 'primaryKey' in existing: meta_data['primaryKey'] = existing['primaryKey']
                    if 'foreignKeys' in existing: meta_data['foreignKeys'] = existing['foreignKeys']
            except: pass

        try:
            with open(json_path, 'w', encoding='utf-8') as jf:
                json.dump(meta_data, jf, ensure_ascii=False, indent=2)
            on_log(f"  └ 💾 JSON 메타데이터 갱신 완료: {os.path.basename(json_path)}")
        except Exception as e:
            on_log(f"  └ ❌ JSON 저장 실패: {e}")

    on_log("\n✨ 모든 CSV 파일의 후보키 분석 및 JSON 갱신이 완료되었습니다!")
    on_progress(100)
