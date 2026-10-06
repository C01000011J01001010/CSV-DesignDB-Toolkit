import os
import sys
import time
import math
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from itertools import combinations
import pandas as pd
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    import msvcrt
except ImportError:
    msvcrt = None

lock_file_handle = None

def check_single_instance():
    global lock_file_handle
    temp_dir = os.environ.get("TEMP", os.path.dirname(os.path.abspath(__file__)))
    lock_file_path = os.path.join(temp_dir, "data_pipeline_hub.lock")
    try:
        lock_file_handle = open(lock_file_path, "w")
        if msvcrt:
            msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except (IOError, OSError):
        return False
    return True

def get_initial_dir():
    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        return os.path.abspath(sys.argv[1])
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def is_disabled_path(filepath):
    parts = os.path.normpath(filepath).split(os.sep)
    for part in parts:
        if part.startswith("Disabled"):
            return True
    return False

# ============ [모듈 1] 포맷 변환 유틸리티 ============
def convert_xlsx_file(filepath):
    dir_name = os.path.dirname(filepath)
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    csv_filepath = os.path.join(dir_name, f"{base_name}.csv")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            df = pd.read_excel(filepath, engine='openpyxl')
            df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
            return True, csv_filepath
        except PermissionError:
            time.sleep(1)
        except Exception as e:
            return False, str(e)
    return False, "파일 접근 권한 초과"

def convert_ansi_csv_to_utf8(filepath):
    encodings_to_try = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
    df = None
    used_encoding = None
    
    for enc in encodings_to_try:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            used_encoding = enc
            break
        except Exception:
            continue
            
    if df is not None:
        try:
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            if used_encoding in ['utf-8-sig', 'utf-8']:
                return True, "이미 UTF-8 형식입니다 (재저장 완료)"
            else:
                return True, f"변환 완료 ({used_encoding.upper()} ➔ UTF-8)"
        except Exception as e:
            return False, f"저장 실패: {str(e)}"
    else:
        return False, "지원하지 않는 인코딩이거나 파일을 읽을 수 없습니다."

class WatcherHandler(FileSystemEventHandler):
    def __init__(self, log_callback):
        super().__init__()
        self.log_callback = log_callback
        self.last_processed = {}

    def on_created(self, event):
        self.process_event(event)

    def on_modified(self, event):
        self.process_event(event)

    def process_event(self, event):
        if event.is_directory:
            return
        
        filepath = event.src_path
        filename = os.path.basename(filepath)

        if is_disabled_path(filepath):
            return

        if filepath.endswith('.xlsx') and not filename.startswith('~$'):
            current_time = time.time()
            if filepath in self.last_processed:
                if current_time - self.last_processed[filepath] < 1.5:
                    return
            self.last_processed[filepath] = current_time

            self.log_callback(f"👀 [자동 감지] {filename} 변환 중...")
            success, result = convert_xlsx_file(filepath)
            if success:
                self.log_callback(f"✅ [감지 변환 완료] {os.path.basename(result)}\n")
            else:
                self.log_callback(f"❌ [감지 변환 실패] {filename}: {result}\n")

