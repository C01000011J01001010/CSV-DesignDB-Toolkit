import tkinter as tk
from tkinter import ttk, messagebox
import os, json
import pandas as pd
from gui.widgets import ScrollableFrame

class MetaEditorTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#1E1E1E")
        self.app = app
        
        sf = ScrollableFrame(self)
        sf.pack(fill="both", expand=True)
        self.inner = sf.inner_frame
        
        self.current_json_path = None
        self.meta_data = None
        self.workspace_csv_files = []
        self.local_col_vars = {} 

        # --- Top: File Selector ---
        top_frame = tk.Frame(self.inner, bg="#1E1E1E")
        top_frame.pack(fill="x", padx=10, pady=(15, 5))
        tk.Label(top_frame, text="대상 JSON (현재 작업 경로 內):", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        self.combo_files = ttk.Combobox(top_frame, state="readonly", width=50)
        self.combo_files.pack(side="left", padx=10)
        tk.Button(top_frame, text="새로고침", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.refresh_files).pack(side="left", padx=2)
        tk.Button(top_frame, text="메타 로드", font=("맑은 고딕", 9, "bold"), bg="#007ACC", fg="white", bd=0, command=self.load_meta).pack(side="left", padx=2)

        # --- Section 1: Primary Key ---
        self.pk_frame = tk.Frame(self.inner, bg="#252526", bd=1, relief="solid")
        self.pk_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_pk_header = tk.Label(self.pk_frame, text="🔑 Primary Key (기본키) 설정", bg="#2D2D2D", fg="#FFD700", font=("맑은 고딕", 10, "bold"), anchor="w", padx=10, pady=5)
        lbl_pk_header.pack(fill="x")
        
        pk_inner = tk.Frame(self.pk_frame, bg="#252526", padx=10, pady=10)
        pk_inner.pack(fill="x")
        
        tk.Label(pk_inner, text="후보키(Candidate Keys) 목록 중 선택:", bg="#252526", fg="#CCCCCC", font=("맑은 고딕", 9)).pack(side="left")
        self.combo_pk = ttk.Combobox(pk_inner, state="readonly", width=40)
        self.combo_pk.pack(side="left", padx=10)
        tk.Button(pk_inner, text="PK 반영/저장", font=("맑은 고딕", 9, "bold"), bg="#E67E22", fg="white", bd=0, command=self.save_pk).pack(side="left")

        # --- Section 2: Foreign Keys ---
        self.fk_frame = tk.Frame(self.inner, bg="#252526", bd=1, relief="solid")
        self.fk_frame.pack(fill="x", padx=10, pady=10)
        
        lbl_fk_header = tk.Label(self.fk_frame, text="🔗 Foreign Keys (외래키) 객체 매핑", bg="#2D2D2D", fg="#00FF66", font=("맑은 고딕", 10, "bold"), anchor="w", padx=10, pady=5)
        lbl_fk_header.pack(fill="x")
        
        self.fk_list_container = tk.Frame(self.fk_frame, bg="#252526")
        self.fk_list_container.pack(fill="x", padx=10, pady=5)
        
        fk_add_bar = tk.Frame(self.fk_frame, bg="#1E1E1E", padx=10, pady=5)
        fk_add_bar.pack(fill="x", padx=10, pady=10)
        
        tk.Label(fk_add_bar, text="객체명(Name):", bg="#1E1E1E", fg="#CCCCCC").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.ent_fk_name = tk.Entry(fk_add_bar, width=20, font=("Consolas", 10))
        self.ent_fk_name.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        tk.Label(fk_add_bar, text="타겟 테이블 (Workspace 內):", bg="#1E1E1E", fg="#CCCCCC").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.combo_target_table = ttk.Combobox(fk_add_bar, state="readonly", width=30)
        self.combo_target_table.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        tk.Button(fk_add_bar, text="+ FK 객체 추가", bg="#28A745", fg="white", font=("맑은 고딕", 9, "bold"), bd=0, command=self.add_fk).grid(row=0, column=4, sticky="w", padx=15)
        
        tk.Label(fk_add_bar, text="로컬 컬럼 선택:", bg="#1E1E1E", fg="#CCCCCC").grid(row=1, column=0, padx=5, pady=5, sticky="ne")
        self.local_cols_frame = tk.Frame(fk_add_bar, bg="#1E1E1E")
        self.local_cols_frame.grid(row=1, column=1, columnspan=4, padx=5, pady=5, sticky="w")

    def refresh_files(self):
        if not self.app.workspace_root: return
        jsons = []
        csvs = []
        
        for root, dirs, files in os.walk(self.app.workspace_root):
            if 'Disabled' in root: continue
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.app.workspace_root)
                if f.endswith('.csv'): csvs.append(rel)
                
        is_recursive = self.app.include_subdirs.get()
        for root, dirs, files in os.walk(self.app.target_dir):
            if 'Disabled' in root: continue
            if not is_recursive: dirs.clear()
            for f in files:
                if f.endswith('.json'):
                    # 💡 [FIX] JSON의 드롭박스 표시도 target_dir 기준 상대경로로 맞춥니다.
                    rel = os.path.relpath(os.path.join(root, f), self.app.target_dir)
                    jsons.append(rel)
                
        self.combo_files['values'] = jsons
        if jsons: self.combo_files.current(0)
        
        self.workspace_csv_files = csvs
        self.combo_target_table['values'] = csvs
        self.app.right_panel.log(f"작업 경로 내 JSON {len(jsons)}개 스캔 / 전체 DB 타겟 CSV {len(csvs)}개 발견")

    def load_meta(self):
        rel = self.combo_files.get()
        if not rel: return
        # 💡 [FIX] 선택된 JSON 경로도 target_dir과 결합합니다.
        self.current_json_path = os.path.join(self.app.target_dir, rel)
        
        try:
            with open(self.current_json_path, 'r', encoding='utf-8') as f:
                self.meta_data = json.load(f)
        except Exception as e:
            self.app.right_panel.log(f"❌ JSON 로드 실패: {e}")
            return
            
        c_keys = self.meta_data.get('candidateKeys', [])
        pk = self.meta_data.get('primaryKey', [])
        fks = self.meta_data.get('foreignKeys', {})
        
        combo_vals = ["(없음)"] + [" + ".join(ck) for ck in c_keys]
        self.combo_pk['values'] = combo_vals
        if pk and pk in c_keys:
            self.combo_pk.set(" + ".join(pk))
        else:
            self.combo_pk.set("(없음)")
            
        for w in self.fk_list_container.winfo_children(): w.destroy()
        for fk_name, fk_data in fks.items():
            self._render_fk_row(fk_name, fk_data['targetTable'], fk_data['columns'])
            
        csv_path = self.current_json_path.replace('.json', '.csv')
        clean_cols = []
        if os.path.exists(csv_path):
            try:
                try: df = pd.read_csv(csv_path, nrows=0, encoding='utf-8')
                except UnicodeDecodeError: df = pd.read_csv(csv_path, nrows=0, encoding='cp949')
                    
                for c in df.columns:
                    c_str = str(c).strip()
                    if c_str.startswith('{') and c_str.endswith('}'):
                        clean_cols.append(c_str[1:-1].split('/')[0].strip())
                    else:
                        clean_cols.append(c_str)
            except Exception as e:
                self.app.right_panel.log(f"⚠️ CSV 컬럼 로드 실패: {e}")

        for w in self.local_cols_frame.winfo_children(): w.destroy()
        self.local_col_vars.clear()

        if not clean_cols:
            tk.Label(self.local_cols_frame, text="(읽을 수 있는 컬럼이 없습니다.)", bg="#1E1E1E", fg="#888888").pack(side="left")
        else:
            for i, col in enumerate(clean_cols):
                var = tk.BooleanVar(value=False)
                self.local_col_vars[col] = var
                cb = tk.Checkbutton(self.local_cols_frame, text=col, variable=var, font=("Consolas", 10),
                                    bg="#1E1E1E", fg="#FFD700", selectcolor="#2D2D2D",
                                    activebackground="#1E1E1E", activeforeground="white")
                row_idx = i // 5
                col_idx = i % 5
                cb.grid(row=row_idx, column=col_idx, sticky="w", padx=5, pady=2)

        self.app.right_panel.log(f"▶ {rel} 메타데이터 및 컬럼 정보 로드 완료.")

    def _render_fk_row(self, name, target, cols):
        row = tk.Frame(self.fk_list_container, bg="#333333", pady=5, padx=5)
        row.pack(fill="x", pady=2)
        
        info = f"🔗 {name}  ➔  [{target}]  (연결: {', '.join(cols)})"
        tk.Label(row, text=info, bg="#333333", fg="#00FF66", font=("Consolas", 10)).pack(side="left")
        tk.Button(row, text="삭제", bg="#DC3545", fg="white", bd=0, padx=10, command=lambda r=row, n=name: self.delete_fk(r, n)).pack(side="right")

    def save_pk(self):
        if not self.meta_data or not self.current_json_path: return
        val = self.combo_pk.get()
        if val == "(없음)":
            self.meta_data['primaryKey'] = []
        else:
            self.meta_data['primaryKey'] = [c.strip() for c in val.split('+')]
            
        self._write_json()
        self.app.right_panel.log("✅ 기본키(PK) 메타데이터 저장 완료.")

    def add_fk(self):
        if not self.meta_data or not self.current_json_path: return
        name = self.ent_fk_name.get().strip()
        target = self.combo_target_table.get().strip()
        cols = [col for col, var in self.local_col_vars.items() if var.get()]
        
        if not name or not target or not cols:
            messagebox.showwarning("오류", "객체명과 타겟 테이블을 지정하고, 로컬 컬럼을 1개 이상 체크해주세요.")
            return
            
        if 'foreignKeys' not in self.meta_data:
            self.meta_data['foreignKeys'] = {}
            
        self.meta_data['foreignKeys'][name] = {"columns": cols, "targetTable": target}
        self._write_json()
        self.ent_fk_name.delete(0, tk.END)
        self.load_meta() 
        self.app.right_panel.log(f"✅ 외래키({name}) 메타데이터 추가 완료.")

    def delete_fk(self, row, name):
        if name in self.meta_data.get('foreignKeys', {}):
            del self.meta_data['foreignKeys'][name]
            self._write_json()
            row.destroy()
            self.app.right_panel.log(f"🗑️ 외래키({name}) 삭제 완료.")

    def _write_json(self):
        with open(self.current_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.meta_data, f, ensure_ascii=False, indent=2)
