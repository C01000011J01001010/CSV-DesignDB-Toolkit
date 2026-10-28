import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import threading
from gui.widgets import ScrollableFrame
from gui.constraint_builder import ColumnConstraintBuilder
from gui.meta_editor import MetaEditorTab
from core.excel_editor import get_excel_files, read_headers, write_headers
from core.converter import convert_xlsx_file
from core.registry_manager import (
    scan_available_registries,
    parse_regimeta_file,
    load_csvregi,
    save_csvregi,
    get_csvregi_path,
)

ADD_EXTERNAL_REGI_OPTION = "📂 외부 .regimeta 직접 찾아보기..."


class LeftPanel(tk.Frame):
    def __init__(self, parent, app, *args, **kwargs):
        super().__init__(parent, bg="#1E1E1E", *args, **kwargs)
        self.app = app
        self.parsed_headers = []
        self.available_registries = []
        self.regi_label_map = {}
        self.current_regi_bindings = {}
        self.t1_1_btn_plus = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab2 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab2, text="1. CSV 변환")
        self._build_tab2()

        self.tab1 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab1, text="2. 스키마 설정")
        self._build_tab1()
        
        self.tab3 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab3, text="3. 메타(슈퍼키) 추출")
        self._build_tab3()

        self.tab4 = MetaEditorTab(self.notebook, self.app)
        self.notebook.add(self.tab4, text="4. 메타 관리(PK/FK)")

        self.tab5 = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.tab5, text="5. 전체 무결성 검증")
        self._build_tab5()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        current_idx = self.notebook.index("current")
        if current_idx > 0:
            if not self.app.watcher.is_watching:
                messagebox.showwarning("안내", "DB 설계 및 검증 기능을 사용하려면\n먼저 [1. CSV 변환] 탭에서 '백그라운드 자동 변환 모드'를 켜주세요.")
                self.notebook.select(0)

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
        top_frame = tk.Frame(self.tab1, bg="#1E1E1E")
        top_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(top_frame, text="대상 엑셀 파일 선택:", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        self.t1_combo_files = ttk.Combobox(top_frame, state="readonly", width=60)
        self.t1_combo_files.pack(side="left", padx=10, fill="x", expand=True)
        
        btn_refresh = tk.Button(top_frame, text="새로고침", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self._t1_refresh_files)
        btn_refresh.pack(side="left", padx=2)
        btn_load = tk.Button(top_frame, text="헤더 로드", font=("맑은 고딕", 9, "bold"), bg="#007ACC", fg="white", bd=0, command=self._t1_load_headers)
        btn_load.pack(side="left", padx=2)
        btn_open = tk.Button(top_frame, text="엑셀 열기", font=("맑은 고딕", 9, "bold"), bg="#28A745", fg="white", bd=0, command=self._t1_open_excel)
        btn_open.pack(side="left", padx=2)

        guide_frame = tk.Frame(self.tab1, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(0, 5))
        guide_text = (
            "📌 [안내] `{}` 기호가 포함된 최초의 행/열부터 마지막 `{}` 열까지만 스키마와 데이터로 인식합니다. (바깥 여백 및 메모 무시)\n"
            "🎨 좌측 `[-]` / `[+]` 버튼으로 컬럼을 삭제·추가할 수 있으며, `AssetID` 계열 선택 시 연결된 레지스트리는 `.csvregi`로 관리됩니다."
        )
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=5).pack(fill="x")

        self.sub_notebook = ttk.Notebook(self.tab1)
        self.sub_notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.sub_tab1 = tk.Frame(self.sub_notebook, bg="#1E1E1E")
        self.sub_notebook.add(self.sub_tab1, text="2.1 타입 설정")
        self._build_sub_tab1()
        
        self.sub_tab2 = tk.Frame(self.sub_notebook, bg="#1E1E1E")
        self.sub_notebook.add(self.sub_tab2, text="2.2 제약조건 설정")
        self._build_sub_tab2()

    def _build_sub_tab1(self):
        sf = ScrollableFrame(self.sub_tab1)
        sf.pack(fill="both", expand=True)
        self.t1_1_inner = sf.inner_frame
        
        self.t1_1_rows_frame = tk.Frame(self.t1_1_inner, bg="#252526", bd=1, relief="solid", pady=6)
        self.t1_1_rows_frame.pack(fill="x", padx=10, pady=10)
        self.t1_1_row_widgets = []
        
        btn_frame = tk.Frame(self.t1_1_inner, bg="#1E1E1E")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(
            btn_frame,
            text="📂 외부 .regimeta 추가",
            font=("맑은 고딕", 9, "bold"),
            bg="#3A3D41",
            fg="#FFD700",
            bd=0,
            padx=10,
            pady=5,
            command=self._add_external_regimeta_dialog
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            btn_frame,
            text="⚡ 현재 테이블 AssetID 동기화",
            font=("맑은 고딕", 9, "bold"),
            bg="#007ACC",
            fg="white",
            bd=0,
            padx=10,
            pady=5,
            command=self._t1_1_sync_current_table
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text="✅ 엑셀에 스키마(타입) 저장",
            font=("맑은 고딕", 10, "bold"),
            bg="#28A745",
            fg="white",
            bd=0,
            padx=14,
            pady=5,
            command=self._t1_1_save_headers
        ).pack(side="right")

    def _build_sub_tab2(self):
        sf = ScrollableFrame(self.sub_tab2)
        sf.pack(fill="both", expand=True)
        self.t1_2_inner = sf.inner_frame
        
        self.t1_2_rows_frame = tk.Frame(self.t1_2_inner, bg="#1E1E1E")
        self.t1_2_rows_frame.pack(fill="x", padx=10, pady=10)
        self.t1_2_row_widgets = []
        
        btn_frame = tk.Frame(self.t1_2_inner, bg="#1E1E1E")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(btn_frame, text="✅ 엑셀에 제약조건 적용 및 저장", font=("맑은 고딕", 10, "bold"), bg="#E67E22", fg="white", bd=0, padx=14, pady=5, command=self._t1_2_save_headers).pack(side="right")

    def _refresh_available_registries(self, silent=True):
        if not self.app.workspace_root:
            self.available_registries = []
            self.regi_label_map = {}
            return

        prefix = self.app.exclude_prefix_var.get().strip() or "Disabled"
        extra_paths = getattr(self.app, "external_regimeta_paths", [])
        self.available_registries = scan_available_registries(
            self.app.workspace_root,
            exclude_prefix=prefix,
            extra_paths=extra_paths
        )
        self.regi_label_map = {r["displayLabel"]: r for r in self.available_registries}

        for item in self.t1_1_row_widgets:
            self._update_row_registry_widget_state(item, preserve_selection=True)

        if not silent:
            self.app.right_panel.log(f"🎨 에셋 레지스트리(.regimeta) {len(self.available_registries)}개 스캔 완료.")

    def _add_external_regimeta_dialog(self, target_row_item=None):
        if not self.app.workspace_root:
            messagebox.showwarning("안내", "먼저 워크스페이스를 설정해주세요.")
            return None

        selected_file = filedialog.askopenfilename(
            title="연결할 유니티 .regimeta 파일 선택",
            initialdir=self.app.workspace_root,
            filetypes=[("Registry Meta (.regimeta)", ".regimeta"), ("모든 파일 (*.*)", "*.*")]
        )
        if not selected_file:
            return None

        info = parse_regimeta_file(selected_file, self.app.workspace_root)
        if not info:
            messagebox.showerror("오류", "유효한 .regimeta JSON 파일이 아닙니다.")
            return None

        if not hasattr(self.app, "external_regimeta_paths"):
            self.app.external_regimeta_paths = []

        abs_selected = os.path.abspath(selected_file).replace("\\", "/")
        if abs_selected not in self.app.external_regimeta_paths:
            self.app.external_regimeta_paths.append(abs_selected)
            self.app.save_workspace_config()

        self._refresh_available_registries(silent=True)
        if target_row_item is not None:
            target_row_item["combo_regi"].set(info["displayLabel"])
            self._on_row_regi_changed(target_row_item)

        self.app.right_panel.log(f"✅ 외부 레지스트리 등록 완료: {info['displayLabel']} ({info['regiMetaPath']})")
        return info

    def _find_matching_registry_for_binding(self, bound_info):
        """저장된 .csvregi 바인딩 정보와 일치하는 스캔된 레지스트리 객체를 찾습니다."""
        if not bound_info or not isinstance(bound_info, dict):
            return None

        target_guid = str(bound_info.get("registrySoGuid", "")).strip()
        target_path = str(bound_info.get("regiMetaPath", "")).strip().replace("\\", "/")
        target_name = str(bound_info.get("registryName", "")).strip()

        if target_guid:
            for r in self.available_registries:
                if r["registrySoGuid"] == target_guid:
                    return r

        if target_path:
            for r in self.available_registries:
                if r["regiMetaPath"] == target_path or r["metaAbsPath"] == target_path:
                    return r

        if target_name:
            for r in self.available_registries:
                if r["registryName"] == target_name:
                    return r

        return None

    def _t1_refresh_files(self):
        if not self.app.workspace_root:
            self.app.right_panel.log("⚠️ 워크스페이스가 설정되지 않았습니다.")
            return
        
        prefix = self.app.exclude_prefix_var.get().strip() or "Disabled"
        files = []
        for root, dirs, files_in_dir in os.walk(self.app.target_dir):
            rel_root = os.path.relpath(root, self.app.target_dir)
            if rel_root != '.' and any(p.startswith(prefix) for p in rel_root.replace('\\', '/').split('/')):
                continue
                
            if not self.app.include_subdirs.get() and root != self.app.target_dir:
                continue
                
            for file in files_in_dir:
                if file.startswith('~$') or file.startswith(prefix):
                    continue
                if file.endswith('.xlsx'):
                    rel_path = os.path.relpath(os.path.join(root, file), self.app.target_dir).replace('\\', '/')
                    files.append(rel_path)

        if files:
            self.t1_combo_files['values'] = files
            self.t1_combo_files.current(0)
            self.app.right_panel.log(f"작업 경로 내 엑셀 파일 {len(files)}개 스캔 완료.")
        else:
            self.t1_combo_files['values'] = []
            self.t1_combo_files.set('')
            self.app.right_panel.log("작업 경로 내에 발견된 엑셀 파일이 없습니다.")

    def _t1_load_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        success, data = read_headers(filepath)
        if not success:
            self.app.right_panel.log(f"❌ 헤더 로드 실패: {data}")
            return
            
        self.parsed_headers = []
        for idx, h in enumerate(data):
            if not h: continue
            c_name, c_type, constraints = self._parse_raw_header(h)
            constraints = [c for c in constraints if c.upper() not in ['PK', 'PRIMARYKEY', 'REF', 'REFERENCE']]
            self.parsed_headers.append({
                'name': c_name,
                'type': c_type,
                'constraints': constraints,
                'orig_offset': idx
            })

        regi_data = load_csvregi(filepath)
        self.current_regi_bindings = regi_data.get("bindings", {})
        self._refresh_available_registries(silent=True)
            
        self._render_tab1_1()
        self._render_tab1_2()

        regi_count = len(self.current_regi_bindings)
        regi_msg = f" (.csvregi 에셋 바인딩 {regi_count}건)" if regi_count > 0 else ""
        self.app.right_panel.log(f"▶ {rel_path} 스키마 로드 완료{regi_msg}")

    def _render_tab1_1(self):
        for w in self.t1_1_rows_frame.winfo_children():
            w.destroy()
        self.t1_1_row_widgets.clear()

        # 상단 테이블 컬럼 헤더 (좌측 0번 열은 [-] / [+] 버튼 전용 열)
        tk.Label(self.t1_1_rows_frame, text="", width=3, bg="#252526").grid(row=0, column=0, padx=(8, 2), pady=6)
        tk.Label(self.t1_1_rows_frame, text="컬럼명", width=20, bg="#252526", fg="#00FF66", font=("맑은 고딕", 9, "bold")).grid(row=0, column=1, padx=4, pady=6)
        tk.Label(self.t1_1_rows_frame, text="타입 선택", width=12, bg="#252526", fg="#00FF66", font=("맑은 고딕", 9, "bold")).grid(row=0, column=2, padx=4, pady=6)
        tk.Label(self.t1_1_rows_frame, text="참조 에셋 레지스트리 (.regimeta)", width=30, bg="#252526", fg="#00E5FF", font=("맑은 고딕", 9, "bold")).grid(row=0, column=3, padx=4, pady=6)
        tk.Label(self.t1_1_rows_frame, text="바인딩 상태", width=22, bg="#252526", fg="#FFD700", font=("맑은 고딕", 9, "bold"), anchor="w").grid(row=0, column=4, padx=6, pady=6, sticky="w")

        # 좌측 하단 [+] 새 컬럼 추가 버튼 (마지막 [-] 버튼 바로 아래에 위치)
        self.t1_1_btn_plus = tk.Button(
            self.t1_1_rows_frame,
            text="+",
            font=("Consolas", 11, "bold"),
            bg="#28A745",
            fg="white",
            activebackground="#34CE57",
            activeforeground="white",
            bd=0,
            width=3,
            cursor="hand2",
            command=self._t1_1_add_row
        )

        for d in self.parsed_headers:
            self._t1_1_create_row(
                name=d['name'],
                ctype=d['type'],
                orig_name=d['name'],
                orig_offset=d.get('orig_offset'),
                constraints=d.get('constraints', []),
                regrid=False
            )

        self._t1_1_regrid_rows()

    def _t1_1_regrid_rows(self):
        """현재 남아있는 행들과 하단 [+] 버튼의 grid 좌표를 순서대로 재정렬합니다."""
        for idx, item in enumerate(self.t1_1_row_widgets):
            r = idx + 1
            item["btn_del"].grid(row=r, column=0, padx=(8, 2), pady=3)
            item["ent_name"].grid(row=r, column=1, padx=4, pady=3)
            item["combo_type"].grid(row=r, column=2, padx=4, pady=3)
            item["combo_regi"].grid(row=r, column=3, padx=4, pady=3)
            item["lbl_status"].grid(row=r, column=4, padx=6, pady=3, sticky="w")

        plus_row = len(self.t1_1_row_widgets) + 1
        if self.t1_1_btn_plus and self.t1_1_btn_plus.winfo_exists():
            self.t1_1_btn_plus.grid(row=plus_row, column=0, padx=(8, 2), pady=(6, 4))

    def _t1_1_remove_row(self, row_item):
        if len(self.t1_1_row_widgets) <= 1:
            messagebox.showwarning("삭제 제한", "테이블에는 최소 1개 이상의 스키마 컬럼이 존재해야 합니다.")
            return

        if row_item in self.t1_1_row_widgets:
            self.t1_1_row_widgets.remove(row_item)
            for key in ["btn_del", "ent_name", "combo_type", "combo_regi", "lbl_status"]:
                w = row_item.get(key)
                if w and w.winfo_exists():
                    w.destroy()
            self._t1_1_regrid_rows()

    def _t1_1_create_row(self, name="", ctype="", orig_name="", orig_offset=None, constraints=None, regrid=True):
        btn_del = tk.Button(
            self.t1_1_rows_frame,
            text="-",
            font=("Consolas", 11, "bold"),
            bg="#DC3545",
            fg="white",
            activebackground="#E4606D",
            activeforeground="white",
            bd=0,
            width=3,
            cursor="hand2"
        )

        ent_name = tk.Entry(self.t1_1_rows_frame, font=("Consolas", 10), bg="#1E1E1E", fg="white", insertbackground="white", width=22)
        ent_name.insert(0, name)
        
        combo_type = ttk.Combobox(
            self.t1_1_rows_frame,
            state="readonly",
            width=12,
            values=["int", "int[]", "float", "float[]", "string", "string[]", "bool", "bool[]", "enum", "enum[]", "AssetID", "AssetID[]"]
        )
        if ctype:
            if ctype.lower() == "assetid": ctype = "AssetID"
            elif ctype.lower() == "assetid[]": ctype = "AssetID[]"
            combo_type.set(ctype)

        combo_regi = ttk.Combobox(self.t1_1_rows_frame, state="disabled", width=30)

        lbl_status = tk.Label(self.t1_1_rows_frame, text="-", bg="#252526", fg="#777777", font=("맑은 고딕", 9), anchor="w", width=24)

        row_item = {
            "btn_del": btn_del,
            "ent_name": ent_name,
            "combo_type": combo_type,
            "combo_regi": combo_regi,
            "lbl_status": lbl_status,
            "orig_name": orig_name,
            "orig_offset": orig_offset,
            "constraints": list(constraints) if constraints else [],
            "missing_fallback_info": None
        }

        btn_del.config(command=lambda it=row_item: self._t1_1_remove_row(it))
        combo_type.bind("<<ComboboxSelected>>", lambda e, it=row_item: self._on_row_type_changed(it))
        combo_regi.bind("<Button-1>", lambda e, it=row_item: self._on_regi_dropdown_clicked(it))
        combo_regi.bind("<<ComboboxSelected>>", lambda e, it=row_item: self._on_row_regi_changed(it))

        self._update_row_registry_widget_state(row_item, preserve_selection=False)
        self.t1_1_row_widgets.append(row_item)

        if regrid:
            self._t1_1_regrid_rows()
            ent_name.focus_set()

    def _on_regi_dropdown_clicked(self, row_item):
        """레지스트리 드롭다운을 클릭할 때 자동으로 최신 .regimeta 목록을 재스캔합니다."""
        ctype = row_item["combo_type"].get().strip()
        if ctype in ["AssetID", "AssetID[]"]:
            self._refresh_available_registries(silent=True)

    def _update_row_registry_widget_state(self, row_item, preserve_selection=False):
        combo_type = row_item["combo_type"]
        combo_regi = row_item["combo_regi"]
        lbl_status = row_item["lbl_status"]
        col_key = row_item["orig_name"] or row_item["ent_name"].get().strip()

        ctype = combo_type.get().strip()
        if ctype not in ["AssetID", "AssetID[]"]:
            combo_regi["values"] = ["(해당 없음)"]
            combo_regi.set("(해당 없음)")
            combo_regi.config(state="disabled")
            lbl_status.config(text="-", fg="#777777")
            row_item["missing_fallback_info"] = None
            return

        prev_selected = combo_regi.get().strip() if preserve_selection else ""
        options = ["(레지스트리 선택)"] + [r["displayLabel"] for r in self.available_registries]
        bound_info = self.current_regi_bindings.get(col_key)
        matched_regi = self._find_matching_registry_for_binding(bound_info)

        fallback_label = None
        if bound_info and not matched_regi:
            r_name = bound_info.get("registryName", "Unknown")
            s_rev = bound_info.get("syncedRevision", 0)
            fallback_label = f"[기존 바인딩] {r_name} [Rev {s_rev}] (파일 미발견)"
            options.append(fallback_label)
            row_item["missing_fallback_info"] = bound_info
        else:
            row_item["missing_fallback_info"] = None

        options.append(ADD_EXTERNAL_REGI_OPTION)
        combo_regi["values"] = options
        combo_regi.config(state="readonly")

        if preserve_selection and prev_selected in options and prev_selected not in ["(해당 없음)", ADD_EXTERNAL_REGI_OPTION]:
            combo_regi.set(prev_selected)
            self._on_row_regi_changed(row_item)
        elif matched_regi:
            combo_regi.set(matched_regi["displayLabel"])
            synced_rev = int(bound_info.get("syncedRevision", matched_regi["currentRevision"]))
            curr_rev = int(matched_regi["currentRevision"])
            if synced_rev == curr_rev:
                lbl_status.config(text=f"✅ 동기화됨 (Rev {synced_rev})", fg="#5CD679")
            else:
                lbl_status.config(text=f"⚠️ 리비전 변경 (Rev {synced_rev} ➔ {curr_rev})", fg="#FFD700")
        elif fallback_label:
            combo_regi.set(fallback_label)
            lbl_status.config(text="❌ .regimeta 위치 확인 필요", fg="#FF5555")
        else:
            combo_regi.set("(레지스트리 선택)")
            if len(self.available_registries) == 0:
                lbl_status.config(text="⚠️ .regimeta 추가 필요", fg="#FF7B88")
            else:
                lbl_status.config(text="⚠️ 레지스트리 선택 필요", fg="#FFD700")

    def _on_row_type_changed(self, row_item):
        self._update_row_registry_widget_state(row_item, preserve_selection=True)

    def _on_row_regi_changed(self, row_item):
        combo_regi = row_item["combo_regi"]
        lbl_status = row_item["lbl_status"]
        col_key = row_item["orig_name"] or row_item["ent_name"].get().strip()
        selected_label = combo_regi.get().strip()

        if selected_label == ADD_EXTERNAL_REGI_OPTION:
            added = self._add_external_regimeta_dialog(target_row_item=row_item)
            if not added:
                combo_regi.set("(레지스트리 선택)")
                lbl_status.config(text="⚠️ 레지스트리 선택 필요", fg="#FFD700")
            return

        if selected_label in ["", "(해당 없음)", "(레지스트리 선택)"]:
            lbl_status.config(text="⚠️ 레지스트리 선택 필요", fg="#FFD700")
            return

        if selected_label in self.regi_label_map:
            regi = self.regi_label_map[selected_label]
            bound_info = self.current_regi_bindings.get(col_key)
            if bound_info and bound_info.get("registrySoGuid") == regi["registrySoGuid"]:
                synced_rev = int(bound_info.get("syncedRevision", regi["currentRevision"]))
                curr_rev = int(regi["currentRevision"])
                if synced_rev == curr_rev:
                    lbl_status.config(text=f"✅ 동기화됨 (Rev {synced_rev})", fg="#5CD679")
                else:
                    lbl_status.config(text=f"⚠️ 리비전 변경 (Rev {synced_rev} ➔ {curr_rev})", fg="#FFD700")
            else:
                lbl_status.config(text=f"📌 바인딩 예정 (초기 Rev {regi['currentRevision']})", fg="#00E5FF")
        elif row_item.get("missing_fallback_info"):
            lbl_status.config(text="❌ .regimeta 위치 확인 필요", fg="#FF5555")

    def _t1_1_add_row(self):
        if not self.t1_combo_files.get() or not self.app.workspace_root:
            messagebox.showwarning("안내", "먼저 상단에서 대상 엑셀 파일을 선택하고 [헤더 로드]를 실행해주세요.")
            return
        self._t1_1_create_row(name="", ctype="int", orig_name="", orig_offset=None, constraints=[], regrid=True)
        
    def _t1_1_save_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        new_headers = []
        orig_offsets = []
        new_bindings = {}
        seen_names = set()
        allow_unbound_save = False

        for row_item in self.t1_1_row_widgets:
            name = row_item["ent_name"].get().strip()
            ctype = row_item["combo_type"].get().strip()
            selected_regi_label = row_item["combo_regi"].get().strip()
            orig_name = row_item["orig_name"]
            orig_offset = row_item.get("orig_offset")
            existing_constraints = row_item.get("constraints", [])

            if not name:
                messagebox.showwarning("컬럼명 누락", "컬럼명이 비어있는 행이 있습니다. 컬럼명을 입력하거나 [-] 버튼으로 삭제해주세요.")
                row_item["ent_name"].focus_set()
                return

            if not ctype:
                messagebox.showwarning("타입 누락", f"'{name}' 컬럼의 데이터 타입을 선택해주세요.")
                return

            if name in seen_names:
                messagebox.showerror("중복 컬럼명", f"테이블 내에 중복된 컬럼명('{name}')이 존재합니다.")
                return
            seen_names.add(name)
            
            if ctype and existing_constraints:
                new_headers.append(f"{{{name}/{ctype}/{'/'.join(existing_constraints)}}}")
            elif ctype:
                new_headers.append(f"{{{name}/{ctype}}}")
            else:
                new_headers.append(f"{{{name}}}")

            orig_offsets.append(orig_offset)

            if ctype in ["AssetID", "AssetID[]"]:
                prev_binding = self.current_regi_bindings.get(orig_name) or self.current_regi_bindings.get(name)

                if selected_regi_label in self.regi_label_map:
                    regi = self.regi_label_map[selected_regi_label]
                    if prev_binding and prev_binding.get("registrySoGuid") and prev_binding.get("registrySoGuid") == regi["registrySoGuid"]:
                        synced_rev = int(prev_binding.get("syncedRevision", regi["currentRevision"]))
                    elif prev_binding and not prev_binding.get("registrySoGuid") and prev_binding.get("regiMetaPath") == regi["regiMetaPath"]:
                        synced_rev = int(prev_binding.get("syncedRevision", regi["currentRevision"]))
                    else:
                        synced_rev = int(regi["currentRevision"])

                    new_bindings[name] = {
                        "registryName": regi["registryName"],
                        "registrySoGuid": regi["registrySoGuid"],
                        "assetType": regi["assetType"],
                        "regiMetaPath": regi["regiMetaPath"],
                        "syncedRevision": synced_rev
                    }
                elif row_item.get("missing_fallback_info") and selected_regi_label.startswith("[기존 바인딩]"):
                    new_bindings[name] = dict(row_item["missing_fallback_info"])
                else:
                    if len(self.available_registries) > 0:
                        messagebox.showerror(
                            "레지스트리 선택 필요",
                            f"'{name}' ({ctype}) 컬럼에 연결할 참조 에셋 레지스트리(.regimeta)를 선택해주세요."
                        )
                        return
                    elif not allow_unbound_save:
                        ans = messagebox.askyesno(
                            "레지스트리 미연결 확인",
                            f"현재 워크스페이스에서 스캔된 .regimeta 파일이 없어 '{name}' ({ctype}) 컬럼에 레지스트리를 연결하지 못했습니다.\n\n"
                            "레지스트리 바인딩 없이 스키마만 먼저 저장하시겠습니까?\n"
                            "('아니오'를 누르면 저장을 취소하고 [📂 외부 .regimeta 추가] 버튼으로 파일을 먼저 등록할 수 있습니다.)"
                        )
                        if not ans:
                            return
                        allow_unbound_save = True

        if not new_headers:
            messagebox.showwarning("안내", "저장할 스키마 컬럼이 없습니다.")
            return
                
        success, msg = write_headers(filepath, new_headers, orig_offsets=orig_offsets)
        if not success:
            self.app.right_panel.log(f"❌ 스키마 저장 실패: {msg}")
            messagebox.showerror("저장 실패", msg)
            return

        # 엑셀 스키마 변경 즉시 대응 CSV도 함께 갱신
        convert_xlsx_file(filepath)

        regi_ok, regi_res = save_csvregi(filepath, new_bindings)
        if not regi_ok:
            self.app.right_panel.log(f"⚠️ 스키마는 저장되었으나 .csvregi 저장 실패: {regi_res}")
        else:
            csvregi_name = os.path.basename(get_csvregi_path(filepath))
            if new_bindings:
                self.app.right_panel.log(f"✅ 스키마(컬럼 {len(new_headers)}개) 및 {csvregi_name} (AssetID 바인딩 {len(new_bindings)}건) 저장 완료.")
            else:
                self.app.right_panel.log(f"✅ 스키마(컬럼 {len(new_headers)}개) 반영 완료.")

        self._t1_load_headers()

    def _t1_1_sync_current_table(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path or not self.app.workspace_root:
            messagebox.showwarning("안내", "먼저 상단에서 대상 엑셀 파일을 선택하고 [헤더 로드]를 실행해주세요.")
            return
        filepath = os.path.join(self.app.target_dir, rel_path)
        regi_path = get_csvregi_path(filepath)
        if not os.path.isfile(regi_path):
            messagebox.showinfo(
                "안내",
                "현재 테이블에 저장된 .csvregi 바인딩 파일이 없습니다.\n"
                "AssetID 컬럼에 레지스트리를 선택한 뒤 먼저 [✅ 엑셀에 스키마(타입) 저장]을 눌러주세요."
            )
            return
        self.app.run_single_table_asset_sync(filepath, on_complete_callback=self._t1_load_headers)

    def _render_tab1_2(self):
        for w in self.t1_2_rows_frame.winfo_children(): w.destroy()
        self.t1_2_row_widgets.clear()
        
        for d in self.parsed_headers:
            regi_binding = self.current_regi_bindings.get(d['name'])
            builder = ColumnConstraintBuilder(self.t1_2_rows_frame, d['name'], d['type'], d['constraints'], regi_binding=regi_binding)
            builder.pack(fill="x", pady=5)
            self.t1_2_row_widgets.append(builder)

    def _t1_2_save_headers(self):
        rel_path = self.t1_combo_files.get()
        if not rel_path or not self.app.workspace_root: return
        filepath = os.path.join(self.app.target_dir, rel_path)
        
        new_headers = []
        for i, builder in enumerate(self.t1_2_row_widgets):
            name = builder.col_name
            ctype = builder.col_type
            constraints = builder.get_constraints()
            
            if constraints is None:
                self.app.right_panel.log(f"❌ '{name}' 제약조건 모순. 저장 취소.")
                return
            
            parts = [name]
            if ctype: parts.append(ctype)
            parts.extend(constraints)
            new_headers.append("{" + "/".join(parts) + "}")
            
        success, msg = write_headers(filepath, new_headers)
        if success:
            convert_xlsx_file(filepath)
            self.app.right_panel.log(f"✅ 제약조건 반영 완료.")
            self._t1_load_headers()
        else:
            self.app.right_panel.log(f"❌ 제약조건 저장 실패: {msg}")
            messagebox.showerror("저장 실패", msg)

    def _build_tab2(self):
        scroll_frame = ScrollableFrame(self.tab2)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame
        
        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        guide_text = "📌 [파싱 범위 안내]\n\n엑셀 문서에서 `{}` 기호가 처음 시작되는 행과 열부터 마지막 `{}` 열 사이의 데이터만\n유효한 스키마(바운딩 박스) 영역으로 자동 크롭(Crop)되어 CSV로 변환됩니다."
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")
        
        self.app.btn1 = tk.Button(inner, text="엑셀 ➔ CSV 전체 변환 (현재 작업 경로 내)", font=("맑은 고딕", 11, "bold"), bg="#007ACC", fg="white", bd=0, height=2, command=self.app.run_xlsx_to_csv_all)
        self.app.btn1.pack(fill="x", padx=10, pady=10)
        
        self.app.btn2 = tk.Button(inner, text="CSV ➔ UTF-8 변환 (현재 작업 경로 내)", font=("맑은 고딕", 11, "bold"), bg="#28A745", fg="white", bd=0, height=2, command=self.app.run_ansi_to_utf8_all)
        self.app.btn2.pack(fill="x", padx=10, pady=5)
        
        self.app.btn3 = tk.Button(inner, text="백그라운드 자동 변환 모드 시작", font=("맑은 고딕", 11, "bold"), bg="#6C757D", fg="white", bd=0, height=2, command=self.app.toggle_watch_mode)
        self.app.btn3.pack(fill="x", padx=10, pady=5)

        sync_guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        sync_guide_frame.pack(fill="x", padx=10, pady=(20, 8))
        sync_guide_text = (
            "🎨 [유니티 AssetRegistry (.regilog) ➔ 테이블 AssetID 자동 동기화]\n\n"
            "유니티에서 에셋 재정렬 또는 Stride 배분으로 AssetID가 변경되어 .regimeta 리비전(Rev)이 올라간 경우,\n"
            ".csvregi 바인딩 이력과 .regilog의 GUID 기록을 대조하여 원본 엑셀(.xlsx)과 .csv의 AssetID를 1-Pass로 일괄 갱신합니다."
        )
        tk.Label(sync_guide_frame, text=sync_guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")

        self.app.btn_sync_assets = tk.Button(
            inner,
            text="🔄 에셋 레지스트리(.regilog) 변경분 테이블 일괄 동기화 (워크스페이스 전역)",
            font=("맑은 고딕", 11, "bold"),
            bg="#17A2B8",
            fg="white",
            bd=0,
            height=2,
            command=self.app.run_asset_id_sync_all
        )
        self.app.btn_sync_assets.pack(fill="x", padx=10, pady=5)

    def _build_tab3(self):
        scroll_frame = ScrollableFrame(self.tab3)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame

        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        
        guide_text = "📌 [메타데이터 (슈퍼키) 추출]\n\n배열([])과 float 타입을 배제하고 고유하게 식별 가능한 모든 슈퍼키 조합을 추출하여 JSON 포맷의 .csvmeta 파일로 저장합니다.\n\n※ 엑셀 스키마에 제약조건 \"UNIQUE\"와 \"NOT NULL\"이 동시에 적용된 컬럼을 포함하고 있는 키조합은 내부 유일성 검사 목록에서 제외됩니다.\n    (즉시 슈퍼키로 확정 - Fast Track)"
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")

        opt_frame2 = tk.Frame(inner, bg="#1E1E1E")
        opt_frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(opt_frame2, text="최대 슈퍼키 조합 길이 (연산량 조절용):", font=("맑은 고딕", 10), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        tk.Spinbox(opt_frame2, from_=1, to=10, textvariable=self.app.max_combo_var, width=5, font=("Consolas", 10)).pack(side="left", padx=10)

        self.app.btn4 = tk.Button(inner, text="메타데이터(슈퍼키) 자동 추출 및 .csvmeta 갱신 (현재 경로)", font=("맑은 고딕", 11, "bold"), bg="#9C27B0", fg="white", bd=0, height=3, command=self.app.run_super_key_finder)
        self.app.btn4.pack(fill="x", padx=10, pady=10)

        self.app.progress_bar = ttk.Progressbar(inner, variable=self.app.progress_var, maximum=100)
        self.app.progress_bar.pack(fill="x", padx=10, pady=(0, 10))

    def _build_tab5(self):
        scroll_frame = ScrollableFrame(self.tab5)
        scroll_frame.pack(fill="both", expand=True)
        inner = scroll_frame.inner_frame

        guide_frame = tk.Frame(inner, bg="#252526", bd=1, relief="solid")
        guide_frame.pack(fill="x", padx=10, pady=(15, 10))
        
        guide_text = (
            "🛡️ [전체 데이터베이스 무결성 검증]\n\n"
            "워크스페이스(Root: 폴더 및 하위 폴더) 전체를 대상으로 RDBMS 수준의 5대 무결성을 교차 검증합니다.\n\n"
            "1. 개체 무결성 : 기본키(PK)의 중복 및 빈 칸(Null) 존재 여부\n"
            "2. 참조 무결성 : 외래키(FK)가 가리키는 대상이 실제로 존재하는지 교차 확인\n"
            "3. 도메인 무결성: 데이터 타입의 형식 일치 여부\n"
            "4. 고유 무결성 : UNIQUE 제약조건 위반 여부\n"
            "5. Null 무결성 : NOT NULL 제약조건 위반 여부\n\n"
            "※ 검증 전, 모든 파일의 [메타 추출] 및 [PK 설정]이 완료되어야 합니다.\n"
            "※ 검증 완료 시 워크스페이스 전체의 참조 관계도(ERD) HTML 파일이 자동 생성/갱신됩니다."
        )
        tk.Label(guide_frame, text=guide_text, font=("맑은 고딕", 9), fg="#D4D4D4", bg="#252526", justify="left", anchor="w", padx=10, pady=10).pack(fill="x")

        self.app.btn_validate = tk.Button(inner, text="데이터베이스 전체 무결성 글로벌 검증 시작", font=("맑은 고딕", 12, "bold"), bg="#DC3545", fg="white", bd=0, height=3, command=self.app.run_global_validation)
        self.app.btn_validate.pack(fill="x", padx=10, pady=(10, 5))

        self.app.btn_open_erd = tk.Button(inner, text="📊 참조 관계도(ERD) 브라우저로 열기 (무결성 검증 시 자동 생성)", font=("맑은 고딕", 11, "bold"), bg="#444444", fg="white", bd=0, height=2, state=tk.DISABLED, command=self.app.open_erd_viewer)
        self.app.btn_open_erd.pack(fill="x", padx=10, pady=5)
