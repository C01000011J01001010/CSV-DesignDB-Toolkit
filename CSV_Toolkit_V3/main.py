import sys
from tkinter import messagebox
from utils import check_single_instance
from gui.app_window import AppGUI

def main():
    if not check_single_instance():
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("중복 실행 방지", "이미 프로그램이 실행 중입니다!")
        root.destroy()
        sys.exit(0)

    app = AppGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
