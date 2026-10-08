import tkinter as tk
from tkinter import ttk

class RightPanel(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#1E1E1E", *args, **kwargs)
        
        header_frame = tk.Frame(self, bg="#1E1E1E")
        header_frame.pack(fill="x", pady=(0, 5))

        tk.Label(header_frame, text="실시간 실행 로그", font=("맑은 고딕", 10, "bold"), fg="#CCCCCC", bg="#1E1E1E").pack(side="left")
        
        btn_clear_log = tk.Button(header_frame, text="🗑️ 로그 초기화", font=("맑은 고딕", 9), bg="#555555", fg="white", bd=0, padx=10, command=self.clear_log)
        btn_clear_log.pack(side="right")
        
        text_container = tk.Frame(self, bg="#1E1E1E")
        text_container.pack(fill="both", expand=True)
        
        self.log_area = tk.Text(text_container, font=("Consolas", 9), bg="#121212", fg="#00FF66", insertbackground="white", bd=1, relief="solid", wrap="char")
        
        scroll_y = ttk.Scrollbar(text_container, orient="vertical", command=self.log_area.yview)
        self.log_area.configure(yscrollcommand=scroll_y.set)
        
        self.log_area.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        
        text_container.grid_rowconfigure(0, weight=1)
        text_container.grid_columnconfigure(0, weight=1)

    def clear_log(self):
        self.log_area.delete(1.0, tk.END)
        self.log("✨ 로그 화면이 초기화되었습니다.")

    def log(self, message):
        self.after(0, self._insert_log, message)

    def _insert_log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
