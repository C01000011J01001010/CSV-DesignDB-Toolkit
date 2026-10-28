import os
import json
import csv
import openpyxl
from core.excel_editor import find_schema_bounds
from core.converter import convert_xlsx_file

CSVREGI_EXT = ".csvregi"
REGIMETA_FILENAME = ".regimeta"
REGILOG_FILENAME = ".regilog"

IGNORED_UNITY_DIRS = {
    ".git", ".svn", ".vs", ".idea", "__pycache__",
    "Library", "Temp", "Obj", "obj", "Logs", "UserSettings", "Packages", "Builds"
}


def get_csvregi_path(table_filepath):
    """엑셀(.xlsx) 또는 CSV(.csv) 경로로부터 대응하는 .csvregi 파일 경로를 반환합니다."""
    base, _ = os.path.splitext(table_filepath)
    return base + CSVREGI_EXT


def find_unity_assets_root(start_dir):
    """
    주어진 경로의 상위 또는 하위에서 Unity 프로젝트의 Assets 루트 폴더를 탐색합니다.
    찾지 못하면 None을 반환합니다.
    """
    if not start_dir:
        return None

    curr = os.path.abspath(start_dir)
    while True:
        folder_name = os.path.basename(curr)
        parent_dir = os.path.dirname(curr)
        if folder_name.lower() == "assets":
            if os.path.isdir(os.path.join(parent_dir, "ProjectSettings")) or os.path.isdir(os.path.join(parent_dir, "Packages")):
                return curr
        assets_candidate = os.path.join(curr, "Assets")
        if os.path.isdir(assets_candidate) and os.path.isdir(os.path.join(curr, "ProjectSettings")):
            return assets_candidate

        if parent_dir == curr:
            break
        curr = parent_dir

    return None


