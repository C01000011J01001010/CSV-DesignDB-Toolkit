import os
import openpyxl

# 💡 Prefix 적용하여 엑셀 목록 반환
def get_excel_files(target_dir, include_subdirs=True, exclude_prefix="Disabled"):
    excel_files = []
    for root, dirs, files in os.walk(target_dir):
        if any(p.startswith(exclude_prefix) for p in root.replace('\\', '/').split('/')): continue
        if not include_subdirs and root != target_dir: continue
        for file in files:
            if file.startswith('~$') or file.startswith(exclude_prefix): continue
            if file.endswith('.xlsx'):
                rel_path = os.path.relpath(os.path.join(root, file), target_dir)
                excel_files.append(rel_path)
    return excel_files

# 💡 스키마 바운딩 박스 좌표 추적 엔진
def find_schema_bounds(sheet):
    for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        valid_cols = []
        for col_idx, val in enumerate(row, start=1):
            val_str = str(val).strip() if val is not None else ""
            if val_str.startswith('{') and val_str.endswith('}'):
                valid_cols.append(col_idx)
        if valid_cols:
            return row_idx, valid_cols[0], valid_cols[-1]
    return None, None, None

def read_headers(filepath):
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheet = wb.active
        row_idx, start_col, end_col = find_schema_bounds(sheet)
        
        if row_idx is None:
            return False, "스키마 행을 찾을 수 없습니다."
            
        headers = []
        # {}로 묶인 시작부터 끝 열까지만 가져오기 (외부 메모 무시)
        for col_idx in range(start_col, end_col + 1):
            val = sheet.cell(row=row_idx, column=col_idx).value
            val_str = str(val).strip() if val is not None else ""
            headers.append(val_str)
            
        wb.close()
        return True, headers
    except Exception as e:
        return False, str(e)

def write_headers(filepath, new_headers):
    try:
        wb = openpyxl.load_workbook(filepath)
        sheet = wb.active
        row_idx, start_col, end_col = find_schema_bounds(sheet)
        
        if row_idx is None:
            return False, "원본 스키마 행을 찾을 수 없습니다."
            
        # 정확한 원본 셀 좌표에 덮어쓰기 (레이아웃 보존)
        for i, header in enumerate(new_headers):
            c_idx = start_col + i
            if c_idx <= end_col:
                sheet.cell(row=row_idx, column=c_idx).value = header
                
        wb.save(filepath)
        wb.close()
        return True, ""
    except Exception as e:
        return False, str(e)
