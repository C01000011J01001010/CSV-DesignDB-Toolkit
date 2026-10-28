import os
import json

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
