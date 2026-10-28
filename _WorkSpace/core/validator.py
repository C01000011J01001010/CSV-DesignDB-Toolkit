import os
import json
import pandas as pd
import numpy as np
import re
from core.erd_generator import generate_erd_html
from core.registry_manager import (
    scan_available_registries,
    resolve_registry_for_binding,
    load_csvregi,
    get_registry_snapshot_at_revision,
    _normalize_id_token,
)

def parse_header(raw_str):
    name = str(raw_str).strip().lstrip('\ufeff')
    c_type = ""
    constraints = []
    is_schema = False
    if name.startswith('{') and name.endswith('}'):
        is_schema = True
        parts = [p.strip() for p in name[1:-1].split('/')]
        name = parts[0]
        if len(parts) > 1: c_type = parts[1].strip()
        if len(parts) > 2: constraints = [p.strip() for p in parts[2:]]
    return name, c_type, constraints, is_schema

def check_type(data_series, c_type_base):
    data_str = data_series.astype(str).str.strip()
    if c_type_base in ['int', 'assetid']: return data_str.str.match(r'^-?\d+$')
    elif c_type_base == 'float': return data_str.str.match(r'^-?\d+(\.\d+)?$')
    elif c_type_base == 'bool': return data_str.str.lower().isin(['true', 'false', '0', '1', '0.0', '1.0'])
    elif c_type_base in ['string', 'enum']: return pd.Series([True]*len(data_series), index=data_series.index)
    return pd.Series([False]*len(data_series), index=data_series.index)

def evaluate_check_expr(val, expr):
    try:
        val_str = str(val).strip()
        try:
            numeric_val = float(val_str)
            py_expr = expr.upper().replace("VALUE", str(numeric_val)).replace("AND", " and ").replace("OR", " or ")
        except ValueError:
            py_expr = expr.upper().replace("VALUE", f"'{val_str}'").replace("AND", " and ").replace("OR", " or ")
        if any(unsafe in py_expr.lower() for unsafe in ['import', 'exec', 'eval', 'os', 'sys']): return False
        return bool(eval(py_expr))
    except: return False

def format_errors(invalid_series, limit=3):
    total = len(invalid_series)
    items = []
    for idx, val in invalid_series.head(limit).items():
        row_num = idx + 2 
        items.append(f"{{행{row_num}: '{val}'}}")
    res = "[" + ", ".join(items) + "]"
    if total > limit: res += f" (외 {total - limit}건)"
    return res

