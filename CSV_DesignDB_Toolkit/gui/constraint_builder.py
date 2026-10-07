import tkinter as tk
from tkinter import ttk
import re

def parse_constraint_string(c_str):
    c_str = c_str.strip()
    c_upper = c_str.upper()
    if c_upper == 'UNIQUE': return 'UNIQUE', None
    if c_upper == 'NOT NULL': return 'NOT NULL', None
    
    if c_upper.startswith('DEFAULT') and '(' in c_str:
        val = c_str[c_str.find('(')+1 : c_str.rfind(')')].strip()
        return 'DEFAULT', {'value': val}
        
    if c_upper.startswith('CHECK IN') and '(' in c_str:
        inner = c_str[c_str.find('(')+1 : c_str.rfind(')')]
        vals = [v.strip() for v in inner.split('|') if v.strip()]
        return 'CHECK IN', {'values': vals}
        
    if c_upper.startswith('CHECK NOT IN') and '(' in c_str:
        inner = c_str[c_str.find('(')+1 : c_str.rfind(')')]
        vals = [v.strip() for v in inner.split('|') if v.strip()]
        return 'CHECK NOT IN', {'values': vals}
        
    if c_upper.startswith('CHECK') and '(' in c_str:
        inner = c_str[c_str.find('(')+1 : c_str.rfind(')')].strip()
        tokens = re.split(r'\s+(AND|OR|XOR)\s+', inner, flags=re.IGNORECASE)
        conditions = []
        try:
            logic = ""
            for i in range(0, len(tokens), 2):
                expr = tokens[i].strip()
                if i > 0: logic = tokens[i-1].strip().upper()
                
                match = re.match(r'VALUE\s*(==|!=|>=|<=|>|<)\s*(.+)', expr, re.IGNORECASE)
                if match:
                    comp = match.group(1)
                    val = match.group(2).strip()
                    conditions.append({'logic': logic, 'comp': comp, 'val': val})
                else:
                    raise Exception("Parse fail")
            return 'CHECK', {'conditions': conditions}
        except: pass
    
    return 'RAW', {'value': c_str}

class ConstraintWidget(tk.Frame):
    def __init__(self, parent, c_type, init_data=None):
        super().__init__(parent, bg="#333333", bd=1, relief="solid")
        self.c_type = c_type
        
        top = tk.Frame(self, bg="#333333")
        top.pack(fill="x", padx=5, pady=2)
        tk.Label(top, text=c_type, bg="#333333", fg="#FFD700", font=("Consolas", 10, "bold")).pack(side="left")
        tk.Button(top, text="🗑️", bg="#DC3545", fg="white", bd=0, padx=5, pady=0, font=("맑은 고딕", 8), command=self.destroy).pack(side="right")
        
        self.content = tk.Frame(self, bg="#333333")
        self.content.pack(fill="x", padx=10, pady=(0,5))
        
        self.entries = []
        self.conditions = []
        
        if c_type == 'DEFAULT':
            e = tk.Entry(self.content, width=20, font=("Consolas", 10))
            e.pack(anchor="w")
            if init_data: e.insert(0, init_data.get('value', ''))
            self.entries.append(e)
            
        elif c_type in ['CHECK IN', 'CHECK NOT IN']:
            btn = tk.Button(self.content, text="+ 값 추가", bg="#555555", fg="white", bd=0, command=lambda: self.add_entry())
            btn.pack(anchor="w", pady=2)
            if init_data and init_data.get('values'):
                for v in init_data.get('values', []): self.add_entry(v)
            else:
                self.add_entry()
                
        elif c_type == 'CHECK':
            btn = tk.Button(self.content, text="+ 조건식 추가", bg="#555555", fg="white", bd=0, command=lambda: self.add_condition())
            btn.pack(anchor="w", pady=2)
            if init_data and init_data.get('conditions'):
                for c in init_data.get('conditions', []): self.add_condition(c)
            else:
                self.add_condition()
                
        elif c_type == 'RAW':
            e = tk.Entry(self.content, width=40, font=("Consolas", 10))
            e.pack(anchor="w")
            if init_data: e.insert(0, init_data.get('value', ''))
            self.entries.append(e)

    def add_entry(self, val=""):
        row = tk.Frame(self.content, bg="#333333")
        row.pack(fill="x", pady=2)
        e = tk.Entry(row, width=15, font=("Consolas", 10))
        e.insert(0, val)
        e.pack(side="left")
        tk.Button(row, text="X", bg="#DC3545", fg="white", bd=0, width=2, command=lambda r=row, ent=e: self.remove_entry(r, ent)).pack(side="left", padx=5)
        self.entries.append(e)
        
    def remove_entry(self, row, e):
        if e in self.entries: self.entries.remove(e)
        row.destroy()
        
    def add_condition(self, data=None):
        row = tk.Frame(self.content, bg="#333333")
        row.pack(fill="x", pady=2)
        
        is_first = len(self.conditions) == 0
        logic_cb = ttk.Combobox(row, values=["AND", "OR", "XOR"], state="readonly", width=5)
        logic_cb.set(data.get('logic', 'AND') if data and not is_first else "AND")
        if not is_first: logic_cb.pack(side="left", padx=(0, 5))
        
        tk.Label(row, text="VALUE", bg="#333333", fg="#00FF66", font=("Consolas", 10, "bold")).pack(side="left")
        comp_cb = ttk.Combobox(row, values=["==", "!=", ">", ">=", "<", "<="], state="readonly", width=4)
        comp_cb.set(data.get('comp', '==') if data else "==")
        comp_cb.pack(side="left", padx=5)
        
        val_e = tk.Entry(row, width=10, font=("Consolas", 10))
        if data: val_e.insert(0, data.get('val', ''))
        val_e.pack(side="left", padx=5)
        
        tk.Button(row, text="X", bg="#DC3545", fg="white", bd=0, width=2, command=lambda r=row, cond=(logic_cb, comp_cb, val_e): self.remove_condition(r, cond)).pack(side="left")
        self.conditions.append((logic_cb, comp_cb, val_e))
        
    def remove_condition(self, row, cond):
        if cond in self.conditions: self.conditions.remove(cond)
        row.destroy()
        
    def get_value(self):
        if self.c_type in ['UNIQUE', 'NOT NULL']: return self.c_type
        elif self.c_type == 'DEFAULT': return f"DEFAULT({self.entries[0].get()})"
        elif self.c_type in ['CHECK IN', 'CHECK NOT IN']:
            vals = [e.get() for e in self.entries if e.get().strip()]
            if not vals: return None
            return f"{self.c_type}({'|'.join(vals)})"
        elif self.c_type == 'CHECK':
            conds = []
            for i, (l, c, v) in enumerate(self.conditions):
                val = v.get().strip()
                if not val: continue
                if i == 0: conds.append(f"VALUE {c.get()} {val}")
                else: conds.append(f" {l.get()} VALUE {c.get()} {val}")
            if not conds: return None
            return f"CHECK({''.join(conds)})"
        elif self.c_type == 'RAW':
            val = self.entries[0].get().upper()
            if 'PK' in val or 'REF' in val or 'PRIMARYKEY' in val or 'REFERENCE' in val: return None 
            return self.entries[0].get()

