import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
from utils.shared import get_target_language, center_window, CONFIG
import pandas as pd
import re
import shutil
from lxml import etree

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)

    def schedule(self, event):
        self.id = self.widget.after(600, self.show)

    def show(self):
        if self.tip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=LEFT,
                         background="#ffffe0", relief=SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide(self, event):
        if self.id: self.widget.after_cancel(self.id); self.id = None
        if self.tip_window: self.tip_window.destroy(); self.tip_window = None

class AddTermDialog(ttk.Toplevel):
    def __init__(self, parent, current_file, glossary_logic_callback):
        super().__init__(parent)
        self.title("Add Glossary Term")
        center_window(self, 500, 550, parent)
        self.logic_callback = glossary_logic_callback # Function to reload glossary in main app
        
        # Get defaults
        initial_source = ""
        try: initial_source = parent.txt_source.get("sel.first", "sel.last")
        except: pass
        
        # UI Construction
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=BOTH, expand=True)

        ttk.Label(main_frame, text="Source Term:", font=("Helvetica", 10, "bold"), bootstyle="info").pack(anchor=W, pady=(0, 5))
        self.e_src = ttk.Entry(main_frame, width=40)
        self.e_src.pack(fill=X, pady=(0, 15))
        self.e_src.insert(0, initial_source)
        
        ttk.Label(main_frame, text="Translation:", font=("Helvetica", 10, "bold"), bootstyle="info").pack(anchor=W, pady=(0, 5))
        self.e_tgt = ttk.Entry(main_frame, width=40)
        self.e_tgt.pack(fill=X, pady=(0, 15))
        
        ttk.Label(main_frame, text="Language Code:", font=("Helvetica", 10, "bold"), bootstyle="info").pack(anchor=W, pady=(0, 5))
        
        self.all_langs = CONFIG.get("protected_languages", [])
        default_lang = ""
        if current_file: default_lang = get_target_language(current_file)
        
        self.c_lang = ttk.Combobox(main_frame, values=self.all_langs, width=38)
        self.c_lang.pack(fill=X, pady=(0, 15))
        self.c_lang.set(default_lang)
        self.c_lang.bind('<KeyRelease>', self.filter_lang_options)

        # Advanced
        adv_frame = ttk.Labelframe(main_frame, text="Advanced Settings", padding=10, bootstyle="secondary")
        adv_frame.pack(fill=X, pady=(5, 10))
        
        r1 = ttk.Frame(adv_frame); r1.pack(fill=X, pady=5)
        ttk.Label(r1, text="Match Type:").pack(side=LEFT)
        self.match_var = tk.StringVar(value="partial")
        ttk.Combobox(r1, textvariable=self.match_var, values=("partial", "exact", "regex"), state="readonly", width=10).pack(side=LEFT, padx=(5, 15))
        
        ttk.Label(r1, text="Context:").pack(side=LEFT)
        self.e_context = ttk.Entry(r1, width=15)
        self.e_context.pack(side=LEFT, padx=5, fill=X, expand=True)

        r2 = ttk.Frame(adv_frame); r2.pack(fill=X, pady=5)
        self.case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r2, text="Case Sensitive", variable=self.case_var).pack(side=LEFT, padx=(0, 15))
        self.forbidden_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r2, text="Mark as Forbidden", variable=self.forbidden_var).pack(side=LEFT)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=BOTTOM, fill=X, pady=(10, 0))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle="secondary").pack(side=RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Save Term", command=self.save_term, bootstyle="success").pack(side=RIGHT)

        if initial_source: self.e_tgt.focus_set()
        else: self.e_src.focus_set()

    def filter_lang_options(self, event):
        if event.keysym in ['Up', 'Down', 'Return', 'Left', 'Right', 'Tab']: return
        typed = self.c_lang.get()
        if typed == '': self.c_lang['values'] = self.all_langs
        else: self.c_lang['values'] = [x for x in self.all_langs if typed.lower() in x.lower()]
        try: 
            if self.c_lang['values']: self.c_lang.tk.call('ttk::combobox::Post', self.c_lang._w)
        except: pass

    def save_term(self):
        s, t, l = self.e_src.get().strip(), self.e_tgt.get().strip(), self.c_lang.get().strip()
        if not s or not t: messagebox.showwarning("Missing Data", "Source and Target are required."); return
        
        g_path = Path("glossary.xlsx")
        new_row = {
            "source_text": s, "target_text": t, "language_code": l,
            "match_type": self.match_var.get(), "case_sensitive": str(self.case_var.get()).upper(),
            "context": self.e_context.get().strip(), "is_forbidden": str(self.forbidden_var.get()).upper()
        }
        try:
            if g_path.exists():
                df = pd.read_excel(g_path).fillna("")
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            else: df = pd.DataFrame([new_row])
            df.to_excel(g_path, index=False)
            
            # Callback to main app to refresh glossary
            self.logic_callback() 
            messagebox.showinfo("Success", "Term added.")
            self.destroy()
        except PermissionError: messagebox.showerror("File Locked", "Close glossary.xlsx first.")
        except Exception as e: messagebox.showerror("Error", f"Failed: {e}")

class FindReplaceDialog(ttk.Toplevel):
    def __init__(self, parent, current_folder, current_file, file_map, load_file_callback):
        super().__init__(parent)
        self.title("Find & Replace")
        center_window(self, 700, 800, parent)
        
        self.current_folder = current_folder
        self.current_file = current_file
        self.file_map = file_map
        self.load_file_callback = load_file_callback
        self.parent = parent # Reference to editor tab for tree access

        # Inputs
        f1 = ttk.Frame(self, padding=10); f1.pack(fill=X)
        ttk.Label(f1, text="Find:").pack(anchor=W); self.e_find = ttk.Entry(f1); self.e_find.pack(fill=X)
        ttk.Label(f1, text="Replace:").pack(anchor=W); self.e_repl = ttk.Entry(f1); self.e_repl.pack(fill=X)
        
        # Options
        f2 = ttk.Frame(self, padding=10); f2.pack(fill=X)
        self.var_case = tk.BooleanVar(); ttk.Checkbutton(f2, text="Match Case", variable=self.var_case).pack(anchor=W)
        self.var_regex = tk.BooleanVar(); ttk.Checkbutton(f2, text="Regex", variable=self.var_regex).pack(anchor=W)
        self.var_back = tk.BooleanVar(value=True); ttk.Checkbutton(f2, text="Backup", variable=self.var_back).pack(anchor=W)
        self.var_scope = tk.StringVar(value="current_file")
        ttk.Radiobutton(f2, text="Current File", variable=self.var_scope, value="current_file").pack(anchor=W)
        ttk.Radiobutton(f2, text="All Files", variable=self.var_scope, value="all_files").pack(anchor=W)

        # Progress & Results
        self.prog = ttk.Progressbar(self, mode='determinate'); self.prog.pack(fill=X, padx=10, pady=10)
        self.res_tree = ttk.Treeview(self, columns=("file", "id", "txt"), show="headings")
        self.res_tree.pack(fill=BOTH, expand=True, padx=10)
        self.res_tree.heading("file", text="File"); self.res_tree.heading("id", text="ID"); self.res_tree.heading("txt", text="Text")
        self.res_tree.bind("<Double-1>", self.jump_to_result)

        # Buttons
        btn_frame = ttk.Frame(self, padding=10); btn_frame.pack(fill=X)
        ttk.Button(btn_frame, text="Find", command=lambda: self.run_thread("find")).pack(side=LEFT, padx=10)
        ttk.Button(btn_frame, text="Replace All", command=lambda: self.run_thread("replace")).pack(side=LEFT, padx=10)

    def jump_to_result(self, event):
        sel = self.res_tree.selection()
        if not sel: return
        item = self.res_tree.item(sel[0]); f = item['tags'][0]; tid = item['values'][1]
        
        # Call back to parent to load the file
        if str(self.current_file) != str(f): 
            self.load_file_callback(f)
            
        # Select row in parent tree
        # Note: This assumes parent.tree is accessible. 
        # A cleaner way is to pass a "select_id" callback, but direct access works for now.
        try:
            self.parent.tree.selection_remove(self.parent.tree.selection())
            for c in self.parent.tree.get_children():
                if str(self.parent.tree.item(c, 'values')[0]) == str(tid): 
                    self.parent.tree.selection_set(c)
                    self.parent.tree.see(c)
                    self.parent.on_row_select(None)
                    break
        except: pass

    def run_thread(self, mode):
        import threading
        threading.Thread(target=lambda: self.run_process(mode)).start()

    def run_process(self, mode):
        find = self.e_find.get(); repl = self.e_repl.get()
        if not find: return
        
        files = [Path(self.current_file)] if self.var_scope.get() == "current_file" else [f for l in self.file_map.values() for f in l]
        
        pat = None
        if self.var_regex.get():
            try: pat = re.compile(find, 0 if self.var_case.get() else re.I)
            except: messagebox.showerror("Error", "Bad Regex"); return

        self.prog['maximum'] = len(files); hits = 0; mods = 0
        namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}

        for i, fp in enumerate(files):
            try:
                t = etree.parse(str(fp)); dirty = False
                for tu in t.xpath('//xliff:trans-unit', namespaces=namespaces):
                    tn = tu.find('xliff:target', namespaces=namespaces)
                    if tn is not None and tn.text:
                        orig = tn.text; new = orig; found = False
                        if self.var_regex.get(): 
                            if pat.search(orig): found=True; new=pat.sub(repl, orig) if mode=="replace" else orig
                        else:
                            if self.var_case.get(): found=(find in orig); new=orig.replace(find, repl) if found and mode=="replace" else orig
                            else: found=(find.lower() in orig.lower()); new=re.compile(re.escape(find), re.I).sub(repl, orig) if found and mode=="replace" else orig
                        
                        if found:
                            hits+=1
                            if mode=="find": self.res_tree.insert("", "end", values=(fp.name, tu.get('id'), orig[:50]), tags=(str(fp),))
                            if mode=="replace" and new!=orig: tn.text=new; tn.set('state', 'translated'); dirty=True
                
                if dirty and mode=="replace":
                    mods+=1
                    if self.var_back.get(): shutil.copy2(fp, str(fp)+".bak")
                    t.write(str(fp), encoding="UTF-8", xml_declaration=True, pretty_print=True)
            except: pass
            self.prog['value'] = i+1; self.update_idletasks()
        
        if mode=="replace": 
            messagebox.showinfo("Done", f"Replaced {hits} in {mods} files.")
            if self.current_file: self.load_file_callback(self.current_file)
