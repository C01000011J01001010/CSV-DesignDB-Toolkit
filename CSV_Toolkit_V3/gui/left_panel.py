import tkinter as tk
from tkinter import ttk
import os
import threading
from gui.widgets import ScrollableFrame
from gui.constraint_builder import ColumnConstraintBuilder
from core.pk_analyzer import analyze_pk_status
from core.excel_editor import get_excel_files, read_headers, write_headers

class LeftPanel(tk.Frame):
    def __init__(self, parent, app, *args, **kwargs):
        super().__init__(parent, bg="#1E1E1E", *args, **kwargs)
        self.app = app
        self.parsed_headers = []

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab1 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab1, text="1. 스키마 및 제약조건 설정")
        self._build_tab1()

        self.tab2 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab2, text="2. CSV 변환 및 인코딩")
        self._build_tab2()
        
        self.tab3 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab3, text="3. 후보키 분석")
        self._build_tab3()

        self.tab4 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab4, text="4. PK 검증 및 추천")
        self._build_tab4()

    def _parse_raw_header(self, header_str):
        name = header_str
        c_type = ""
        constraints = []
        if header_str.startswith('{') and header_str.endswith('}'):
            parts = [p.strip() for p in header_str[1:-1].split('/')]
            name = parts[0]
            if len(parts) > 1: c_type = parts[1]
            if len(parts) > 2: constraints = parts[2:]
        return name, c_type, constraints

    def _build_tab1(self):
        # Top Global File Selector
        top_frame = tk.Frame(self.tab1, bg="#1E1E1E")
        top_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(top_frame, text="대상 엑셀 파일 선택:", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        self.t1_combo_files = ttk.Combobox(top_frame, state="readonly", width=60)
        self.t1_combo_files.pack(side="left", padx=10, fill="x", expand=True)
        
        btn_refresh = tk.Button(top_frame, text="새로고침", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self._t1_refresh_files)
        btn_refresh.pack(side="left", padx=2)
        btn_load = tk.Button(top_frame, text="헤더 로드", font=("맑은 고딕", 9, "bold"), bg="#007ACC", fg="white", bd=0, command=self._t1_load_headers)
        btn_load.pack(side="left", padx=2)

        # Sub Notebook for Type & Constraints
        self.sub_notebook = ttk.Notebook(self.tab1)
        self.sub_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.sub_tab1 = tk.Frame(self.sub_notebook, bg="#1E1E1E")
        self.sub_notebook.add(self.sub_tab1, text="1.1 타입 설정")
        self._build_sub_tab1()
        
        self.sub_tab2 = tk.Frame(self.sub_notebook, bg="#1E1E1E")
        self.sub_notebook.add(self.sub_tab2, text="1.2 제약조건 설정")
        self._build_sub_tab2()

    def _build_sub_tab1(self):
        sf = ScrollableFrame(self.sub_tab1)
        sf.pack(fill="both", expand=True)
        self.t1_1_inner = sf.inner_frame
        
        self.t1_1_rows_frame = tk.Frame(self.t1_1_inner, bg="#252526", bd=1, relief="solid")
        self.t1_1_rows_frame.pack(fill="x", padx=10, pady=10)
        self.t1_1_row_widgets = []
        
        btn_frame = tk.Frame(self.t1_1_inner, bg="#1E1E1E")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(btn_frame, text="+ 새 컬럼 추가", font=("맑은 고딕", 10), bg="#444444", fg="white", bd=0, command=self._t1_1_add_row).pack(side="left")
        tk.Button(btn_frame, text="✅ 엑셀에 스키마(타입) 저장", font=("맑은 고딕", 10, "bold"), bg="#28A745", fg="white", bd=0, command=self._t1_1_save_headers).pack(side="right")

    def _build_sub_tab2(self):
        sf = ScrollableFrame(self.sub_tab2)
        sf.pack(fill="both", expand=True)
        self.t1_2_inner = sf.inner_frame
        
        self.t1_2_rows_frame = tk.Frame(self.t1_2_inner, bg="#1E1E1E")
        self.t1_2_rows_frame.pack(fill="x", padx=10, pady=10)
        self.t1_2_row_widgets = []
        
        btn_frame = tk.Frame(self.t1_2_inner, bg="#1E1E1E")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(btn_frame, text="✅ 엑셀에 제약조건 적용 및 저장", font=("맑은 고딕", 10, "bold"), bg="#E67E22", fg="white", bd=0, command=self._t1_2_save_headers).pack(side="right")

    def _t1_refresh_files(self):
        files = get_excel_files(self.app.target_dir, self.app.include_subdirs.get())
        if files:
            self.t1_combo_files['values'] = files
            self.t1_combo_files.current(0)
            self.app.right_panel.log(f"엑셀 파일 {len(files)}개 스캔 완료.")
        else:
            self.t1_combo_files['values'] = []
            self.t1_combo_files.set('')
            self.app.right_panel.log("발견된 엑셀 파일이 없습니다.")

    def _t1_load_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        success, data = read_headers(filepath)
        if not success:
            self.app.right_panel.log(f"❌ 헤더 로드 실패: {data}")
            return
            
        self.parsed_headers = []
        for h in data:
            if not h: continue
            c_name, c_type, constraints = self._parse_raw_header(h)
            self.parsed_headers.append({'name': c_name, 'type': c_type, 'constraints': constraints})
            
        self._render_tab1_1()
        self._render_tab1_2()
        self.app.right_panel.log(f"▶ {rel_path} 스키마 로드 완료 (총 {len(self.parsed_headers)}개 컬럼)")

    def _render_tab1_1(self):
        for w in self.t1_1_rows_frame.winfo_children(): w.destroy()
        self.t1_1_row_widgets.clear()
        tk.Label(self.t1_1_rows_frame, text="컬럼명", width=20, bg="#252526", fg="#00FF66", font=("맑은 고딕", 9, "bold")).grid(row=0, column=0, pady=5)
        tk.Label(self.t1_1_rows_frame, text="타입 선택", width=20, bg="#252526", fg="#00FF66", font=("맑은 고딕", 9, "bold")).grid(row=0, column=1, pady=5)
        for d in self.parsed_headers:
            self._t1_1_create_row(d['name'], d['type'])

    def _t1_1_create_row(self, name="", ctype=""):
        row_idx = len(self.t1_1_row_widgets) + 1
        ent_name = tk.Entry(self.t1_1_rows_frame, font=("Consolas", 10), bg="#1E1E1E", fg="white", insertbackground="white", width=25)
        ent_name.insert(0, name)
        ent_name.grid(row=row_idx, column=0, padx=5, pady=2)
        
        # 💡 enum, enum[] 추가
        combo_type = ttk.Combobox(self.t1_1_rows_frame, state="readonly", width=20, 
                                  values=["int", "int[]", "float", "float[]", "string", "string[]", "bool", "bool[]", "enum", "enum[]", "AssetId", "AssetId[]", "ForeignKey", "ForeignKey[]"])
        if ctype: combo_type.set(ctype)
        combo_type.grid(row=row_idx, column=1, padx=5, pady=2)
        self.t1_1_row_widgets.append((ent_name, combo_type))

    def _t1_1_add_row(self):
        self._t1_1_create_row()
        
    def _t1_1_save_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        new_headers = []
        for i, (ent_name, combo_type) in enumerate(self.t1_1_row_widgets):
            name = ent_name.get().strip()
            ctype = combo_type.get().strip()
            if not name: continue
            
            existing_constraints = []
            if i < len(self.parsed_headers):
                existing_constraints = self.parsed_headers[i]['constraints']
                
            if ctype.lower() in ["assetid", "assetid[]", "foreignkey", "foreignkey[]"] and "REF" not in [x.upper() for x in existing_constraints]:
                existing_constraints.append("REF")
                
            if ctype and existing_constraints:
                new_headers.append(f"{{{name}/{ctype}/{'/'.join(existing_constraints)}}}")
            elif ctype:
                new_headers.append(f"{{{name}/{ctype}}}")
            else:
                new_headers.append(f"{{{name}}}")
                
        success, msg = write_headers(filepath, new_headers)
        if success:
            self.app.right_panel.log(f"✅ [1.1] {os.path.basename(filepath)} 스키마/타입 반영 완료.")
            self._t1_load_headers()
        else:
            self.app.right_panel.log(f"❌ 저장 실패: {msg}")

    def _render_tab1_2(self):
        for w in self.t1_2_rows_frame.winfo_children(): w.destroy()
        self.t1_2_row_widgets.clear()
        
        for d in self.parsed_headers:
            builder = ColumnConstraintBuilder(self.t1_2_rows_frame, d['name'], d['type'], d['constraints'])
            builder.pack(fill="x", pady=5)
            self.t1_2_row_widgets.append(builder)

    def _t1_2_save_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        new_headers = []
        for i, builder in enumerate(self.t1_2_row_widgets):
            name = builder.col_name
            ctype = builder.col_type
            constraints = builder.get_constraints()
            
            # 💡 빌더에서 자체 무결성 검사 실패(PK/REF 공존 등) 시 저장 차단
            if constraints is None:
                self.app.right_panel.log(f"❌ '{name}' 컬럼에 논리적 모순이 있는 제약조건이 있어 저장을 취소합니다.")
                return
            
            parts = [name]
            if ctype: parts.append(ctype)
            parts.extend(constraints)
            
            new_headers.append("{" + "/".join(parts) + "}")
            
        success, msg = write_headers(filepath, new_headers)
        if success:
            self.app.right_panel.log(f"✅ [1.2] {os.path.basename(filepath)} 제약조건 반영 완료.")
            self._t1_load_headers()
        else:
            self.app.right_panel.log(f"❌ 저장 실패: {msg}")

    # ==========================
    # Tab 2: CSV Convert
    # ==========================
    def _build_tab2(self):
        scroll_frame = ScrollableFrame(self.tab2)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame
        
        self.app.btn1 = tk.Button(inner, text="엑셀 전체 일괄 변환 (XLSX ➔ CSV)", font=("맑은 고딕", 11, "bold"), bg="#007ACC", fg="white", bd=0, height=2, command=self.app.run_xlsx_to_csv_all)
        self.app.btn1.pack(fill="x", padx=10, pady=10)
        
        self.app.btn2 = tk.Button(inner, text="인코딩 전체 일괄 변환 (ANSI ➔ UTF-8)", font=("맑은 고딕", 11, "bold"), bg="#28A745", fg="white", bd=0, height=2, command=self.app.run_ansi_to_utf8_all)
        self.app.btn2.pack(fill="x", padx=10, pady=5)
        
        self.app.btn3 = tk.Button(inner, text="백그라운드 자동 변환 감시 모드 시작", font=("맑은 고딕", 11, "bold"), bg="#6C757D", fg="white", bd=0, height=2, command=self.app.toggle_watch_mode)
        self.app.btn3.pack(fill="x", padx=10, pady=5)

    # ==========================
    # Tab 3: Candidate Finder
    # ==========================
    def _build_tab3(self):
        scroll_frame = ScrollableFrame(self.tab3)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame

        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        
        tk.Label(guide_frame, text="📌 [후보키 탐색 기능 (JSON 생성)]\n\n현재 설정된 스키마와 데이터를 바탕으로 유일성을 만족하는 후보키를 찾아 JSON으로 추출합니다.", font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")

        opt_frame2 = tk.Frame(inner, bg="#1E1E1E")
        opt_frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(opt_frame2, text="최대 후보키 조합 길이 (연산량 조절용):", font=("맑은 고딕", 10), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        tk.Spinbox(opt_frame2, from_=1, to=10, textvariable=self.app.max_combo_var, width=5, font=("Consolas", 10)).pack(side="left", padx=10)

        self.app.btn4 = tk.Button(inner, text="현재 경로 CSV 최소 후보키 탐색 (JSON 자동 생성)", font=("맑은 고딕", 11, "bold"), bg="#9C27B0", fg="white", bd=0, height=3, command=self.app.run_candidate_key_finder)
        self.app.btn4.pack(fill="x", padx=10, pady=10)

        self.app.progress_bar = ttk.Progressbar(inner, variable=self.app.progress_var, maximum=100)
        self.app.progress_bar.pack(fill="x", padx=10, pady=(0, 10))
        
    # ==========================
    # Tab 4: PK Analyzer
    # ==========================
    def _build_tab4(self):
        scroll_frame = ScrollableFrame(self.tab4)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame

        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        
        # 💡 PK 가능 타입 안내 수정 (enum 추가)
        guide_text = (
            "📌 [PK(기본키) 검증 프로세스 규칙]\n\n"
            "• PK 가능 타입은 오직 'int', 'string', 'bool', 'enum' 뿐입니다. (배열 불가)\n"
            "• 'string' PK인 경우, 데이터 내부에 '_' 기호가 존재하면 반려됩니다.\n"
            "• 설정된 PK 조합이 반드시 '파일명.json'의 후보키 목록에 있어야 합니다.\n"
            "• 분석 대상 JSON 파일이 없다면 최우선 경고(우선 처리) 대상으로 표시됩니다."
        )
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")

        self.btn5 = tk.Button(inner, text="전체 상태 점검 및 PK 리스트업", font=("맑은 고딕", 11, "bold"), bg="#E67E22", fg="white", bd=0, height=3, command=self.run_pk_analyzer)
        self.btn5.pack(fill="x", padx=10, pady=10)
        
    def run_pk_analyzer(self):
        def task():
            self.app.set_buttons_state(False)
            self.btn5.config(state=tk.DISABLED)
            self.app.right_panel.log("\n🚀 [작업 시작] 전체 CSV 파일 PK 무결성 검사")
            
            analyze_pk_status(
                target_dir=self.app.target_dir,
                include_subdirs=self.app.include_subdirs.get(),
                on_log=self.app.right_panel.log
            )
            
            self.app.set_buttons_state(True)
            self.btn5.config(state=tk.NORMAL)
            
        threading.Thread(target=task, daemon=True).start()
