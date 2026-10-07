import tkinter as tk
from tkinter import ttk

class ScrollableFrame(tk.Frame):
    def __init__(self, container, bg_color="#1E1E1E", *args, **kwargs):
        super().__init__(container, bg=bg_color, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0)
        self.scrollbar_y = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner_frame = tk.Frame(self.canvas, bg=bg_color)
        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set)
        
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.canvas.bind('<Enter>', self._bind_mousewheel)
        self.canvas.bind('<Leave>', self._unbind_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        if self.inner_frame.winfo_reqheight() > self.canvas.winfo_height():
            scroll_dir = int(-1 * (event.delta / 120))
            self.canvas.yview_scroll(scroll_dir, "units")
