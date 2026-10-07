import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from utils import get_initial_dir
from core.converter import convert_xlsx_file, convert_ansi_csv_to_utf8
from core.candidate_finder import find_candidate_keys
from core.watcher import PipelineWatcher

from gui.left_panel import LeftPanel
from gui.right_panel import RightPanel

class AppGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV Toolkit")
        
        self.base_width = 1600
        self.base_height = 900
        self.geometry(f"{self.base_width}x{self.base_height}")
        self.minsize(800, 600)
        self.configure(bg="#1E1E1E")
        
        try:
            self.state('zoomed')
        except:
            pass

        self.target_dir = get_initial_dir()
        self.include_subdirs = tk.BooleanVar(value=True)
        self.max_combo_var = tk.IntVar(value=4)
        self.progress_var = tk.DoubleVar()

        self.setup_ui()

        self.watcher = PipelineWatcher(self.right_panel.log)
        self.right_panel.log(f"✅ 프로그램 준비 완료! 시작 경로: {self.target_dir}")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure("TNotebook", background="#1E1E1E", borderwidth=0)
        style.configure("TNotebook.Tab", background="#2D2D2D", foreground="white", padding=[15, 5], font=("맑은 고딕", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#007ACC")])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.global_canvas = tk.Canvas(self, bg="#1E1E1E", highlightthickness=0)
        self.global_scroll_y = ttk.Scrollbar(self, orient="vertical", command=self.global_canvas.yview)
        self.global_scroll_x = ttk.Scrollbar(self, orient="horizontal", command=self.global_canvas.xview)
        
        self.main_container = tk.Frame(self.global_canvas, bg="#1E1E1E")
        
        self.main_container.bind(
            "<Configure>",
            lambda e: self.global_canvas.configure(scrollregion=self.global_canvas.bbox("all"))
        )
        self.canvas_window = self.global_canvas.create_window((0, 0), window=self.main_container, anchor="nw")
        self.global_canvas.bind('<Configure>', self._on_global_canvas_configure)
        
        self.global_canvas.configure(yscrollcommand=self.global_scroll_y.set, xscrollcommand=self.global_scroll_x.set)
        
        self.global_canvas.grid(row=0, column=0, sticky="nsew")
        self.global_scroll_y.grid(row=0, column=1, sticky="ns")
        self.global_scroll_x.grid(row=1, column=0, sticky="ew")

        self.bind('<Configure>', self._on_root_configure)

        # Header
        header_frame = tk.Frame(self.main_container, bg="#2D2D2D", pady=10)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="⚙️ 기획 데이터 파이프라인 관리 도구", font=("Segoe UI", 16, "bold"), fg="#FFFFFF", bg="#2D2D2D").pack()
        
        # Navigation
        nav_frame = tk.Frame(self.main_container, bg="#1E1E1E", pady=15, padx=20)
        nav_frame.pack(fill="x")
        tk.Label(nav_frame, text="작업 경로:", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        
        self.path_entry_var = tk.StringVar(value=self.target_dir)
        self.path_entry = tk.Entry(nav_frame, textvariable=self.path_entry_var, font=("Consolas", 10), bg="#2D2D2D", fg="white", insertbackground="white", bd=1, relief="solid")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.path_entry.bind('<Return>', lambda event: self.apply_manual_path())

        btn_go = tk.Button(nav_frame, text="이동", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.apply_manual_path)
        btn_go.pack(side="left", padx=2)
        btn_up = tk.Button(nav_frame, text="⬆ 상위", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.go_up_dir)
        btn_up.pack(side="left", padx=2)
        btn_browse = tk.Button(nav_frame, text="🔍 탐색", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.browse_dir)
        btn_browse.pack(side="left", padx=2)

        # 💡 [NEW] Global Option Frame
        opt_frame = tk.Frame(self.main_container, bg="#1E1E1E", padx=20)
        opt_frame.pack(fill="x", pady=(0, 10))
        tk.Checkbutton(opt_frame, text="현재 경로 및 하위 폴더 모두 포함 (DFS 탐색)", variable=self.include_subdirs, font=("맑은 고딕", 10, "bold"),
                       bg="#1E1E1E", fg="#FFD700", selectcolor="#2D2D2D", activebackground="#1E1E1E", activeforeground="white", command=self.on_option_changed).pack(side="left")

        # Content 5:5 split
        content_frame = tk.Frame(self.main_container, bg="#1E1E1E")
        content_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        content_frame.grid_columnconfigure(0, weight=1, uniform="half")
        content_frame.grid_columnconfigure(1, weight=1, uniform="half")
        content_frame.grid_rowconfigure(0, weight=1)

        self.left_panel = LeftPanel(content_frame, app=self)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.right_panel = RightPanel(content_frame)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    def _on_root_configure(self, event):
        if event.widget == self:
            is_fullscreen = False
            try:
                if self.state() == 'zoomed':
                    is_fullscreen = True
            except:
                pass
            
            if is_fullscreen:
                self.global_scroll_y.grid_remove()
                self.global_scroll_x.grid_remove()
            else:
                self.global_scroll_y.grid()
                self.global_scroll_x.grid()

    def _on_global_canvas_configure(self, event):
        w = max(event.width, self.base_width)
        h = max(event.height, self.base_height)
        self.global_canvas.itemconfig(self.canvas_window, width=w, height=h)

    def set_buttons_state(self, state):
        flag = tk.NORMAL if state else tk.DISABLED
        if hasattr(self, 'btn1'): self.btn1.config(state=flag)
        if hasattr(self, 'btn2'): self.btn2.config(state=flag)
        if hasattr(self, 'btn4'): self.btn4.config(state=flag)
        self.path_entry.config(state=flag)
        
    def apply_manual_path(self):
        new_path = self.path_entry_var.get().strip()
        if os.path.isdir(new_path):
            self.change_dir(new_path)
        else:
            messagebox.showerror("오류", "유효하지 않은 경로입니다.")
            self.path_entry_var.set(self.target_dir)

    def go_up_dir(self):
        parent_dir = os.path.dirname(self.target_dir)
        if os.path.isdir(parent_dir):
            self.change_dir(parent_dir)

    def browse_dir(self):
        selected_dir = filedialog.askdirectory(initialdir=self.target_dir, title="작업 폴더 선택")
        if selected_dir:
            self.change_dir(os.path.normpath(selected_dir))

    def change_dir(self, new_dir):
        if self.target_dir != new_dir:
            self.target_dir = new_dir
            self.path_entry_var.set(self.target_dir)
            self.right_panel.log(f"\n📂 작업 경로 변경됨: {self.target_dir}")
            if self.watcher.is_watching:
                self.right_panel.log("🔄 설정 변경으로 인해 감시기를 재시작합니다...")
                self.watcher.stop()
                self.watcher.start(self.target_dir, self.include_subdirs.get())

    def on_option_changed(self):
        state = "포함" if self.include_subdirs.get() else "제외"
        self.right_panel.log(f"\n⚙️ 옵션 변경: 하위 폴더 {state}")
        if self.watcher.is_watching:
            self.watcher.stop()
            self.watcher.start(self.target_dir, self.include_subdirs.get())

    def set_progress(self, value):
        self.after(0, lambda: self.progress_var.set(value))

    def run_xlsx_to_csv_all(self):
        def task():
            self.set_buttons_state(False)
            self.right_panel.log("\n🚀 [작업 시작] 전체 XLSX ➔ UTF-8 CSV 변환")
            count = 0
            for root, dirs, files in os.walk(self.target_dir):
                dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
                if not self.include_subdirs.get(): dirs.clear() 

                for file in files:
                    if file.startswith('Disabled'): continue
                    if file.endswith('.xlsx') and not file.startswith('~$'):
                        filepath = os.path.join(root, file)
                        self.right_panel.log(f"🔄 변환 중: {file}")
                        success, result = convert_xlsx_file(filepath)
                        if success:
                            self.right_panel.log(f"   └ ✅ 성공: {os.path.basename(result)}")
                            count += 1
                        else:
                            self.right_panel.log(f"   └ ❌ 실패: {result}")
            self.right_panel.log(f"✨ 총 {count}개 파일 변환 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def run_ansi_to_utf8_all(self):
        def task():
            self.set_buttons_state(False)
            self.right_panel.log("\n🚀 [작업 시작] 전체 CSV 인코딩(UTF-8) 변환")
            count = 0
            for root, dirs, files in os.walk(self.target_dir):
                dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
                if not self.include_subdirs.get(): dirs.clear()

                for file in files:
                    if file.startswith('Disabled'): continue
                    if file.endswith('.csv'):
                        filepath = os.path.join(root, file)
                        self.right_panel.log(f"🔄 점검 중: {file}")
                        success, msg = convert_ansi_csv_to_utf8(filepath)
                        if success:
                            self.right_panel.log(f"   └ ✅ {msg}")
                            count += 1
                        else:
                            self.right_panel.log(f"   └ ❌ 실패: {msg}")
            self.right_panel.log(f"✨ 총 {count}개 CSV 파일 처리 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def toggle_watch_mode(self):
        if not self.watcher.is_watching:
            is_recursive = self.include_subdirs.get()
            self.watcher.start(self.target_dir, is_recursive)
            if hasattr(self, 'btn3'): self.btn3.config(text="백그라운드 감시 중지 (실행 중...)", bg="#DC3545")
            self.right_panel.log(f"\n🕵️‍♂️ [백그라운드 감시 시작] (하위 폴더 포함: {is_recursive})")
        else:
            self.watcher.stop()
            if hasattr(self, 'btn3'): self.btn3.config(text="백그라운드 자동 변환 감시 모드 시작", bg="#6C757D")
            self.right_panel.log("\n🛑 [백그라운드 감시 중지] 정상 종료됨.")

    def run_candidate_key_finder(self):
        def task():
            self.set_buttons_state(False)
            self.set_progress(0)
            self.right_panel.log("\n🚀 [작업 시작] CSV 최소 후보키 탐색")
            
            find_candidate_keys(
                target_dir=self.target_dir,
                max_len=self.max_combo_var.get(),
                include_subdirs=self.include_subdirs.get(),
                on_log=self.right_panel.log,
                on_progress=self.set_progress
            )
            
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def on_close(self):
        self.watcher.stop()
        self.destroy()