def parse_regimeta_file(meta_filepath, workspace_root=None):
    """단일 .regimeta 파일을 파싱하여 메타 정보 딕셔너리를 반환합니다."""
    if not meta_filepath or not os.path.isfile(meta_filepath):
        return None
    try:
        with open(meta_filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None

        regi_name = str(data.get("registryName", "")).strip()
        regi_guid = str(data.get("registrySoGuid", "")).strip()
        asset_type = str(data.get("assetType", "UnityEngine.Object")).strip()
        short_type = asset_type.split(".")[-1] if asset_type else "Object"
        current_rev = int(data.get("currentRevision", 0))
        last_baked = str(data.get("lastBakedUtc", "")).strip()

        abs_meta = os.path.abspath(meta_filepath)
        rel_meta = abs_meta.replace("\\", "/")
        if workspace_root:
            try:
                rel_meta = os.path.relpath(abs_meta, workspace_root).replace("\\", "/")
            except ValueError:
                rel_meta = abs_meta.replace("\\", "/")

        if not regi_name:
            regi_name = os.path.basename(os.path.dirname(abs_meta)) or "UnnamedRegistry"

        display_label = f"{regi_name} ({short_type}) [Rev {current_rev}]"

        return {
            "registryName": regi_name,
            "registrySoGuid": regi_guid,
            "assetType": asset_type,
            "shortType": short_type,
            "currentRevision": current_rev,
            "lastBakedUtc": last_baked,
            "metaAbsPath": abs_meta.replace("\\", "/"),
            "regiMetaPath": rel_meta,
            "logAbsPath": os.path.join(os.path.dirname(abs_meta), REGILOG_FILENAME).replace("\\", "/"),
            "displayLabel": display_label,
        }
    except Exception:
        return None


def scan_available_registries(workspace_root, exclude_prefix="Disabled", extra_paths=None):
    """
    워크스페이스 루트(및 감지된 Unity Assets 폴더, 추가 등록 경로)를 스캔하여
    사용 가능한 모든 .regimeta 목록을 반환합니다.
    """
    if not workspace_root:
        return []

    scan_roots = []
    abs_ws = os.path.abspath(workspace_root)
    unity_assets = find_unity_assets_root(abs_ws)
    if unity_assets:
        scan_roots.append(unity_assets)
    if not unity_assets or not abs_ws.startswith(unity_assets):
        scan_roots.append(abs_ws)

    found_by_key = {}

    for root_dir in scan_roots:
        if not os.path.isdir(root_dir):
            continue
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [
                d for d in dirs
                if d not in IGNORED_UNITY_DIRS
                and not (exclude_prefix and d.startswith(exclude_prefix))
            ]
            if REGIMETA_FILENAME in files:
                meta_fp = os.path.join(root, REGIMETA_FILENAME)
                info = parse_regimeta_file(meta_fp, workspace_root)
                if info:
                    key = info["registrySoGuid"] or info["metaAbsPath"]
                    found_by_key[key] = info

    if extra_paths:
        for p in extra_paths:
            if not p:
                continue
            cand = p if os.path.isabs(p) else os.path.normpath(os.path.join(workspace_root, p))
            if os.path.isdir(cand):
                cand = os.path.join(cand, REGIMETA_FILENAME)
            info = parse_regimeta_file(cand, workspace_root)
            if info:
                key = info["registrySoGuid"] or info["metaAbsPath"]
                found_by_key[key] = info

    result = list(found_by_key.values())
    result.sort(key=lambda x: (x["registryName"].lower(), x["metaAbsPath"].lower()))
    return result


def resolve_registry_for_binding(bound_info, available_registries, workspace_root=None):
    """
    .csvregi의 단일 컬럼 바인딩 정보로부터 실제 .regimeta 정보를 찾습니다.
    1순위: registrySoGuid 일치
    2순위: regiMetaPath 상대/절대 경로 직접 파싱 또는 일치
    3순위: registryName 일치
    """
    if not bound_info or not isinstance(bound_info, dict):
        return None

    target_guid = str(bound_info.get("registrySoGuid", "")).strip()
    target_path = str(bound_info.get("regiMetaPath", "")).strip().replace("\\", "/")
    target_name = str(bound_info.get("registryName", "")).strip()

    if target_guid:
        for r in available_registries:
            if r["registrySoGuid"] == target_guid:
                return r

    if target_path:
        for r in available_registries:
            if r["regiMetaPath"] == target_path or r["metaAbsPath"] == target_path:
                return r
        # 스캔 목록에 없더라도 상대 경로 파일이 실제로 존재하면 직접 파싱
        if workspace_root:
            cand_abs = target_path if os.path.isabs(target_path) else os.path.normpath(os.path.join(workspace_root, target_path))
            direct_info = parse_regimeta_file(cand_abs, workspace_root)
            if direct_info:
                if not target_guid or direct_info["registrySoGuid"] == target_guid:
                    return direct_info

    if target_name:
        for r in available_registries:
            if r["registryName"] == target_name:
                return r

    return None


def load_csvregi(table_filepath):
    """테이블의 .csvregi 파일을 읽어 딕셔너리로 반환합니다. 파일이 없으면 기본 구조를 반환합니다."""
    regi_path = get_csvregi_path(table_filepath)
    base_csv_name = os.path.splitext(os.path.basename(table_filepath))[0] + ".csv"
    default_data = {
        "tableFileName": base_csv_name,
        "bindings": {}
    }
    if not os.path.isfile(regi_path):
        return default_data

    try:
        with open(regi_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_data
        if "bindings" not in data or not isinstance(data["bindings"], dict):
            data["bindings"] = {}
        data["tableFileName"] = base_csv_name
        return data
    except Exception:
        return default_data


def save_csvregi(table_filepath, bindings_dict):
    """
    테이블의 AssetID 컬럼 바인딩 정보를 .csvregi 파일로 저장합니다.
    바인딩된 AssetID 컬럼이 하나도 없으면 기존 .csvregi 파일을 삭제하여 깔끔하게 유지합니다.
    """
    regi_path = get_csvregi_path(table_filepath)
    if not bindings_dict:
        if os.path.isfile(regi_path):
            try:
                os.remove(regi_path)
            except Exception as e:
                return False, str(e)
        return True, "removed"

    base_csv_name = os.path.splitext(os.path.basename(table_filepath))[0] + ".csv"
    payload = {
        "tableFileName": base_csv_name,
        "bindings": bindings_dict
    }
    temp_path = regi_path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, regi_path)
        return True, regi_path
    except Exception as e:
        if os.path.isfile(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False, str(e)


# ==============================================================================
# Step 3: .regilog 파싱, GUID 기반 Delta Mapping 및 1-Pass 테이블 동기화 엔진
# ==============================================================================

def parse_regilog_file(log_filepath):
    """단일 .regilog JSON 파일을 읽어 파싱된 딕셔너리를 반환합니다."""
    if not log_filepath or not os.path.isfile(log_filepath):
        return None
    try:
        with open(log_filepath, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        if "assets" not in data or not isinstance(data["assets"], list):
            data["assets"] = []
        return data
    except Exception:
        return None


def get_asset_id_at_revision(history_list, target_rev):
    """
    특정 에셋의 history 리스트에서 target_rev 시점에 유효했던 에셋 ID(int)를 반환합니다.
    (entry.rev <= target_rev 를 만족하는 가장 최신 엔트리의 id. 없으면 0)
    """
    if not history_list or not isinstance(history_list, list):
        return 0
    best_rev = -1
    best_id = 0
    for entry in history_list:
        if not isinstance(entry, dict):
            continue
        try:
            r = int(entry.get("rev", -1))
            aid = int(entry.get("id", 0))
        except (ValueError, TypeError):
            continue
        if r <= target_rev and r >= best_rev:
            best_rev = r
            best_id = aid
    return best_id if best_id > 0 else 0


def build_revision_delta_map(log_filepath, old_rev, new_rev):
    """
    .regilog 파일을 분석하여 old_rev -> new_rev 사이의 GUID 매개 상태 전이 맵을 구축합니다.
    반환값: (success, result_dict_or_error_msg)
    result_dict 구조:
      - replace_map: { old_id_str: new_id_str } (변경된 ID만 포함, 1-Pass 치환용)
      - asset_names: { old_id_str: lastKnownName }
      - deleted_map: { old_id_str: lastKnownName } (old_rev에선 존재했으나 new_rev에서 0이 된 에셋)
      - active_new_ids: { new_id_str: lastKnownName } (new_rev 기준 살아있는 모든 에셋 ID)
    """
    log_data = parse_regilog_file(log_filepath)
    if not log_data:
        return False, f".regilog 파일을 읽을 수 없습니다: {log_filepath}"

    replace_map = {}
    asset_names = {}
    deleted_map = {}
    active_new_ids = {}

    for record in log_data.get("assets", []):
        if not isinstance(record, dict):
            continue
        last_name = str(record.get("lastKnownName", "")).strip() or record.get("guid", "Unknown")
        history = record.get("history", [])

        old_id = get_asset_id_at_revision(history, old_rev)
        new_id = get_asset_id_at_revision(history, new_rev)

        if new_id > 0:
            active_new_ids[str(new_id)] = last_name

        if old_id > 0:
            old_str = str(old_id)
            asset_names[old_str] = last_name
            if new_id > 0:
                new_str = str(new_id)
                if old_str != new_str:
                    replace_map[old_str] = new_str
            else:
                # 이전에 존재했으나 삭제(또는 ID 회수)되어 id == 0 이 된 케이스
                deleted_map[old_str] = last_name

    # 만약 old_id가 삭제되었는데 다른 신규 에셋이 우연히 그 번호를 새로 차지한 경우,
    # GUID 기준으로는 해당 에셋이 변경/삭제된 것이므로 replace_map이 우선하며,
    # replace_map에 이미 등록된 old_id는 deleted_map에서 제외
    for k in list(deleted_map.keys()):
        if k in replace_map:
            del deleted_map[k]

    return True, {
        "replace_map": replace_map,
        "asset_names": asset_names,
        "deleted_map": deleted_map,
        "active_new_ids": active_new_ids,
    }


def _parse_schema_header_token(raw_header):
    """'{colName/AssetID[]/NOT NULL}' -> (colName, colType, is_schema)"""
    s = str(raw_header).strip().lstrip("\ufeff")
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].strip()
    if s.startswith("{") and s.endswith("}"):
        parts = [p.strip() for p in s[1:-1].split("/")]
        c_name = parts[0] if parts else ""
        c_type = parts[1].strip() if len(parts) > 1 else ""
        return c_name, c_type, True
    return s, "", False


def _normalize_id_token(token_str):
    """'101.0' (엑셀 float 문자열화 방지) 또는 ' 101 ' -> '101'"""
    t = str(token_str).strip()
    if t.endswith(".0") and t[:-2].lstrip("-").isdigit():
        t = t[:-2]
    return t


def transform_cell_value_one_pass(raw_val, is_array, replace_map, deleted_map, asset_names):
    """
    단일 셀 값을 1-Pass로 변환합니다.
    반환값: (changed: bool, new_val_str: str, change_notes: list[str], deleted_notes: list[str])
    """
    if raw_val is None:
        return False, "", [], []
    raw_str = str(raw_val).strip()
    if raw_str == "" or raw_str.lower() == "nan":
        return False, "", [], []

    change_notes = []
    deleted_notes = []

    if is_array:
        tokens = raw_str.split("|")
        new_tokens = []
        changed = False
        for tok in tokens:
            t_norm = _normalize_id_token(tok)
            if t_norm == "" or t_norm == "0":
                new_tokens.append(t_norm if t_norm else tok.strip())
                continue
            if t_norm in replace_map:
                new_t = replace_map[t_norm]
                new_tokens.append(new_t)
                changed = True
                a_name = asset_names.get(t_norm, "")
                change_notes.append(f"{t_norm}➔{new_t}" + (f"({a_name})" if a_name else ""))
            else:
                new_tokens.append(t_norm)
                if t_norm in deleted_map:
                    deleted_notes.append(f"ID {t_norm}('{deleted_map[t_norm]}')")
        new_val_str = "|".join(new_tokens)
        return changed, new_val_str, change_notes, deleted_notes
    else:
        t_norm = _normalize_id_token(raw_str)
        if t_norm == "" or t_norm == "0":
            return False, t_norm, [], []
        if t_norm in replace_map:
            new_t = replace_map[t_norm]
            a_name = asset_names.get(t_norm, "")
            change_notes.append(f"{t_norm}➔{new_t}" + (f"({a_name})" if a_name else ""))
            return True, new_t, change_notes, []
        else:
            if t_norm in deleted_map:
                deleted_notes.append(f"ID {t_norm}('{deleted_map[t_norm]}')")
            return False, t_norm, [], deleted_notes


def check_files_writable(filepaths):
    """
    주어진 파일 목록 중 엑셀이나 외부 프로그램에 의해 열려 있어 쓰기가 불가능한(잠긴) 파일 목록을 반환합니다.
    """
    locked = []
    for fp in filepaths:
        if not fp or not os.path.isfile(fp):
            continue
        try:
            with open(fp, "r+b"):
                pass
        except PermissionError:
            locked.append(fp)
        except OSError:
            locked.append(fp)
    return locked


def _sync_single_xlsx_table(xlsx_path, col_sync_plans, on_log, rel_display):
    """
    원본 .xlsx 파일의 스키마 바운딩 박스 내 대상 컬럼들을 1-Pass 치환하고,
    convert_xlsx_file을 호출하여 .csv까지 동시 갱신합니다.
    반환값: (success: bool, updated_cells_count: int, deleted_warning_count: int)
    """
    try:
        wb = openpyxl.load_workbook(xlsx_path)
        sheet = wb.active
        header_row_idx, start_col, end_col = find_schema_bounds(sheet)
        if header_row_idx is None:
            wb.close()
            on_log(f"  ❌ [{rel_display}] 엑셀에서 스키마 행({{}})을 찾을 수 없습니다.")
            return False, 0, 0

        # 컬럼명 -> (엑셀 열 인덱스, is_array) 매핑
        col_index_map = {}
        for c_idx in range(start_col, end_col + 1):
            cell_val = sheet.cell(row=header_row_idx, column=c_idx).value
            c_name, c_type, is_schema = _parse_schema_header_token(cell_val if cell_val is not None else "")
            if is_schema and c_name:
                col_index_map[c_name] = (c_idx, "[]" in c_type)

        total_updated_cells = 0
        total_deleted_warnings = 0
        max_row = sheet.max_row

        for col_name, plan in col_sync_plans.items():
            if col_name not in col_index_map:
                on_log(f"  ⚠️ [{rel_display}] '{col_name}' 컬럼이 엑셀 스키마에 존재하지 않아 건너뜁니다.")
                continue

            c_idx, is_array = col_index_map[col_name]
            replace_map = plan["replace_map"]
            deleted_map = plan["deleted_map"]
            asset_names = plan["asset_names"]

            col_updated = 0
            for r_idx in range(header_row_idx + 1, max_row + 1):
                # 행 전체가 비어있는지 확인
                cell = sheet.cell(row=r_idx, column=c_idx)
                changed, new_val_str, c_notes, d_notes = transform_cell_value_one_pass(
                    cell.value, is_array, replace_map, deleted_map, asset_names
                )
                if changed:
                    if not is_array and new_val_str.isdigit():
                        cell.value = int(new_val_str)
                    else:
                        cell.value = new_val_str
                    col_updated += 1
                    total_updated_cells += 1
                    if col_updated <= 15:
                        on_log(f"     • [엑셀 {r_idx}행] {col_name}: {', '.join(c_notes)}")
                if d_notes:
                    total_deleted_warnings += len(d_notes)
                    on_log(f"     🚨 [엑셀 {r_idx}행] {col_name} 삭제된 에셋(id=0) 참조 감지: {', '.join(d_notes)}")

            if col_updated > 15:
                on_log(f"     • ... 외 {col_updated - 15}개 셀 추가 치환됨")

        if total_updated_cells > 0:
            wb.save(xlsx_path)
        wb.close()

        # 엑셀이 수정되었거나 CSV가 없으면 CSV로 크롭/변환 실행
        csv_path = os.path.splitext(xlsx_path)[0] + ".csv"
        if total_updated_cells > 0 or not os.path.isfile(csv_path):
            ok, err = convert_xlsx_file(xlsx_path)
            if not ok:
                on_log(f"  ❌ [{rel_display}] 엑셀 저장 후 CSV 변환 실패: {err}")
                return False, total_updated_cells, total_deleted_warnings

        return True, total_updated_cells, total_deleted_warnings
    except Exception as e:
        on_log(f"  ❌ [{rel_display}] 엑셀 패치 중 예외 발생: {e}")
        return False, 0, 0


def _sync_single_csv_only_table(csv_path, col_sync_plans, on_log, rel_display):
    """
    원본 .xlsx 없이 .csv만 존재하는 테이블의 대상 컬럼들을 1-Pass 치환합니다.
    반환값: (success: bool, updated_cells_count: int, deleted_warning_count: int)
    """
    try:
        rows = []
        encoding_used = "utf-8-sig"
        try:
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
        except UnicodeDecodeError:
            encoding_used = "cp949"
            with open(csv_path, "r", encoding="cp949", newline="") as f:
                rows = list(csv.reader(f))

        if not rows:
            return True, 0, 0

        headers = rows[0]
        col_index_map = {}
        for idx, h in enumerate(headers):
            c_name, c_type, is_schema = _parse_schema_header_token(h)
            if c_name:
                col_index_map[c_name] = (idx, "[]" in c_type)

        total_updated_cells = 0
        total_deleted_warnings = 0

        for col_name, plan in col_sync_plans.items():
            if col_name not in col_index_map:
                on_log(f"  ⚠️ [{rel_display}] '{col_name}' 컬럼이 CSV 헤더에 존재하지 않아 건너뜁니다.")
                continue

            c_idx, is_array = col_index_map[col_name]
            replace_map = plan["replace_map"]
            deleted_map = plan["deleted_map"]
            asset_names = plan["asset_names"]

            col_updated = 0
            for r_idx in range(1, len(rows)):
                row = rows[r_idx]
                if c_idx >= len(row):
                    continue
                changed, new_val_str, c_notes, d_notes = transform_cell_value_one_pass(
                    row[c_idx], is_array, replace_map, deleted_map, asset_names
                )
                if changed:
                    row[c_idx] = new_val_str
                    col_updated += 1
                    total_updated_cells += 1
                    if col_updated <= 15:
                        on_log(f"     • [CSV {r_idx + 1}행] {col_name}: {', '.join(c_notes)}")
                if d_notes:
                    total_deleted_warnings += len(d_notes)
                    on_log(f"     🚨 [CSV {r_idx + 1}행] {col_name} 삭제된 에셋(id=0) 참조 감지: {', '.join(d_notes)}")

            if col_updated > 15:
                on_log(f"     • ... 외 {col_updated - 15}개 셀 추가 치환됨")

        if total_updated_cells > 0:
            temp_csv = csv_path + ".tmp"
            with open(temp_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                writer.writerows(rows)
            os.replace(temp_csv, csv_path)

        return True, total_updated_cells, total_deleted_warnings
    except Exception as e:
        on_log(f"  ❌ [{rel_display}] CSV 패치 중 예외 발생: {e}")
        return False, 0, 0


def run_asset_id_synchronization(
    workspace_root,
    on_log,
    on_progress=None,
    exclude_prefix="Disabled",
    extra_paths=None,
    target_table_filepath=None
):
    """
    워크스페이스 전역(또는 target_table_filepath 단일 테이블)의 .csvregi를 검사하여
    .regimeta / .regilog 리비전 변경분을 1-Pass로 안전하게 동기화합니다.
    반환값: dict (summary 결과)
    """
    summary = {
        "success": False,
        "locked_files": [],
        "synced_tables": 0,
        "up_to_date_tables": 0,
        "updated_cells": 0,
        "deleted_warnings": 0,
        "errors": 0,
    }

    if not workspace_root or not os.path.isdir(workspace_root):
        on_log("❌ 유효한 워크스페이스 경로가 아닙니다.")
        return summary

    available_registries = scan_available_registries(
        workspace_root, exclude_prefix=exclude_prefix, extra_paths=extra_paths
    )

    # 1. 대상 .csvregi 파일 수집
    csvregi_files = []
    if target_table_filepath:
        regi_fp = get_csvregi_path(target_table_filepath)
        if os.path.isfile(regi_fp):
            csvregi_files.append(regi_fp)
        else:
            on_log(f"ℹ️ '{os.path.basename(target_table_filepath)}' 테이블에 연결된 .csvregi 파일이 없습니다.")
            summary["success"] = True
            return summary
    else:
        for root, dirs, files in os.walk(workspace_root):
            rel_root = os.path.relpath(root, workspace_root)
            if rel_root != "." and any(p.startswith(exclude_prefix) for p in rel_root.replace("\\", "/").split("/")):
                continue
            for file in files:
                if file.startswith(exclude_prefix) or file.startswith("~$"):
                    continue
                if file.endswith(CSVREGI_EXT):
                    csvregi_files.append(os.path.join(root, file))

    if not csvregi_files:
        on_log("ℹ️ 워크스페이스 내에 에셋 바인딩(.csvregi) 파일이 없습니다.")
        if on_progress:
            on_progress(100)
        summary["success"] = True
        return summary

    on_log(f"🔍 총 {len(csvregi_files)}개의 .csvregi 바인딩 파일 리비전 상태 점검 중...")

    # 2. 동기화가 필요한 테이블 및 델타 플랜 수집 + 잠금 검사 대상 파일 파악
    table_jobs = []
    files_to_lock_check = []

    for regi_fp in sorted(csvregi_files):
        base_no_ext = os.path.splitext(regi_fp)[0]
        xlsx_fp = base_no_ext + ".xlsx"
        csv_fp = base_no_ext + ".csv"
        rel_display = os.path.relpath(base_no_ext, workspace_root).replace("\\", "/")

        regi_data = load_csvregi(regi_fp)
        bindings = regi_data.get("bindings", {})
        if not bindings:
            continue

        col_sync_plans = {}
        table_has_error = False
        table_needs_sync = False

        for col_name, b_info in bindings.items():
            matched_regi = resolve_registry_for_binding(b_info, available_registries, workspace_root)
            if not matched_regi:
                r_name = b_info.get("registryName", "Unknown")
                on_log(f"  ❌ [{rel_display}] '{col_name}' 컬럼의 레지스트리('{r_name}') .regimeta 파일을 찾을 수 없습니다.")
                summary["errors"] += 1
                table_has_error = True
                continue

            synced_rev = int(b_info.get("syncedRevision", 0))
            curr_rev = int(matched_regi.get("currentRevision", 0))
            r_name = matched_regi["registryName"]

            if curr_rev == synced_rev:
                continue

            if curr_rev < synced_rev:
                on_log(
                    f"  🚨 [{rel_display}] '{col_name}' 리비전 역전 감지! "
                    f"(테이블 Rev {synced_rev} > 유니티 '{r_name}' Rev {curr_rev}) ➔ 데이터 보호를 위해 건너뜁니다."
                )
                summary["errors"] += 1
                table_has_error = True
                continue

            # curr_rev > synced_rev: .regilog에서 Delta Map 구축
            log_fp = matched_regi["logAbsPath"]
            ok, delta_or_err = build_revision_delta_map(log_fp, synced_rev, curr_rev)
            if not ok:
                on_log(f"  ❌ [{rel_display}] '{col_name}' ({r_name}) 로그 분석 실패: {delta_or_err}")
                summary["errors"] += 1
                table_has_error = True
                continue

            table_needs_sync = True
            col_sync_plans[col_name] = {
                "registry": matched_regi,
                "old_rev": synced_rev,
                "new_rev": curr_rev,
                "replace_map": delta_or_err["replace_map"],
                "deleted_map": delta_or_err["deleted_map"],
                "asset_names": delta_or_err["asset_names"],
            }

        if not table_needs_sync and not table_has_error:
            summary["up_to_date_tables"] += 1
            continue

        if table_needs_sync:
            has_xlsx = os.path.isfile(xlsx_fp)
            has_csv = os.path.isfile(csv_fp)
            if not has_xlsx and not has_csv:
                on_log(f"  ❌ [{rel_display}] 원본 .xlsx 또는 .csv 테이블 파일이 존재하지 않습니다.")
                summary["errors"] += 1
                continue

            if has_xlsx:
                files_to_lock_check.append(xlsx_fp)
            if has_csv:
                files_to_lock_check.append(csv_fp)
            files_to_lock_check.append(regi_fp)

            table_jobs.append({
                "regi_fp": regi_fp,
                "xlsx_fp": xlsx_fp if has_xlsx else None,
                "csv_fp": csv_fp if has_csv else None,
                "rel_display": rel_display,
                "bindings": bindings,
                "col_sync_plans": col_sync_plans,
            })

    if not table_jobs:
        if summary["errors"] == 0:
            on_log(f"✅ 모든 에셋 바인딩 테이블({summary['up_to_date_tables']}개)이 이미 최신 리비전 상태입니다!")
            summary["success"] = True
        else:
            on_log(f"⚠️ 동기화할 대상이 없거나 오류({summary['errors']}건)로 인해 중단되었습니다.")
        if on_progress:
            on_progress(100)
        return summary

    # 3. Pre-flight File Lock Check (원자성 보장: 하나라도 엑셀에 열려 있으면 전체 중단)
    locked_files = check_files_writable(files_to_lock_check)
    if locked_files:
        summary["locked_files"] = [os.path.relpath(p, workspace_root).replace("\\", "/") for p in locked_files]
        on_log("\n🚨 [동기화 중단 - 파일 잠금 감지]")
        on_log("다음 파일이 현재 엑셀(Excel) 또는 다른 프로그램에서 열려 있어 수정할 수 없습니다:")
        for lf in summary["locked_files"]:
            on_log(f"  🔒 {lf}")
        on_log("데이터 일관성을 위해 어떤 파일도 변경하지 않았습니다. 창을 닫고 다시 시도해주세요.")
        return summary

    # 4. 테이블별 1-Pass 치환 및 .csvregi 리비전 갱신 실행
    total_jobs = len(table_jobs)
    for idx, job in enumerate(table_jobs):
        rel_display = job["rel_display"]
        col_sync_plans = job["col_sync_plans"]
        bindings = job["bindings"]

        on_log(f"\n🔄 [{rel_display}] AssetID 리비전 동기화 진행 중...")
        for col_name, plan in col_sync_plans.items():
            r_name = plan["registry"]["registryName"]
            r_cnt = len(plan["replace_map"])
            d_cnt = len(plan["deleted_map"])
            on_log(
                f"  📌 컬럼 '{col_name}' ({r_name}): Rev {plan['old_rev']} ➔ Rev {plan['new_rev']} "
                f"(ID 변경 규칙: {r_cnt}건, 삭제된 에셋: {d_cnt}건)"
            )

        if job["xlsx_fp"]:
            ok, updated_cnt, del_warn_cnt = _sync_single_xlsx_table(
                job["xlsx_fp"], col_sync_plans, on_log, rel_display + ".xlsx"
            )
        else:
            ok, updated_cnt, del_warn_cnt = _sync_single_csv_only_table(
                job["csv_fp"], col_sync_plans, on_log, rel_display + ".csv"
            )

        if not ok:
            summary["errors"] += 1
            continue

        # 성공 시 bindings의 syncedRevision 및 최신 메타 경로/이름 갱신 후 .csvregi 저장
        for col_name, plan in col_sync_plans.items():
            regi = plan["registry"]
            bindings[col_name]["registryName"] = regi["registryName"]
            bindings[col_name]["registrySoGuid"] = regi["registrySoGuid"]
            bindings[col_name]["assetType"] = regi["assetType"]
            bindings[col_name]["regiMetaPath"] = regi["regiMetaPath"]
            bindings[col_name]["syncedRevision"] = plan["new_rev"]

        save_ok, save_err = save_csvregi(job["regi_fp"], bindings)
        if not save_ok:
            on_log(f"  ❌ [{rel_display}] .csvregi 리비전 갱신 저장 실패: {save_err}")
            summary["errors"] += 1
            continue

        summary["synced_tables"] += 1
        summary["updated_cells"] += updated_cnt
        summary["deleted_warnings"] += del_warn_cnt
        on_log(f"  ✅ [{rel_display}] 동기화 완료 (치환된 셀: {updated_cnt}개)")

        if on_progress:
            on_progress(int((idx + 1) / total_jobs * 100))

    summary["success"] = (summary["errors"] == 0)
    return summary