def run_global_validation(
    workspace_root,
    on_log,
    on_progress,
    exclude_prefix="Disabled",
    project_name="Workspace",
    erd_output_path=None,
    extra_regi_paths=None
):
    csv_files = []
    for root, dirs, files in os.walk(workspace_root):
        rel_root = os.path.relpath(root, workspace_root)
        if rel_root != '.' and any(p.startswith(exclude_prefix) for p in rel_root.replace('\\', '/').split('/')):
            continue
            
        for file in files:
            if file.startswith(exclude_prefix):
                continue
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))

    if not csv_files:
        on_log("❌ 워크스페이스 내에 검증할 CSV 파일이 없습니다.")
        return False

    on_log("🔍 1단계: 메타데이터(.csvmeta) 및 기본키(PK) 설정 여부 확인 중...")
    missing_meta = []
    missing_pk = []
    meta_dict = {}
    df_dict = {}

    for csv_file in csv_files:
        json_file = os.path.splitext(csv_file)[0] + ".csvmeta"
        base_name = os.path.basename(csv_file)
        
        if not os.path.exists(json_file):
            missing_meta.append(base_name)
            continue
            
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                if not meta.get('primaryKey'): missing_pk.append(base_name)
                else: meta_dict[base_name] = meta
        except Exception:
            missing_meta.append(base_name)

    if missing_meta or missing_pk:
        on_log("\n🚨 [검증 중단] 유효한 메타데이터가 없는 테이블이 발견되었습니다.")
        on_log("다음 파일들은 [3. 추출] 및 [4. 메타 관리] 탭에서 기본키(PK)를 먼저 설정해야 무결성 검사가 가능합니다.\n")
        for f in missing_meta: on_log(f" ❌ {f} (.csvmeta 메타파일 누락 또는 파싱 실패)")
        for f in missing_pk: on_log(f" ❌ {f} (기본키 미설정)")
        return False

    on_log("✅ 모든 테이블의 메타데이터 확인 완료. 데이터 및 에셋 레지스트리(.csvregi) 로드 시작...\n")
    on_progress(20)

    available_registries = scan_available_registries(
        workspace_root, exclude_prefix=exclude_prefix, extra_paths=extra_regi_paths
    )
    regilog_snapshot_cache = {}
    
    file_errors = {}
    
    for csv_file in csv_files:
        base_name = os.path.basename(csv_file)
        if base_name not in meta_dict: continue
        file_errors[base_name] = [] 
        rel_path = os.path.relpath(csv_file, workspace_root).replace('\\', '/')
        regi_data = load_csvregi(csv_file)
        regi_bindings = regi_data.get('bindings', {})
        
        try:
            try: df = pd.read_csv(csv_file, encoding='utf-8-sig', dtype=str)
            except UnicodeDecodeError: df = pd.read_csv(csv_file, encoding='cp949', dtype=str)
            
            rename_map = {}
            col_info = {}
            for c in df.columns:
                c_name, c_type, constraints, is_schema = parse_header(c)
                rename_map[c] = c_name
                col_info[c_name] = {
                    'type': c_type,
                    'constraints': constraints,
                    'raw': c,
                    'is_schema': is_schema,
                    'regi_badge': None
                }
            
            df = df.rename(columns=rename_map)
            df_dict[base_name] = {
                'df': df,
                'info': col_info,
                'meta': meta_dict[base_name],
                'regi_bindings': regi_bindings,
                'rel_path': rel_path
            }
        except Exception as e:
            on_log(f"❌ {base_name} 데이터 로드 실패: {e}")
            return False

    on_progress(40)
    total_errors = 0
    on_log("🔍 2단계: 개체, 고유, Null, 도메인, 참조 및 에셋 레지스트리 무결성 통합 검사 가동 중...")
    
    for t_name, t_data in df_dict.items():
        df = t_data['df']
        info = t_data['info']
        meta = t_data['meta']
        regi_bindings = t_data.get('regi_bindings', {})
        
        pk_cols = meta['primaryKey']
        missing_in_df = [p for p in pk_cols if p not in df.columns]
        if missing_in_df:
            file_errors[t_name].append(f"[개체 무결성] PK 컬럼 {missing_in_df} 데이터 누락")
            total_errors += 1
        else:
            pk_null_mask = df[pk_cols].isna().any(axis=1)
            if pk_null_mask.any():
                invalid_series = pd.Series(["NULL"] * pk_null_mask.sum(), index=df[pk_null_mask].index)
                file_errors[t_name].append(f"[개체 무결성] 기본키({pk_cols}) 빈 칸(NULL) 존재 ➔ {format_errors(invalid_series)}")
                total_errors += 1
                
            pk_dup_mask = df.duplicated(subset=pk_cols, keep=False)
            if pk_dup_mask.any():
                invalid_df = df[pk_dup_mask][pk_cols]
                invalid_series = pd.Series([", ".join(x.astype(str)) for x in invalid_df.to_numpy()], index=invalid_df.index)
                file_errors[t_name].append(f"[개체 무결성] 기본키({pk_cols}) 중복 ➔ {format_errors(invalid_series)}")
                total_errors += 1

        # .csvregi 에 남아있는 불필요/구버전 컬럼 바인딩 검사
        for bound_col in regi_bindings.keys():
            if bound_col not in info or info[bound_col].get('type', '').replace('[]', '').lower() != 'assetid':
                file_errors[t_name].append(
                    f"[에셋 레지스트리 무결성] .csvregi 파일에 유효하지 않은 컬럼('{bound_col}') 바인딩이 남아있습니다. [2. 스키마 설정]에서 스키마 저장을 눌러 갱신해주세요."
                )
                total_errors += 1

        for c_name, c_dict in info.items():
            if c_name not in df.columns: continue
            if not c_dict.get('is_schema', False): continue

            c_data = df[c_name]
            constraints = c_dict['constraints']
            c_type_full = c_dict['type']
            
            if not c_type_full:
                file_errors[t_name].append(f"[도메인 무결성] '{c_name}' 컬럼 타입 미지정")
                total_errors += 1
                continue
                
            c_type_base = c_type_full.replace('[]', '').lower()
            is_array = '[]' in c_type_full
            valid_types = ['int', 'float', 'string', 'bool', 'enum', 'assetid']
            
            if c_type_base not in valid_types:
                file_errors[t_name].append(f"[도메인 무결성] '{c_name}' 알 수 없는 타입('{c_type_full}')")
                total_errors += 1
                continue

            non_nulls = c_data.dropna()
            
            if not non_nulls.empty:
                if is_array:
                    exploded = non_nulls.astype(str).str.split('|').explode().str.strip()
                    exploded = exploded[exploded != ""]
                    valid_mask = check_type(exploded, c_type_base)
                    if not valid_mask.all():
                        invalid_series = exploded[~valid_mask]
                        file_errors[t_name].append(f"[도메인 무결성] '{c_name}' 배열 형식 위반 ➔ {format_errors(invalid_series)}")
                        total_errors += 1
                else:
                    valid_mask = check_type(non_nulls, c_type_base)
                    if not valid_mask.all():
                        invalid_series = non_nulls[~valid_mask]
                        file_errors[t_name].append(f"[도메인 무결성] '{c_name}' '{c_type_base}' 형식 위반 ➔ {format_errors(invalid_series)}")
                        total_errors += 1

            # 🎨 에셋 레지스트리(.csvregi / .regimeta / .regilog) 무결성 검사
            if c_type_base == 'assetid':
                b_info = regi_bindings.get(c_name)
                if not b_info:
                    c_dict['regi_badge'] = {
                        'status': 'unbound',
                        'text': '레지스트리 미연결 (.csvregi 누락)'
                    }
                    file_errors[t_name].append(
                        f"[에셋 레지스트리 무결성] '{c_name}' ({c_type_full}) 컬럼에 연결된 에셋 레지스트리(.csvregi)가 없습니다. [2. 스키마 설정]에서 레지스트리를 지정해주세요."
                    )
                    total_errors += 1
                else:
                    matched_regi = resolve_registry_for_binding(b_info, available_registries, workspace_root)
                    if not matched_regi:
                        r_name = b_info.get('registryName', 'Unknown')
                        c_dict['regi_badge'] = {
                            'status': 'error',
                            'text': f"레지스트리 누락: {r_name} (.regimeta 없음)"
                        }
                        file_errors[t_name].append(
                            f"[에셋 레지스트리 무결성] '{c_name}' 컬럼이 참조하는 레지스트리('{r_name}')의 .regimeta 파일을 찾을 수 없습니다."
                        )
                        total_errors += 1
                    else:
                        r_name = matched_regi['registryName']
                        synced_rev = int(b_info.get('syncedRevision', 0))
                        curr_rev = int(matched_regi.get('currentRevision', 0))

                        if synced_rev < curr_rev:
                            c_dict['regi_badge'] = {
                                'status': 'outdated',
                                'text': f"레지스트리: {r_name} (동기화 필요: Rev {synced_rev} ➔ {curr_rev})"
                            }
                            file_errors[t_name].append(
                                f"[에셋 레지스트리 무결성] '{c_name}' 컬럼의 레지스트리('{r_name}') 버전이 구버전입니다 (테이블 Rev {synced_rev} < 유니티 Rev {curr_rev}). AssetID 동기화를 먼저 실행해주세요."
                            )
                            total_errors += 1
                        elif synced_rev > curr_rev:
                            c_dict['regi_badge'] = {
                                'status': 'error',
                                'text': f"레지스트리: {r_name} (리비전 역전: Rev {synced_rev} > {curr_rev})"
                            }
                            file_errors[t_name].append(
                                f"[에셋 레지스트리 무결성] '{c_name}' 컬럼의 레지스트리('{r_name}') 리비전 역전 감지 (테이블 Rev {synced_rev} > 유니티 Rev {curr_rev})."
                            )
                            total_errors += 1
                        else:
                            c_dict['regi_badge'] = {
                                'status': 'ok',
                                'text': f"레지스트리: {r_name} (Rev {curr_rev} ✅)"
                            }

                        # .regilog 스냅샷 로드 및 실제 AssetID 유효성/삭제 여부 대조
                        log_fp = matched_regi['logAbsPath']
                        cache_key = (log_fp, curr_rev)
                        if cache_key not in regilog_snapshot_cache:
                            regilog_snapshot_cache[cache_key] = get_registry_snapshot_at_revision(log_fp, curr_rev)
                        snap_ok, snap_data = regilog_snapshot_cache[cache_key]

                        if not snap_ok:
                            file_errors[t_name].append(
                                f"[에셋 레지스트리 무결성] '{c_name}' 컬럼이 참조하는 '{r_name}'의 .regilog 파일을 읽을 수 없습니다."
                            )
                            total_errors += 1
                            c_dict['regi_badge'] = {
                                'status': 'error',
                                'text': f"레지스트리: {r_name} (.regilog 읽기 실패)"
                            }
                        elif not non_nulls.empty:
                            active_ids = snap_data['active_ids']
                            deleted_ids = snap_data['deleted_ids']
                            del_idx, del_vals = [], []
                            ghost_idx, ghost_vals = [], []

                            for row_idx, cell_val in non_nulls.items():
                                raw_tokens = str(cell_val).split('|') if is_array else [str(cell_val)]
                                for tok_raw in raw_tokens:
                                    tok = _normalize_id_token(tok_raw)
                                    if tok == "" or tok == "0":
                                        continue
                                    if not re.match(r'^-?\d+$', tok):
                                        continue
                                    if int(tok) < 0:
                                        ghost_idx.append(row_idx)
                                        ghost_vals.append(f"{tok}(음수불가)")
                                    elif tok in active_ids:
                                        continue
                                    elif tok in deleted_ids:
                                        del_idx.append(row_idx)
                                        del_vals.append(f"ID {tok}('{deleted_ids[tok]}')")
                                    else:
                                        ghost_idx.append(row_idx)
                                        ghost_vals.append(f"ID {tok}")

                            if del_vals:
                                del_series = pd.Series(del_vals, index=del_idx)
                                file_errors[t_name].append(
                                    f"[에셋 레지스트리 무결성] '{c_name}' 삭제된 에셋(id=0) 참조 ({r_name}) ➔ {format_errors(del_series)}"
                                )
                                total_errors += 1
                                if c_dict['regi_badge']['status'] == 'ok':
                                    c_dict['regi_badge'] = {
                                        'status': 'error',
                                        'text': f"레지스트리: {r_name} (삭제된 에셋 참조 {len(del_vals)}건 ❌)"
                                    }

                            if ghost_vals:
                                ghost_series = pd.Series(ghost_vals, index=ghost_idx)
                                file_errors[t_name].append(
                                    f"[에셋 레지스트리 무결성] '{c_name}' 미등록 유령 AssetID 참조 ({r_name} Rev {curr_rev}) ➔ {format_errors(ghost_series)}"
                                )
                                total_errors += 1
                                if c_dict['regi_badge']['status'] == 'ok':
                                    c_dict['regi_badge'] = {
                                        'status': 'error',
                                        'text': f"레지스트리: {r_name} (유령 AssetID {len(ghost_vals)}건 ❌)"
                                    }

            if 'NOT NULL' in constraints:
                if c_data.isna().any():
                    invalid_series = pd.Series(["NULL"] * c_data.isna().sum(), index=c_data[c_data.isna()].index)
                    file_errors[t_name].append(f"[Null 무결성] '{c_name}' 빈 칸 존재 ➔ {format_errors(invalid_series)}")
                    total_errors += 1
                    
            if 'UNIQUE' in constraints:
                dup_mask = non_nulls.duplicated(keep=False)
                if dup_mask.any():
                    invalid_series = non_nulls[dup_mask]
                    file_errors[t_name].append(f"[고유 무결성] '{c_name}' 중복 존재 ➔ {format_errors(invalid_series)}")
                    total_errors += 1
                    
            if not non_nulls.empty:
                for const in constraints:
                    const_u = const.upper()
                    if const_u.startswith("CHECK IN(") and const.endswith(")"):
                        vals_str = const[len("CHECK IN("):-1]
                        allowed = [v.strip() for v in vals_str.split('|')]
                        items_to_check = non_nulls.astype(str).str.split('|').explode().str.strip() if is_array else non_nulls.astype(str).str.strip()
                        invalid_mask = ~items_to_check.isin(allowed)
                        if invalid_mask.any():
                            invalid_series = items_to_check[invalid_mask]
                            file_errors[t_name].append(f"[도메인 무결성] '{c_name}' CHECK IN({vals_str}) 위반 ➔ {format_errors(invalid_series)}")
                            total_errors += 1
                    elif const_u.startswith("CHECK NOT IN(") and const.endswith(")"):
                        vals_str = const[len("CHECK NOT IN("):-1]
                        disallowed = [v.strip() for v in vals_str.split('|')]
                        items_to_check = non_nulls.astype(str).str.split('|').explode().str.strip() if is_array else non_nulls.astype(str).str.strip()
                        invalid_mask = items_to_check.isin(disallowed)
                        if invalid_mask.any():
                            invalid_series = items_to_check[invalid_mask]
                            file_errors[t_name].append(f"[도메인 무결성] '{c_name}' CHECK NOT IN 위반 ➔ 금지된 값: {format_errors(invalid_series)}")
                            total_errors += 1
                    elif const_u.startswith("CHECK(") and const.endswith(")"):
                        expr = const[len("CHECK("):-1]
                        items_to_check = non_nulls.astype(str).str.split('|').explode().str.strip() if is_array else non_nulls
                        failed_idx, failed_vals = [], []
                        for idx, val in items_to_check.items():
                            if not evaluate_check_expr(val, expr):
                                failed_idx.append(idx)
                                failed_vals.append(str(val))
                        if failed_vals:
                            invalid_series = pd.Series(failed_vals, index=failed_idx)
                            file_errors[t_name].append(f"[도메인 무결성] '{c_name}' CHECK({expr}) 위반 ➔ {format_errors(invalid_series)}")
                            total_errors += 1
                            
    on_progress(70)
    
    fk_edges = []
    for t_name, t_data in df_dict.items():
        df = t_data['df']
        fks = t_data['meta'].get('foreignKeys', {})
        for fk_name, fk_info in fks.items():
            local_cols = fk_info.get('columns', [])
            target_table = fk_info.get('targetTable', '')
            target_basename = os.path.basename(target_table)
            
            if target_basename not in df_dict:
                file_errors[t_name].append(f"[참조 무결성] '{fk_name}' 타겟 테이블 '{target_basename}' 없음")
                total_errors += 1
                fk_edges.append({
                    'from': t_name,
                    'to': target_basename or '(미지정)',
                    'fk_name': fk_name,
                    'local_cols': local_cols,
                    'target_cols': [],
                    'is_valid': False,
                    'error_msg': '타겟 테이블 없음'
                })
                continue
                
            target_data = df_dict[target_basename]
            target_df = target_data['df']
            target_pk = target_data['meta']['primaryKey']
            
            if len(local_cols) != len(target_pk):
                file_errors[t_name].append(f"[참조 무결성] '{fk_name}' 매핑 개수 불일치 (로컬 {len(local_cols)}개 vs 타겟 PK {len(target_pk)}개)")
                total_errors += 1
                fk_edges.append({
                    'from': t_name,
                    'to': target_basename,
                    'fk_name': fk_name,
                    'local_cols': local_cols,
                    'target_cols': target_pk,
                    'is_valid': False,
                    'error_msg': '매핑 개수 불일치'
                })
                continue
            
            missing_locals = [c for c in local_cols if c not in df.columns]
            if missing_locals:
                file_errors[t_name].append(f"[참조 무결성] 로컬 매핑 컬럼 {missing_locals} 존재하지 않음")
                total_errors += 1
                fk_edges.append({
                    'from': t_name,
                    'to': target_basename,
                    'fk_name': fk_name,
                    'local_cols': local_cols,
                    'target_cols': target_pk,
                    'is_valid': False,
                    'error_msg': '로컬 컬럼 누락'
                })
                continue

            local_subset = df[local_cols].dropna()
            if local_subset.empty:
                fk_edges.append({
                    'from': t_name,
                    'to': target_basename,
                    'fk_name': fk_name,
                    'local_cols': local_cols,
                    'target_cols': target_pk,
                    'is_valid': True,
                    'error_msg': ''
                })
                continue
            
            target_tuples = set([tuple(x) for x in target_df[target_pk].dropna().to_numpy()])
            invalid_mask = ~local_subset.apply(tuple, axis=1).isin(target_tuples)
            
            if invalid_mask.any():
                invalid_df = local_subset[invalid_mask]
                invalid_series = pd.Series([", ".join(x.astype(str)) for x in invalid_df.to_numpy()], index=invalid_df.index)
                file_errors[t_name].append(f"[참조 무결성] '{fk_name}' 유령 참조 값(없는 타겟) 발견 ➔ {format_errors(invalid_series)}")
                total_errors += 1
                fk_edges.append({
                    'from': t_name,
                    'to': target_basename,
                    'fk_name': fk_name,
                    'local_cols': local_cols,
                    'target_cols': target_pk,
                    'is_valid': False,
                    'error_msg': f"유령 참조({invalid_mask.sum()}건)"
                })
            else:
                fk_edges.append({
                    'from': t_name,
                    'to': target_basename,
                    'fk_name': fk_name,
                    'local_cols': local_cols,
                    'target_cols': target_pk,
                    'is_valid': True,
                    'error_msg': ''
                })

    on_progress(90)
    on_log("\n🔍 3단계: 검증 결과 리포트 및 참조 관계도(ERD) 생성 중...")
    
    if total_errors > 0:
        for t_name, err_list in file_errors.items():
            if err_list:
                on_log("\n\n\n" + "━"*60) 
                on_log(f"📁 대상 파일: {t_name} (총 {len(err_list)}건 위반)")
                on_log("-" * 60)
                for err in err_list:
                    on_log(f"  ❌ {err}")

    erd_success = False
    if erd_output_path:
        try:
            generate_erd_html(workspace_root, project_name, df_dict, file_errors, fk_edges, erd_output_path)
            erd_success = True
            on_log(f"\n📊 [ERD 생성 완료] 참조 관계도 HTML 파일이 갱신되었습니다: {os.path.basename(erd_output_path)}")
        except Exception as e:
            on_log(f"\n⚠️ [ERD 생성 실패] 관계도 파일 생성 중 오류 발생: {e}")

    on_progress(100)
    on_log("\n\n" + "="*60)
    if total_errors == 0:
        on_log("🎉 [검증 완료] 5대 무결성 및 에셋 레지스트리 위반 사항이 없습니다. 엔진 삽입이 준비되었습니다!")
    else:
        on_log(f"⚠️ [검증 실패] 전체 워크스페이스에서 총 {total_errors}건의 위반 사항이 발견되었습니다. 데이터를 수정해주세요.")
    on_log("="*60)
    return erd_success