# ============ 메인 GUI 클래스 ============
class AppGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        if not check_single_instance():
            messagebox.showwarning("중복 실행 방지", "이미 프로그램이 실행 중입니다!")
            sys.exit()

        self.title("Data Pipeline Hub (Excel/CSV 변환 & 무결성 검증)")
        self.geometry("800x750")
        self.configure(bg="#1E1E1E")
        self.resizable(False, False)

        self.target_dir = get_initial_dir()
        self.is_watching = False
        self.observer = None
        
        self.include_subdirs = tk.BooleanVar(value=True)
        self.max_combo_var = tk.IntVar(value=4)

        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        
        # 탭 스타일 커스텀
        style.configure("TNotebook", background="#1E1E1E", borderwidth=0)
        style.configure("TNotebook.Tab", background="#2D2D2D", foreground="white", padding=[15, 5], font=("맑은 고딕", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#007ACC")])

        # [1] 상단 헤더 & 공통 네비게이션
        header_frame = tk.Frame(self, bg="#2D2D2D", pady=10)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="⚙️ 기획 데이터 파이프라인 관리 도구", font=("Segoe UI", 16, "bold"), fg="#FFFFFF", bg="#2D2D2D").pack()
        
        nav_frame = tk.Frame(self, bg="#1E1E1E", pady=15, padx=20)
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

        # [2] 탭(Notebook) 구성
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="x", padx=20, pady=5)

        # --- 탭 1: 포맷 변환기 ---
        tab1 = tk.Frame(self.notebook, bg="#1E1E1E", pady=15)
        self.notebook.add(tab1, text="1. 포맷 & 인코딩 변환")

        tk.Checkbutton(tab1, text="하위 폴더 포함하여 적용 (재귀적 탐색 및 감시)", variable=self.include_subdirs, font=("맑은 고딕", 10),
                       bg="#1E1E1E", fg="#CCCCCC", selectcolor="#2D2D2D", activebackground="#1E1E1E", activeforeground="white", command=self.on_option_changed).pack(anchor="w", padx=10)
        
        self.btn1 = tk.Button(tab1, text="엑셀 전체 일괄 변환 (XLSX ➔ CSV)", font=("맑은 고딕", 11, "bold"), bg="#007ACC", fg="white", bd=0, height=2, command=self.run_xlsx_to_csv_all)
        self.btn1.pack(fill="x", padx=10, pady=5)
        
        self.btn2 = tk.Button(tab1, text="인코딩 전체 일괄 변환 (ANSI ➔ UTF-8)", font=("맑은 고딕", 11, "bold"), bg="#28A745", fg="white", bd=0, height=2, command=self.run_ansi_to_utf8_all)
        self.btn2.pack(fill="x", padx=10, pady=5)
        
        self.btn3 = tk.Button(tab1, text="백그라운드 자동 변환 감시 모드 시작", font=("맑은 고딕", 11, "bold"), bg="#6C757D", fg="white", bd=0, height=2, command=self.toggle_watch_mode)
        self.btn3.pack(fill="x", padx=10, pady=5)

        # --- 탭 2: 데이터 무결성 검증기 (후보키) ---
        tab2 = tk.Frame(self.notebook, bg="#1E1E1E", pady=15)
        self.notebook.add(tab2, text="2. 데이터 무결성 검증 (CSV)")

        opt_frame2 = tk.Frame(tab2, bg="#1E1E1E")
        opt_frame2.pack(fill="x", padx=10, pady=5)
        tk.Label(opt_frame2, text="최대 후보키 조합 길이 (연산량 조절용):", font=("맑은 고딕", 10), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        tk.Spinbox(opt_frame2, from_=1, to=10, textvariable=self.max_combo_var, width=5, font=("Consolas", 10)).pack(side="left", padx=10)

        self.btn4 = tk.Button(tab2, text="현재 경로 CSV 무결성 검증 (최소 후보키 도출)", font=("맑은 고딕", 11, "bold"), bg="#9C27B0", fg="white", bd=0, height=3, command=self.run_candidate_key_finder)
        self.btn4.pack(fill="x", padx=10, pady=10)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(tab2, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 10))

        # [3] 공통 로그 모니터 
        log_frame = tk.Frame(self, bg="#1E1E1E", padx=20, pady=5)
        log_frame.pack(fill="both", expand=True)

        log_header_frame = tk.Frame(log_frame, bg="#1E1E1E")
        log_header_frame.pack(fill="x", pady=(0, 5))

        tk.Label(log_header_frame, text="실시간 실행 로그", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        
        btn_clear_log = tk.Button(log_header_frame, text="🗑️ 로그 초기화", font=("맑은 고딕", 9), bg="#555555", fg="white", bd=0, padx=10, command=self.clear_log)
        btn_clear_log.pack(side="right")
        
        self.log_area = scrolledtext.ScrolledText(log_frame, font=("Consolas", 9), bg="#121212", fg="#00FF66", insertbackground="white", bd=1, relief="solid")
        self.log_area.pack(fill="both", expand=True, pady=(0, 15))

        self.log(f"✅ 프로그램 준비 완료! 시작 경로: {self.target_dir}")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ============ 공통 UI 로직 ============
    def clear_log(self):
        self.log_area.delete(1.0, tk.END)
        self.log("✨ 로그 화면이 초기화되었습니다.")

    def log(self, message):
        self.after(0, self._insert_log, message)

    def _insert_log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def set_buttons_state(self, state):
        flag = tk.NORMAL if state else tk.DISABLED
        self.btn1.config(state=flag)
        self.btn2.config(state=flag)
        self.btn4.config(state=flag)
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
            self.log(f"\n📂 작업 경로 변경됨: {self.target_dir}")
            if self.is_watching:
                self.log("🔄 설정 변경으로 인해 감시기를 재시작합니다...")
                self.stop_watcher()
                self.start_watcher()

    def on_option_changed(self):
        state = "포함" if self.include_subdirs.get() else "제외"
        self.log(f"\n⚙️ 옵션 변경: 하위 폴더 {state}")
        if self.is_watching:
            self.stop_watcher()
            self.start_watcher()

    # ============ [탭 1] 변환기 구동 로직 ============
    def run_xlsx_to_csv_all(self):
        def task():
            self.set_buttons_state(False)
            self.log("\n🚀 [작업 시작] 전체 XLSX ➔ UTF-8 CSV 변환")
            count = 0
            for root, dirs, files in os.walk(self.target_dir):
                dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
                if not self.include_subdirs.get(): dirs.clear() 

                for file in files:
                    if file.startswith('Disabled'): continue
                    if file.endswith('.xlsx') and not file.startswith('~$'):
                        filepath = os.path.join(root, file)
                        self.log(f"🔄 변환 중: {file}")
                        success, result = convert_xlsx_file(filepath)
                        if success:
                            self.log(f"   └ ✅ 성공: {os.path.basename(result)}")
                            count += 1
                        else:
                            self.log(f"   └ ❌ 실패: {result}")
            self.log(f"✨ 총 {count}개 파일 변환 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def run_ansi_to_utf8_all(self):
        def task():
            self.set_buttons_state(False)
            self.log("\n🚀 [작업 시작] 전체 CSV 인코딩(UTF-8) 변환")
            count = 0
            for root, dirs, files in os.walk(self.target_dir):
                dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
                if not self.include_subdirs.get(): dirs.clear()

                for file in files:
                    if file.startswith('Disabled'): continue
                    if file.endswith('.csv'):
                        filepath = os.path.join(root, file)
                        self.log(f"🔄 점검 중: {file}")
                        success, msg = convert_ansi_csv_to_utf8(filepath)
                        if success:
                            self.log(f"   └ ✅ {msg}")
                            count += 1
                        else:
                            self.log(f"   └ ❌ 실패: {msg}")
            self.log(f"✨ 총 {count}개 CSV 파일 처리 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def start_watcher(self):
        event_handler = WatcherHandler(self.log)
        self.observer = Observer()
        is_recursive = self.include_subdirs.get()
        self.observer.schedule(event_handler, self.target_dir, recursive=is_recursive)
        self.observer.start()
        self.is_watching = True
        self.btn3.config(text="백그라운드 감시 중지 (실행 중...)", bg="#DC3545")
        self.log(f"\n🕵️‍♂️ [백그라운드 감시 시작] (하위 폴더 포함: {is_recursive})")

    def stop_watcher(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.is_watching = False
        self.btn3.config(text="백그라운드 자동 변환 감시 모드 시작", bg="#6C757D")

    def toggle_watch_mode(self):
        if not self.is_watching:
            self.start_watcher()
        else:
            self.stop_watcher()
            self.log("\n🛑 [백그라운드 감시 중지] 정상 종료됨.")

    # ============ [탭 2] 데이터 무결성 검증 구동 로직 ============
    def run_candidate_key_finder(self):
        def task():
            self.set_buttons_state(False)
            self.after(0, lambda: self.progress_var.set(0))
            self.log("\n🚀 [작업 시작] CSV 후보키 및 무결성 검증")
            
            csv_files = []
            for root, dirs, files in os.walk(self.target_dir):
                dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
                if not self.include_subdirs.get(): dirs.clear()
                
                for file in files:
                    if file.startswith('Disabled'): continue
                    if file.endswith('.csv'):
                        csv_files.append(os.path.join(root, file))

            if not csv_files:
                self.log("❌ 검사할 CSV 파일을 찾을 수 없습니다.")
                self.set_buttons_state(True)
                return

            max_len = self.max_combo_var.get()
            
            for csv_file in csv_files:
                self.log(f"\n▶ 파일 검사: {os.path.basename(csv_file)}")
                try:
                    try: df = pd.read_csv(csv_file, encoding='utf-8')
                    except UnicodeDecodeError: df = pd.read_csv(csv_file, encoding='cp949')
                except Exception as e:
                    self.log(f"  └ ❌ 읽기 실패: {e}")
                    continue

                total_rows = len(df)
                valid_columns = []
                ex_null, ex_special = [], []
                
                for col in df.columns:
                    if df[col].isna().any() or (df[col].dropna().astype(str).str.strip() == '').any():
                        ex_null.append(col)
                        continue
                    if df[col].dropna().astype(str).str.contains(r'[|_]', regex=True).any():
                        ex_special.append(col)
                        continue
                    valid_columns.append(col)

                if ex_null: self.log(f"  └ 🚫 제외됨 (빈 값/NaN) : {ex_null}")
                if ex_special: self.log(f"  └ 🚫 제외됨 ('|' 또는 '_'): {ex_special}")
                
                n_cols = len(valid_columns)
                if n_cols == 0:
                    self.log("  └ 검사할 유효한 컬럼이 없습니다.")
                    continue

                actual_max = min(n_cols, max_len)
                total_combos = sum(math.comb(n_cols, r) for r in range(1, actual_max + 1))
                candidate_keys = []
                processed = 0

                for r in range(1, actual_max + 1):
                    for combo in combinations(valid_columns, r):
                        time.sleep(0.001) 
                        combo_set = set(combo)
                        
                        is_minimal = True
                        for ck in candidate_keys:
                            if set(ck).issubset(combo_set):
                                is_minimal = False
                                break
                        
                        if is_minimal and len(df[list(combo)].drop_duplicates()) == total_rows:
                            candidate_keys.append(combo)
                            self.log(f"  └ ✅ [후보키] {combo}")
                        
                        processed += 1
                        progress = (processed / total_combos) * 100
                        self.after(0, lambda p=progress: self.progress_var.set(p))

                self.log(f"▷ 총 {len(candidate_keys)}개의 후보키 발견 완료.")

            self.log("\n✨ 모든 CSV 파일의 데이터 무결성 검증이 완료되었습니다!")
            self.after(0, lambda: self.progress_var.set(100))
            self.set_buttons_state(True)

        threading.Thread(target=task, daemon=True).start()

    def on_close(self):
        if self.is_watching:
            self.stop_watcher()
        self.destroy()

if __name__ == "__main__":
    app = AppGUI()
    app.mainloop()