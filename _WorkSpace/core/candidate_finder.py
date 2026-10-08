import os
import json
import pandas as pd
from itertools import combinations

def parse_header(raw_str):
    name = str(raw_str).strip()
    c_type = "string"
    if name.startswith('{') and name.endswith('}'):
        parts = [p.strip() for p in name[1:-1].split('/')]
        name = parts[0]
        if len(parts) > 1: c_type = parts[1].strip()
    return name, c_type

def find_candidate_keys(target_dir, max_combo, include_subdirs, on_log, on_progress):
    csv_files = []
    for root, dirs, files in os.walk(target_dir):
        if 'Disabled' in root: continue
        if not include_subdirs and root != target_dir: continue
        for file in files:
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        on_log("❌ 작업 경로 내에 스캔할 CSV 파일이 없습니다.")
        return

    total_files = len(csv_files)
    for i, csv_file in enumerate(csv_files):
        base_name = os.path.basename(csv_file)
        json_file = os.path.splitext(csv_file)[0] + ".json"
        
        try:
            try: df = pd.read_csv(csv_file, encoding='utf-8')
            except UnicodeDecodeError: df = pd.read_csv(csv_file, encoding='cp949')
        except Exception as e:
            on_log(f"⚠️ {base_name} 읽기 실패: {e}")
            continue

        rename_map = {}
        col_types = {}
        for c in df.columns:
            c_name, c_type = parse_header(c)
            rename_map[c] = c_name
            col_types[c_name] = c_type.lower()
        df = df.rename(columns=rename_map)

        eligible_cols = []
        for c_name in df.columns:
            c_type = col_types.get(c_name, "string")
            
            # 1. 타입 허용 및 배제 (int, string, bool, enum, assetid 허용 / float, 배열 배제)
            if '[]' in c_type or 'float' in c_type:
                continue
            if c_type not in ['int', 'string', 'bool', 'enum', 'assetid', '']:
                continue
            
            if df[c_name].isna().any():
                continue
            
            # 💡 [최적화] 불필요한 중복 정규식 검사(|, \n) 완전 제거
            eligible_cols.append(c_name)

        candidate_keys = []
        for r in range(1, min(max_combo, len(eligible_cols)) + 1):
            for combo in combinations(eligible_cols, r):
                combo = list(combo)
                
                # 최소성 검증 (슈퍼키 배제)
                is_superkey = False
                for ck in candidate_keys:
                    if set(ck).issubset(set(combo)):
                        is_superkey = True
                        break
                if is_superkey:
                    continue
                    
                # 유일성 검사 (판다스는 내부적으로 Tuple로 비교하므로 구분자 충돌 없음)
                if not df.duplicated(subset=combo).any():
                    candidate_keys.append(combo)

        meta_data = {}
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    meta_data = json.load(f)
            except: pass
            
        meta_data['candidateKeys'] = candidate_keys
        if 'primaryKey' not in meta_data: meta_data['primaryKey'] = []
        if 'foreignKeys' not in meta_data: meta_data['foreignKeys'] = {}
        
        pk = meta_data.get('primaryKey', [])
        pk_valid = False
        if pk:
            for ck in candidate_keys:
                if set(pk) == set(ck):
                    pk_valid = True
                    break
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
        log_msg = f"✅ {base_name} ➔ 후보키 {len(candidate_keys)}개 추출 완료"
        if pk and not pk_valid:
            log_msg += f" (⚠️ 기존 PK {pk}가 더 이상 유효한 조합이 아님!)"
        on_log(log_msg)
        
        on_progress(int((i + 1) / total_files * 100))

    on_log("\n🎉 모든 메타데이터 후보키(JSON) 추출 및 갱신이 완료되었습니다!")
