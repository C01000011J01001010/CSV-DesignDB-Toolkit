import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
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
    lock_file_path = os.path.join(temp_dir, "excel_csv_converter.lock")
    try:
        lock_file_handle = open(lock_file_path, "w")
        if msvcrt:
            msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
    except (IOError, OSError):
        return False
    return True

# 👉 [수정됨] 시작 시 인자(sys.argv)가 있으면 해당 경로로, 없으면 현재 프로그램 경로로 설정
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

class AppGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        if not check_single_instance():
            messagebox.showwarning("중복 실행 방지", "이미 프로그램이 실행 중입니다!\n기존 창이나 백그라운드 프로세스를 확인해 주세요.")
            sys.exit()

        self.title("엑셀 / CSV 변환 & 백그라운드 자동 감시기")
        self.geometry("720x680")
        self.configure(bg="#1E1E1E")
        self.resizable(False, False)

        self.target_dir = get_initial_dir()
        self.is_watching = False
        self.observer = None
        
        # 하위 폴더 포함 여부 (기본값: True)
        self.include_subdirs = tk.BooleanVar(value=True)

        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')

        # [1] 타이틀 헤더
        header_frame = tk.Frame(self, bg="#2D2D2D", pady=10)
        header_frame.pack(fill="x")
        
        title_label = tk.Label(header_frame, text="📁 Excel & CSV Multi-Converter", font=("Segoe UI", 16, "bold"), fg="#FFFFFF", bg="#2D2D2D")
        title_label.pack()
        info_label = tk.Label(header_frame, text="※ 'Disabled'로 시작하는 폴더/파일은 제외됩니다.", font=("맑은 고딕", 9), fg="#FFA500", bg="#2D2D2D")
        info_label.pack()

        # 👉 [추가됨] [2] 디렉터리 네비게이션 프레임
        nav_frame = tk.Frame(self, bg="#1E1E1E", pady=10, padx=20)
        nav_frame.pack(fill="x")

        tk.Label(nav_frame, text="작업 경로:", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        
        self.path_entry_var = tk.StringVar(value=self.target_dir)
        self.path_entry = tk.Entry(nav_frame, textvariable=self.path_entry_var, font=("Consolas", 10), bg="#2D2D2D", fg="white", insertbackground="white", bd=1, relief="solid")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.path_entry.bind('<Return>', lambda event: self.apply_manual_path())

        btn_go = tk.Button(nav_frame, text="이동", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.apply_manual_path)
        btn_go.pack(side="left", padx=(0, 5))

        btn_up = tk.Button(nav_frame, text="⬆ 상위", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.go_up_dir)
        btn_up.pack(side="left", padx=2)

        btn_browse = tk.Button(nav_frame, text="🔍 탐색", font=("맑은 고딕", 9), bg="#444444", fg="white", bd=0, command=self.browse_dir)
        btn_browse.pack(side="left", padx=2)

        # 👉 [추가됨] [3] 옵션 프레임 (하위 폴더 토글)
        opt_frame = tk.Frame(self, bg="#1E1E1E", padx=20)
        opt_frame.pack(fill="x")
        
        chk_subdirs = tk.Checkbutton(opt_frame, text="하위 폴더 포함하여 적용 (재귀적 탐색 및 감시)", 
                                     variable=self.include_subdirs, font=("맑은 고딕", 10),
                                     bg="#1E1E1E", fg="#CCCCCC", selectcolor="#2D2D2D", 
                                     activebackground="#1E1E1E", activeforeground="white", command=self.on_option_changed)
        chk_subdirs.pack(anchor="w")

        # [4] 메인 버튼 구역
        btn_frame = tk.Frame(self, bg="#1E1E1E", pady=10, padx=20)
        btn_frame.pack(fill="x")

        self.btn1 = tk.Button(btn_frame, text="1. 전체 XLSX ➔ UTF-8 CSV 일괄 변환", font=("맑은 고딕", 11, "bold"),
                              bg="#007ACC", fg="white", activebackground="#005999", activeforeground="white",
                              bd=0, relief="flat", height=2, command=self.run_xlsx_to_csv_all)
        self.btn1.pack(fill="x", pady=5)

        self.btn2 = tk.Button(btn_frame, text="2. 전체 CSV (ANSI ➔ UTF-8) 인코딩 일괄 변환", font=("맑은 고딕", 11, "bold"),
                              bg="#28A745", fg="white", activebackground="#1E7E34", activeforeground="white",
                              bd=0, relief="flat", height=2, command=self.run_ansi_to_utf8_all)
        self.btn2.pack(fill="x", pady=5)

        self.btn3 = tk.Button(btn_frame, text="3. 백그라운드 자동 감시 모드 시작", font=("맑은 고딕", 11, "bold"),
                              bg="#6C757D", fg="white", activebackground="#545B62", activeforeground="white",
                              bd=0, relief="flat", height=2, command=self.toggle_watch_mode)
        self.btn3.pack(fill="x", pady=5)

        # [5] 로그 모니터 프레임
        log_frame = tk.Frame(self, bg="#1E1E1E", padx=20, pady=5)
        log_frame.pack(fill="both", expand=True)

        log_label = tk.Label(log_frame, text="실시간 실행 로그", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E")
        log_label.pack(anchor="w", pady=(0, 5))

        self.log_area = scrolledtext.ScrolledText(log_frame, font=("Consolas", 9), bg="#121212", fg="#00FF66",
                                                  insertbackground="white", bd=1, relief="solid")
        self.log_area.pack(fill="both", expand=True, pady=(0, 15))

        self.log(f"✅ 프로그램 준비 완료! 시작 경로: {self.target_dir}")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ============ 디렉터리 이동 로직 ============
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
            self.restart_watcher_if_needed()

    def on_option_changed(self):
        state = "포함" if self.include_subdirs.get() else "제외"
        self.log(f"\n⚙️ 옵션 변경: 하위 폴더 {state}")
        self.restart_watcher_if_needed()

    def restart_watcher_if_needed(self):
        if self.is_watching:
            self.log("🔄 설정 변경으로 인해 감시기를 새 설정으로 재시작합니다...")
            self.stop_watcher()
            self.start_watcher()

    # ============ 코어 로직 ============
    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def set_buttons_state(self, state):
        flag = tk.NORMAL if state else tk.DISABLED
        self.btn1.config(state=flag)
        self.btn2.config(state=flag)
        self.path_entry.config(state=flag)

    def run_xlsx_to_csv_all(self):
        def task():
            self.set_buttons_state(False)
            self.log("\n==========================================")
            self.log("🚀 [작업 시작] 전체 XLSX ➔ UTF-8 CSV 변환")
            self.log("==========================================")
            
            count = 0
            for root, dirs, files in os.walk(self.target_dir):
                # Disabled 하위 폴더 제외
                dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
                
                # 👉 [추가됨] 하위 폴더 포함 옵션이 꺼져있으면 첫(루트) 디렉터리만 탐색하고 os.walk 중지
                if not self.include_subdirs.get():
                    dirs.clear() 

                for file in files:
                    if file.startswith('Disabled'):
                        continue
                        
                    if file.endswith('.xlsx') and not file.startswith('~$'):
                        filepath = os.path.join(root, file)
                        self.log(f"🔄 변환 중: {file}")
                        success, result = convert_xlsx_file(filepath)
                        if success:
                            self.log(f"   └ ✅ 성공: {os.path.basename(result)}")
                            count += 1
                        else:
                            self.log(f"   └ ❌ 실패: {result}")
            
            self.log(f"\n✨ 총 {count}개 파일 변환 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    def run_ansi_to_utf8_all(self):
        def task():
            self.set_buttons_state(False)
            self.log("\n==========================================")
            self.log("🚀 [작업 시작] 전체 CSV 인코딩(UTF-8) 변환")
            self.log("==========================================")
            
            count = 0
            for root, dirs, files in os.walk(self.target_dir):
                dirs[:] = [d for d in dirs if not d.startswith('Disabled')]
                
                # 👉 [추가됨] 하위 폴더 옵션 검사
                if not self.include_subdirs.get():
                    dirs.clear()

                for file in files:
                    if file.startswith('Disabled'):
                        continue
                        
                    if file.endswith('.csv'):
                        filepath = os.path.join(root, file)
                        self.log(f"🔄 점검 중: {file}")
                        success, msg = convert_ansi_csv_to_utf8(filepath)
                        if success:
                            self.log(f"   └ ✅ {msg}")
                            count += 1
                        else:
                            self.log(f"   └ ❌ 실패: {msg}")
                            
            self.log(f"\n✨ 총 {count}개 CSV 파일 처리 완료!")
            self.set_buttons_state(True)
        threading.Thread(target=task, daemon=True).start()

    # ============ 백그라운드 감시기 제어 ============
    def start_watcher(self):
        event_handler = WatcherHandler(self.log)
        self.observer = Observer()
        # 👉 [수정됨] 하위 폴더 포함 여부(recursive)를 체크박스 값에 따라 동적으로 할당
        is_recursive = self.include_subdirs.get()
        self.observer.schedule(event_handler, self.target_dir, recursive=is_recursive)
        self.observer.start()
        self.is_watching = True
        self.btn3.config(text="3. 백그라운드 감시 중지 (실행 중...)", bg="#DC3545", activebackground="#BD2130")
        self.log(f"\n🕵️‍♂️ [백그라운드 감시 시작] (하위 폴더 포함: {is_recursive})")

    def stop_watcher(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.is_watching = False
        self.btn3.config(text="3. 백그라운드 자동 감시 모드 시작", bg="#6C757D", activebackground="#545B62")

    def toggle_watch_mode(self):
        if not self.is_watching:
            self.start_watcher()
        else:
            self.stop_watcher()
            self.log("\n🛑 [백그라운드 감시 중지] 정상 종료됨.")

    def on_close(self):
        if self.is_watching:
            self.stop_watcher()
        self.destroy()

if __name__ == "__main__":
    app = AppGUI()
    app.mainloop()