class ColumnConstraintBuilder(tk.Frame):
    def __init__(self, parent, col_name, col_type, constraints_list):
        super().__init__(parent, bg="#252526", bd=1, relief="solid")
        self.col_name = col_name
        self.col_type = col_type
        
        header = tk.Frame(self, bg="#252526")
        header.pack(fill="x", padx=10, pady=5)
        tk.Label(header, text=f"■ {col_name}", bg="#252526", fg="#00FF66", font=("맑은 고딕", 11, "bold")).pack(side="left")
        if col_type:
            tk.Label(header, text=f"({col_type})", bg="#252526", fg="#CCCCCC", font=("Consolas", 10)).pack(side="left", padx=5)
        
        add_frame = tk.Frame(header, bg="#252526")
        add_frame.pack(side="right")
        self.lbl_error = tk.Label(add_frame, text="", bg="#252526", fg="#FF5555", font=("맑은 고딕", 9, "bold"))
        self.lbl_error.pack(side="left", padx=10)
        
        self.cb_type = ttk.Combobox(add_frame, values=["UNIQUE", "NOT NULL", "DEFAULT", "CHECK", "CHECK IN", "CHECK NOT IN"], state="readonly", width=12)
        self.cb_type.set("UNIQUE")
        self.cb_type.pack(side="left", padx=5)
        tk.Button(add_frame, text="+ 제약조건 추가", bg="#007ACC", fg="white", bd=0, font=("맑은 고딕", 9), command=self.add_new).pack(side="left")
        
        self.c_container = tk.Frame(self, bg="#252526")
        self.c_container.pack(fill="x", padx=10, pady=(0, 10))
        
        for c_str in constraints_list:
            ctype, cdata = parse_constraint_string(c_str)
            if ctype in ['PK', 'REF']: continue
            self.add_widget(ctype, cdata)
            
    def show_error(self, msg):
        self.lbl_error.config(text=f"❌ {msg}")
        self.after(3000, lambda: self.lbl_error.config(text=""))
            
    def add_new(self):
        new_type = self.cb_type.get()
        current_types = [child.c_type for child in self.c_container.winfo_children() if isinstance(child, ConstraintWidget)]
        
        if new_type in current_types:
            self.show_error("동일 제약조건 존재")
            return
        if new_type == "UNIQUE" and "DEFAULT" in current_types:
            self.show_error("UNIQUE와 DEFAULT 공존불가")
            return
        if new_type == "DEFAULT" and "UNIQUE" in current_types:
            self.show_error("UNIQUE와 DEFAULT 공존불가")
            return
            
        self.lbl_error.config(text="")
        self.add_widget(new_type, None)
        
    def add_widget(self, ctype, cdata):
        cw = ConstraintWidget(self.c_container, ctype, cdata)
        cw.pack(side="top", fill="x", pady=2)
        
    def get_constraints(self):
        current_types = [c.c_type for c in self.c_container.winfo_children() if isinstance(c, ConstraintWidget)]
        if "UNIQUE" in current_types and "DEFAULT" in current_types:
            self.show_error("저장 불가: UNIQUE & DEFAULT")
            return None
        if len(current_types) != len(set(current_types)):
            self.show_error("저장 불가: 중복 제약조건")
            return None

        res = []
        for child in self.c_container.winfo_children():
            if isinstance(child, ConstraintWidget):
                val = child.get_value()
                if val: res.append(val)
        return res
