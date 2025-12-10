import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
# UPDATED IMPORTS:
from utils.core import get_target_language, CONFIG
from utils.gui_utils import center_window
from utils.glossary import add_term_to_file
import pandas as pd
import re
from lxml import etree
import shutil

# ... (The rest of the file content remains exactly as it was)
# You only need to change the lines 'from utils.shared import ...' at the top.

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
        self.logic_callback = glossary_logic_callback
        
        initial_source = ""
        try: initial_source = parent.txt_source.get("sel.first", "sel.last")
        except: pass
        
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
            add_term_to_file(g_path, new_row)
            self.logic_callback() 
            messagebox.showinfo("Success", "Term added.")
            self.destroy()
        except PermissionError: messagebox.showerror("File Locked", "Close glossary.xlsx first.")
        except Exception as e: messagebox.showerror("Error", f"Failed: {e}")

class FindReplacePane(ttk.Labelframe):
    def __init__(self, parent, editor_instance):
        super().__init__(parent, text="Find & Replace", padding=5, bootstyle="warning")
        self.editor = editor_instance
        
        # --- COMPACT HEADER (Grid Layout) ---
        input_frame = ttk.Frame(self)
        input_frame.pack(fill=X, pady=2)
        
        ttk.Label(input_frame, text="Find:").grid(row=0, column=0, sticky="w", padx=2)
        self.e_find = ttk.Entry(input_frame)
        self.e_find.grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(input_frame, text="Find", command=lambda: self.run_thread("find"), bootstyle="info-outline", width=6).grid(row=0, column=2, padx=2)
        
        ttk.Label(input_frame, text="Repl:").grid(row=1, column=0, sticky="w", padx=2)
        self.e_repl = ttk.Entry(input_frame)
        self.e_repl.grid(row=1, column=1, sticky="ew", padx=2)
        ttk.Button(input_frame, text="All", command=lambda: self.run_thread("replace"), bootstyle="danger-outline", width=6).grid(row=1, column=2, padx=2)
        
        input_frame.columnconfigure(1, weight=1)

        # --- COMPACT OPTIONS ---
        opt_frame = ttk.Frame(self)
        opt_frame.pack(fill=X, pady=2)
        
        self.var_case = tk.BooleanVar(); ttk.Checkbutton(opt_frame, text="Case", variable=self.var_case).pack(side=LEFT, padx=2)
        self.var_regex = tk.BooleanVar(); ttk.Checkbutton(opt_frame, text="Regex", variable=self.var_regex).pack(side=LEFT, padx=2)
        self.var_back = tk.BooleanVar(value=True); ttk.Checkbutton(opt_frame, text="Backup", variable=self.var_back).pack(side=LEFT, padx=2)

        # --- SCOPE SELECTION ---
        scope_frame = ttk.Frame(self)
        scope_frame.pack(fill=X, pady=2)
        ttk.Label(scope_frame, text="Scope:", font=("Helvetica", 8, "bold")).pack(side=LEFT)
        self.var_scope = tk.StringVar(value="current_file")
        
        ttk.Radiobutton(scope_frame, text="File", variable=self.var_scope, value="current_file").pack(side=LEFT, padx=2)
        ttk.Radiobutton(scope_frame, text="Lang", variable=self.var_scope, value="current_lang").pack(side=LEFT, padx=2)
        ttk.Radiobutton(scope_frame, text="All", variable=self.var_scope, value="all_files").pack(side=LEFT, padx=2)

        # --- RESULTS TREE ---
        self.res_tree = ttk.Treeview(self, columns=("loc", "txt"), show="headings", height=6)
        self.res_tree.heading("loc", text="Loc"); self.res_tree.column("loc", width=60)
        self.res_tree.heading("txt", text="Match"); self.res_tree.column("txt", width=120)
        self.res_tree.pack(fill=BOTH, expand=True, pady=2)
        self.res_tree.bind("<Double-1>", self.jump_to_result)
        
        self.prog = ttk.Progressbar(self, mode='determinate', bootstyle="warning-striped")
        self.prog.pack(fill=X, pady=(2,0))

    def run_thread(self, mode):
        import threading
        threading.Thread(target=lambda: self.run_process(mode)).start()

    def run_process(self, mode):
        find = self.e_find.get(); repl = self.e_repl.get()
        if not find: return
        
        current_f = self.editor.current_file
        file_map = self.editor.file_map
        scope = self.var_scope.get()
        
        if not current_f and scope != "all_files": return

        files = []
        if scope == "current_file":
            files = [Path(current_f)]
        elif scope == "current_lang":
            cur_lang = get_target_language(current_f)
            if cur_lang in file_map:
                files = file_map[cur_lang]
        else: # All files
            for l in file_map.values(): files.extend(l)
        
        pat = None
        if self.var_regex.get():
            try: pat = re.compile(find, 0 if self.var_case.get() else re.I)
            except: messagebox.showerror("Error", "Bad Regex"); return

        self.prog['maximum'] = len(files); hits = 0; mods = 0
        namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        
        if mode == "find":
            for i in self.res_tree.get_children(): self.res_tree.delete(i)

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
                            if mode=="find": 
                                display_name = fp.name if scope != "current_file" else tu.get('id')
                                self.res_tree.insert("", "end", values=(display_name, orig[:50]), tags=(str(fp), tu.get('id')))
                            if mode=="replace" and new!=orig: tn.text=new; tn.set('state', 'translated'); dirty=True
                
                if dirty and mode=="replace":
                    mods+=1
                    if self.var_back.get(): shutil.copy2(fp, str(fp)+".bak")
                    t.write(str(fp), encoding="UTF-8", xml_declaration=True, pretty_print=True)
            except: pass
            self.prog['value'] = i+1; self.update_idletasks()
        
        if mode=="replace": 
            messagebox.showinfo("Done", f"Replaced {hits} in {mods} files.")
            if self.editor.current_file: self.editor.load_file(self.editor.current_file)

    def jump_to_result(self, event):
        sel = self.res_tree.selection()
        if not sel: return
        item = self.res_tree.item(sel[0]); tags = self.res_tree.item(sel[0], 'tags')
        f_path = tags[0]; t_id = tags[1]
        
        if str(self.editor.current_file) != str(f_path): 
            # FIXED: Use safe switching method to check for unsaved changes
            success = self.editor.request_file_switch(f_path)
            if not success: return
            
        for c in self.editor.tree.get_children():
            if str(self.editor.tree.item(c, 'values')[0]) == str(t_id): 
                self.editor.tree.selection_set(c)
                self.editor.tree.see(c)
                self.editor.on_row_select(None)
                break
