import os
import json
import pandas as pd

def analyze_pk_status(target_dir, include_subdirs, on_log):
    csv_files = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
        if not include_subdirs: dirs.clear()
        for file in files:
            if file.startswith('Disabled'): continue
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        on_log("❌ 검사할 CSV 파일을 찾을 수 없습니다.")
        return

    needs_json = []
    needs_pk_reselection = []
    ok_files = []

    for csv_file in csv_files:
        base_name = os.path.splitext(os.path.basename(csv_file))[0]
        json_file = os.path.join(os.path.dirname(csv_file), f"{base_name}.json")

        if not os.path.exists(json_file):
            needs_json.append(base_name)
            continue

        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding='cp949')
        except Exception as e:
            on_log(f"❌ 읽기 실패: {base_name}.csv")
            continue

        c_keys_data = {}
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                c_keys_data = json.load(f)
                c_keys = [set(k['columns']) for k in c_keys_data.get('candidateKeys', [])]
            except Exception:
                c_keys = []

        pk_cols = []
        pk_valid = True
        pk_error_reasons = []

        for col in df.columns:
            col_str = str(col).strip()
            if col_str.startswith('{') and col_str.endswith('}'):
                parts = [p.strip() for p in col_str[1:-1].split('/')]
                c_name = parts[0]
                c_type = parts[1].lower() if len(parts) > 1 else "string"
                constraints = [p.upper() for p in parts[2:]]

                if "PK" in constraints or "PRIMARYKEY" in constraints:
                    pk_cols.append(c_name)
                    if "[]" in c_type:
                        pk_valid = False
                        pk_error_reasons.append(f"{c_name}(배열 타입 불가)")
                    elif c_type not in ['int', 'string', 'bool', 'enum']:
                        pk_valid = False
                        pk_error_reasons.append(f"{c_name}(허용되지 않은 타입: {c_type})")
                    elif c_type == 'string':
                        if df[col].astype(str).str.contains('_').any():
                            pk_valid = False
                            pk_error_reasons.append(f"{c_name}(데이터 내 '_' 포함)")

        recommendation_str = ""
        if c_keys_data.get('candidateKeys'):
            sorted_keys = sorted(c_keys_data['candidateKeys'], key=lambda x: len(x['columns']))
            recommendation_str = f" [💡추천 조합: {', '.join(sorted_keys[0]['columns'])}]"

        if not pk_cols:
            needs_pk_reselection.append((base_name, f"PK가 지정되지 않음{recommendation_str}"))
        elif not pk_valid:
            needs_pk_reselection.append((base_name, f"PK 규칙 위반 [{', '.join(pk_error_reasons)}]{recommendation_str}"))
        else:
            pk_set = set(pk_cols)
            if pk_set not in c_keys:
                needs_pk_reselection.append((base_name, f"지정된 PK({', '.join(pk_cols)})가 JSON 후보키에 없음{recommendation_str}"))
            else:
                ok_files.append(base_name)

    on_log("\n" + "="*50)
    on_log("📊 [PK 상태 검사 및 검증 결과]")
    on_log("="*50)

    if needs_json:
        on_log("\n🚨 [우선 처리 요망] JSON 파일 누락")
        on_log("   👉 아래 파일들은 '3. 최소 후보키 탐색' 작업을 먼저 실행해 JSON을 생성해야 합니다.")
        for f in needs_json:
            on_log(f"   - {f}.csv")

    if needs_pk_reselection:
        on_log("\n🔄 [PK 재선정 필요 대상] 리스트업 및 추천")
        for f, reason in needs_pk_reselection:
            on_log(f"   - {f}.csv : {reason}")
            
    if ok_files:
        on_log("\n✅ [정상] PK 설정 검증 통과")
        for f in ok_files:
            on_log(f"   - {f}.csv")

    on_log("\n" + "="*50)
