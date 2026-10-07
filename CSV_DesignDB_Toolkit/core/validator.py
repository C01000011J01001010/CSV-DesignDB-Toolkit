import os
import json
import pandas as pd
import numpy as np

def parse_header(raw_str):
    name = str(raw_str).strip()
    c_type = "string"
    constraints = []
    if name.startswith('{') and name.endswith('}'):
        parts = [p.strip() for p in name[1:-1].split('/')]
        name = parts[0]
        if len(parts) > 1: c_type = parts[1].strip()
        if len(parts) > 2: constraints = [p.strip() for p in parts[2:]]
    return name, c_type, constraints

def run_global_validation(workspace_root, on_log, on_progress):
    csv_files = []
    for root, dirs, files in os.walk(workspace_root):
        if 'Disabled' in root: continue
        for file in files:
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        on_log("❌ 워크스페이스 내에 검증할 CSV 파일이 없습니다.")
        return

    on_log("🔍 1단계: 메타데이터(JSON) 및 기본키(PK) 설정 여부 확인 중...")
    missing_meta = []
    missing_pk = []
    meta_dict = {}
    df_dict = {}

    # 💡 [핵심] 유효한 JSON 및 PK가 있는지 사전 검사
    for csv_file in csv_files:
        json_file = os.path.splitext(csv_file)[0] + ".json"
        base_name = os.path.basename(csv_file)
        
        if not os.path.exists(json_file):
            missing_meta.append(base_name)
            continue
            
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                if not meta.get('primaryKey'):
                    missing_pk.append(base_name)
                else:
                    meta_dict[base_name] = meta
        except Exception:
            missing_meta.append(base_name)

    # 누락된 정보가 있다면 우선 처리 안내 후 검증 중단
    if missing_meta or missing_pk:
        on_log("\n🚨 [검증 중단] 유효한 메타데이터가 없는 테이블이 발견되었습니다.")
        on_log("다음 파일들은 [3. 메타(후보키) 추출] 및 [4. 메타 관리(PK/FK)] 탭에서 기본키(PK)를 먼저 설정해야 전체 무결성 검사가 가능합니다.\n")
        for f in missing_meta:
            on_log(f" ❌ {f} (JSON 메타파일 누락 또는 파싱 실패)")
        for f in missing_pk:
            on_log(f" ❌ {f} (기본키 미설정)")
        return

    on_log("✅ 모든 테이블의 메타데이터 확인 완료. 데이터 로드 시작...\n")
    on_progress(20)
    
    for csv_file in csv_files:
        base_name = os.path.basename(csv_file)
        if base_name not in meta_dict: continue
        try:
            try: df = pd.read_csv(csv_file, encoding='utf-8')
            except UnicodeDecodeError: df = pd.read_csv(csv_file, encoding='cp949')
            
            rename_map = {}
            col_info = {}
            for c in df.columns:
                c_name, c_type, constraints = parse_header(c)
                rename_map[c] = c_name
                col_info[c_name] = {'type': c_type, 'constraints': constraints, 'raw': c}
            
            df = df.rename(columns=rename_map)
            df_dict[base_name] = {'df': df, 'info': col_info, 'meta': meta_dict[base_name]}
        except Exception as e:
            on_log(f"❌ {base_name} 데이터 로드 실패: {e}")
            return

    on_progress(40)
    total_errors = 0
    
    on_log("🔍 2단계: 개체, 고유, Null, 도메인 무결성 검사 중...")
    for t_name, t_data in df_dict.items():
        df = t_data['df']
        info = t_data['info']
        meta = t_data['meta']
        
        # 1. 개체 무결성 (Entity Integrity)
        pk_cols = meta['primaryKey']
        missing_in_df = [p for p in pk_cols if p not in df.columns]
        if missing_in_df:
            on_log(f" ❌ [{t_name}] 개체 무결성: PK 컬럼 {missing_in_df} 이(가) 데이터에 존재하지 않습니다.")
            total_errors += 1
        else:
            if df[pk_cols].isna().any().any():
                on_log(f" ❌ [{t_name}] 개체 무결성: 기본키({pk_cols})에 빈 칸(NULL)이 존재합니다.")
                total_errors += 1
            if df.duplicated(subset=pk_cols).any():
                on_log(f" ❌ [{t_name}] 개체 무결성: 기본키({pk_cols}) 조합에 중복된 값이 존재합니다.")
                total_errors += 1

        for c_name, c_dict in info.items():
            if c_name not in df.columns: continue
            c_data = df[c_name]
            constraints = c_dict['constraints']
            
            # 5. Null 무결성
            if 'NOT NULL' in constraints:
                if c_data.isna().any():
                    on_log(f" ❌ [{t_name}] Null 무결성: '{c_name}' 컬럼에 빈 칸이 존재합니다.")
                    total_errors += 1
                    
            # 4. 고유 무결성
            if 'UNIQUE' in constraints:
                if c_data.dropna().duplicated().any():
                    on_log(f" ❌ [{t_name}] 고유 무결성: '{c_name}' 컬럼에 중복된 값이 존재합니다.")
                    total_errors += 1
                    
            # 3. 도메인 무결성 (기본적인 int 타입 검사 예시)
            c_type = c_dict['type'].lower()
            if 'int' in c_type and '[]' not in c_type:
                non_nulls = c_data.dropna()
                if not pd.to_numeric(non_nulls, errors='coerce').notnull().all():
                    on_log(f" ❌ [{t_name}] 도메인 무결성: '{c_name}' 컬럼에 정수(int)가 아닌 값이 포함되어 있습니다.")
                    total_errors += 1
                    
    on_progress(70)
                    
    # 2. 참조 무결성 (Referential Integrity)
    on_log("\n🔍 3단계: 참조 무결성(Foreign Key) 교차 검증 중...")
    for t_name, t_data in df_dict.items():
        df = t_data['df']
        fks = t_data['meta'].get('foreignKeys', {})
        
        for fk_name, fk_info in fks.items():
            local_cols = fk_info['columns']
            target_table = fk_info['targetTable']
            
            target_basename = os.path.basename(target_table)
            if target_basename not in df_dict:
                on_log(f" ❌ [{t_name}] 참조 무결성: 타겟 테이블 '{target_basename}'을(를) 찾을 수 없습니다.")
                total_errors += 1
                continue
                
            target_data = df_dict[target_basename]
            target_df = target_data['df']
            target_pk = target_data['meta']['primaryKey']
            
            if len(local_cols) != len(target_pk):
                on_log(f" ❌ [{t_name}] 참조 무결성: '{fk_name}'의 로컬 컬럼 개수({len(local_cols)})와 타겟 PK 개수({len(target_pk)})가 다릅니다.")
                total_errors += 1
                continue
            
            missing_locals = [c for c in local_cols if c not in df.columns]
            if missing_locals:
                on_log(f" ❌ [{t_name}] 참조 무결성: 로컬 매핑 컬럼 {missing_locals} 이(가) 존재하지 않습니다.")
                total_errors += 1
                continue

            local_subset = df[local_cols].dropna()
            if local_subset.empty: continue
            
            # 교차 데이터 값 비교
            local_tuples = set([tuple(x) for x in local_subset.to_numpy()])
            target_tuples = set([tuple(x) for x in target_df[target_pk].dropna().to_numpy()])
            
            invalid_refs = local_tuples - target_tuples
            if invalid_refs:
                on_log(f" ❌ [{t_name}] 참조 무결성: '{fk_name}'에서 유령 참조 값(없는 타겟 값) 발견 ➔ {list(invalid_refs)[:3]}")
                total_errors += 1
                
    on_progress(100)
    on_log("\n" + "="*50)
    if total_errors == 0:
        on_log("🎉 [검증 완료] 5대 무결성 위반 사항이 없습니다. 엔진 삽입이 준비되었습니다!")
    else:
        on_log(f"⚠️ [검증 실패] 총 {total_errors}건의 무결성 위반 사항이 발견되었습니다. 데이터를 수정해주세요.")
    on_log("="*50)
