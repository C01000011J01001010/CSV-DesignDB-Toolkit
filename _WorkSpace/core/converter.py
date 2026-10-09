import pandas as pd
import os
import csv

def convert_xlsx_file(filepath):
    try:
        # 헤더 없이 원본 엑셀을 통째로 읽기 (여백 포함)
        df = pd.read_excel(filepath, header=None, dtype=str)
        if df.empty:
            return False, "빈 파일"
        
        header_row_idx = -1
        start_col_idx = -1
        end_col_idx = -1
        
        # 1. 엑셀을 순회하며 {}가 있는 최초의 행과 열 바운딩 박스 찾기
        for r_idx, row in df.iterrows():
            cols_with_schema = []
            for c_idx, val in row.items():
                val_str = str(val).strip() if pd.notna(val) else ""
                if val_str.startswith('{') and val_str.endswith('}'):
                    cols_with_schema.append(c_idx)
            
            if cols_with_schema:
                header_row_idx = r_idx
                start_col_idx = cols_with_schema[0]
                end_col_idx = cols_with_schema[-1]
                break
                
        if header_row_idx == -1:
            return False, "스키마 행({} 형태)을 찾을 수 없습니다."
            
        # 2. 바운딩 박스 영역으로 데이터프레임 잘라내기 (여백 제거)
        # 행: 스키마 행부터 끝까지 / 열: 첫 번째 {} 열부터 마지막 {} 열까지
        sliced_df = df.iloc[header_row_idx:, start_col_idx:end_col_idx+1].copy()
        
        # 3. 잘라낸 영역의 첫 번째 행을 컬럼(헤더)으로 지정
        sliced_df.columns = sliced_df.iloc[0]
        sliced_df = sliced_df[1:].reset_index(drop=True)
        
        # 4. 전체가 빈 칸인 행(Dummy row) 제거
        sliced_df.dropna(how='all', inplace=True)
        
        # 5. CSV로 저장
        csv_path = os.path.splitext(filepath)[0] + '.csv'
        sliced_df.to_csv(csv_path, index=False, encoding='utf-8', quoting=csv.QUOTE_MINIMAL)
        
        return True, csv_path
    except Exception as e:
        return False, str(e)

def convert_ansi_csv_to_utf8(filepath):
    try:
        with open(filepath, 'r', encoding='cp949') as f:
            content = f.read()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, filepath
    except UnicodeDecodeError:
        return True, filepath # 이미 UTF-8
    except Exception as e:
        return False, str(e)
