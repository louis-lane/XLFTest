import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk as tk_ttk 
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language, log_errors, CONFIG
import shutil
import re
import threading
import os
import pandas as pd

class EditorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_folder = None
        self.current_file = None
        self.file_map = {} 
        self.glossary_data = [] 
        
        self.sidebar_visible = True
        self.glossary_visible = True
        self.admin_mode_active = False 
        
        # --- MAIN LAYOUT: 3 COLUMNS ---
        self.main_split = tk_ttk.PanedWindow(self, orient=HORIZONTAL)
        self.main_split.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 1. LEFT SIDEBAR
        self.sidebar_frame = ttk.Frame(self.main_split)
        self.main_split.add(self.sidebar_frame, weight=1)
        
        sb_controls = ttk.Frame(self.sidebar_frame)
        sb_controls.pack(fill=X, pady=(0, 5))
        ttk.Button(sb_controls, text="📂 Open Project", command=self.load_project_folder, bootstyle="info-outline").pack(fill=X)

        self.file_tree = ttk.Treeview(self.sidebar_frame, show="tree headings", selectmode="browse")
        self.file_tree.heading("#0", text="Project Files")
        sb_scroll = ttk.Scrollbar(self.sidebar_frame, orient=VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscroll=sb_scroll.set)
        sb_scroll.pack(side=RIGHT, fill=Y)
        self.file_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)

        # 2. CENTER CONTENT
        self.content_area = ttk.Frame(self.main_split)
        self.main_split.add(self.content_area, weight=4)

        # --- CENTER TOP CONTROLS ---
        top_controls = ttk.Frame(self.content_area, padding=(0, 0, 0, 5))
        top_controls.pack(fill=X)

        self.btn_toggle_sidebar = ttk.Button(top_controls, text="🗖 Files", command=self.toggle_sidebar, bootstyle="secondary-outline")
        self.btn_toggle_sidebar.pack(side=LEFT, padx=(0, 10))

        ttk.Label(top_controls, text="Search:").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top_controls, textvariable=self.search_var, width=25)
        self.search_entry.pack(side=LEFT, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.apply_filter)

        ttk.Label(top_controls, text="Filter:").pack(side=LEFT, padx=(5, 5))
        self.filter_var = tk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(top_controls, textvariable=self.filter_var, values=("All", "New", "Needs Review", "Translated", "Final"), state="readonly", width=12)
        self.filter_combo.pack(side=LEFT)
        self.filter_combo.bind("<<ComboboxSelected>>", self.apply_filter)

        self.btn_toggle_glossary = ttk.Button(top_controls, text="📖 Glossary", command=self.toggle_glossary, bootstyle="info-outline")
        self.btn_toggle_glossary.pack(side=RIGHT, padx=(10, 0))
        ttk.Button(top_controls, text="🔍 Find", command=self.open_find_replace_dialog, bootstyle="warning-outline").pack(side=RIGHT)

        # --- CENTER SPLIT ---
        self.editor_split = tk_ttk.PanedWindow(self.content_area, orient=VERTICAL)
        self.editor_split.pack(fill=BOTH, expand=True)
        
        self.grid_frame = ttk.Frame(self.editor_split)
        self.editor_split.add(self.grid_frame, weight=3)
        
        cols = ("id", "status", "source", "target")
        self.tree = ttk.Treeview(self.grid_frame, columns=cols, show="headings", selectmode="extended") 
        self.tree.heading("id", text="ID"); self.tree.column("id", width=50)
        self.tree.heading("status", text="Status"); self.tree.column("status", width=90)
        self.tree.heading("source", text="Original Source"); self.tree.column("source", width=300)
        self.tree.heading("target", text="Translated Target"); self.tree.column("target", width=300)
        
        grid_scroll = ttk.Scrollbar(self.grid_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=grid_scroll.set)
        grid_scroll.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        
        self.create_context_menus()
        self.tree.bind("<Button-3>", self.show_grid_menu)
        self.tree.bind("<Button-2>", self.show_grid_menu) 

        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=2)
        
        controls_bot = ttk.Frame(self.edit_panel)
        controls_bot.pack(side=BOTTOM, fill=X, pady=5)

        ttk.Label(controls_bot, text="Status:").pack(side=LEFT, padx=(0, 5))
        self.edit_status_var = tk.StringVar()
        self.status_dropdown = ttk.Combobox(controls_bot, textvariable=self.edit_status_var, values=("new", "needs-review", "translated", "final"), state="readonly", width=15)
        self.status_dropdown.pack(side=LEFT)

        btn_nav_frame = ttk.Frame(controls_bot)
        btn_nav_frame.pack(side=RIGHT)
        ttk.Button(btn_nav_frame, text="<", command=lambda: self.navigate_grid(-1), bootstyle="secondary-outline").pack(side=LEFT, padx=2)
        ttk.Button(btn_nav_frame, text=">", command=lambda: self.navigate_grid(1), bootstyle="secondary-outline").pack(side=LEFT, padx=2)
        ttk.Button(btn_nav_frame, text="Save & Next", command=self.save_and_next, bootstyle="success").pack(side=LEFT, padx=5)
        
        ttk.Label(self.edit_panel, text="Original Source:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        src_frame = ttk.Frame(self.edit_panel)
        src_frame.pack(fill=BOTH, expand=True, pady=(0, 5))
        src_scroll = ttk.Scrollbar(src_frame, orient=VERTICAL)
        self.txt_source = tk.Text(src_frame, height=4, bg="white", fg="black", state=DISABLED, wrap="word", yscrollcommand=src_scroll.set)
        src_scroll.config(command=self.txt_source.yview)
        src_scroll.pack(side=RIGHT, fill=Y)
        self.txt_source.pack(side=LEFT, fill=BOTH, expand=True)
        self.txt_source.bind("<Button-3>", self.show_source_menu)
        
        ttk.Label(self.edit_panel, text="Translation Target:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        tgt_frame = ttk.Frame(self.edit_panel)
        tgt_frame.pack(fill=BOTH, expand=True, pady=(0, 5))
        tgt_scroll = ttk.Scrollbar(tgt_frame, orient=VERTICAL)
        self.txt_target = tk.Text(tgt_frame, height=4, bg="white", fg="black", insertbackground="black", wrap="word", yscrollcommand=tgt_scroll.set)
        tgt_scroll.config(command=self.txt_target.yview)
        tgt_scroll.pack(side=RIGHT, fill=Y)
        self.txt_target.pack(side=LEFT, fill=BOTH, expand=True)
        self.txt_target.bind("<Button-3>", self.show_target_menu)

        # 3. RIGHT SIDEBAR (Glossary)
        self.right_sidebar = ttk.Frame(self.main_split)
        self.main_split.add(self.right_sidebar, weight=1)

        self.glossary_frame = ttk.Labelframe(self.right_sidebar, text="Glossary / Term Base", padding=5, bootstyle="info")
        self.glossary_frame.pack(fill=BOTH, expand=True, padx=(0, 5), pady=5)
        
        cols_gloss = ("term", "trans")
        self.gloss_tree = ttk.Treeview(self.glossary_frame, columns=cols_gloss, show="headings", selectmode="browse")
        self.gloss_tree.heading("term", text="Term"); self.gloss_tree.column("term", width=80)
        self.gloss_tree.heading("trans", text="Translation"); self.gloss_tree.column("trans", width=120)
        
        gloss_scroll = ttk.Scrollbar(self.glossary_frame, orient=VERTICAL, command=self.gloss_tree.yview)
        self.gloss_tree.configure(yscroll=gloss_scroll.set)
        gloss_scroll.pack(side=RIGHT, fill=Y)
        self.gloss_tree.pack(fill=BOTH, expand=True)
        self.gloss_tree.bind("<Double-1>", self.insert_glossary_term)
        
        # GLOSSARY CONTROLS
        self.gloss_ctrl_frame = ttk.Frame(self.glossary_frame)
        self.gloss_ctrl_frame.pack(side=BOTTOM, fill=X, pady=5)
        ttk.Label(self.gloss_ctrl_frame, text="Double-click to insert", font=("Helvetica", 7), foreground="gray").pack(side=LEFT)
        
        # --- ADMIN BUTTON (Hidden by Default) ---
        self.btn_add_term = ttk.Button(self.gloss_ctrl_frame, text="+ Add Term", command=self.open_add_term_dialog, bootstyle="info-outline-sm")

        self.xml_tree = None
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.data_store = []
        self.current_edit_id = None
        self.setup_hotkeys()
        self.load_glossary_data()

    # --- TOGGLE ADMIN MODE ---
    def toggle_admin_mode(self, event=None):
        if self.admin_mode_active:
            self.btn_add_term.pack_forget()
            messagebox.showinfo("Admin Mode", "Admin Mode Deactivated")
        else:
            self.btn_add_term.pack(side=RIGHT)
            messagebox.showinfo("Admin Mode", "Admin Mode Activated\n\n'Add Term' button is now visible.")
        
        self.admin_mode_active = not self.admin_mode_active

    # --- GLOSSARY EDITOR LOGIC ---
    def open_add_term_dialog(self):
        d = ttk.Toplevel(self)
        d.title("Add Glossary Term")
        d.geometry("400x350")
        
        initial_source = ""
        try: initial_source = self.txt_source.get("sel.first", "sel.last")
        except: pass

        ttk.Label(d, text="Source Term:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=(10,0))
        e_src = ttk.Entry(d); e_src.pack(fill=X, padx=10); e_src.insert(0, initial_source)
        
        ttk.Label(d, text="Translation:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=(10,0))
        e_tgt = ttk.Entry(d); e_tgt.pack(fill=X, padx=10)
        
        ttk.Label(d, text="Language Code:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=(10,0))
        
        default_lang = ""
        if self.current_file: default_lang = get_target_language(self.current_file)
        c_lang = ttk.Combobox(d, values=CONFIG.get("protected_languages", []))
        c_lang.pack(fill=X, padx=10); c_lang.set(default_lang)
        
        def save_term():
            s, t, l = e_src.get().strip(), e_tgt.get().strip(), c_lang.get().strip()
            if not s or not t: messagebox.showwarning("Missing Data", "Source and Target are required."); return
            
            for entry in self.glossary_data:
                if entry['source'].lower() == s.lower() and entry['lang'] == l:
                    if not messagebox.askyesno("Duplicate", "Term exists. Add duplicate?"): return
            
            g_path = Path("glossary.xlsx")
            new_row = {"source_text": s, "target_text": t, "language_code": l}
            
            try:
                if g_path.exists():
                    df = pd.read_excel(g_path)
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                else:
                    df = pd.DataFrame([new_row])
                
                df.to_excel(g_path, index=False)
                messagebox.showinfo("Success", "Term added.")
                self.load_glossary_data() 
                if self.current_edit_id:
                    rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
                    if rec: self.check_glossary_matches(rec['source'])
                d.destroy()
            except PermissionError: messagebox.showerror("File Locked", "Close glossary.xlsx first.")
            except Exception as e: messagebox.showerror("Error", f"Failed: {e}")

        ttk.Button(d, text="Save Term", command=save_term, bootstyle="success").pack(pady=20, fill=X, padx=10)

    # --- UI TOGGLE LOGIC ---
    def toggle_sidebar(self):
        if self.sidebar_visible: self.main_split.forget(self.sidebar_frame); self.btn_toggle_sidebar.configure(bootstyle="secondary")
        else: self.main_split.insert(0, self.sidebar_frame, weight=1); self.btn_toggle_sidebar.configure(bootstyle="secondary-outline")
        self.sidebar_visible = not self.sidebar_visible

    def toggle_glossary(self):
        if self.glossary_visible: self.main_split.forget(self.right_sidebar); self.btn_toggle_glossary.configure(bootstyle="info") 
        else: self.main_split.add(self.right_sidebar, weight=1); self.btn_toggle_glossary.configure(bootstyle="info-outline")
        self.glossary_visible = not self.glossary_visible

    # --- GLOSSARY LOGIC ---
    def load_glossary_data(self):
        g_path = Path("glossary.xlsx")
        if not g_path.exists(): return
        try:
            df = pd.read_excel(g_path)
            self.glossary_data = [] 
            for _, row in df.iterrows():
                if pd.notna(row.get('source_text')) and pd.notna(row.get('target_text')):
                    self.glossary_data.append({
                        "source": str(row['source_text']).strip(),
                        "target": str(row['target_text']).strip(),
                        "lang": str(row.get('language_code', '')).strip()
                    })
        except Exception as e: print(f"Glossary load error: {e}")

    def check_glossary_matches(self, source_text):
        for i in self.gloss_tree.get_children(): self.gloss_tree.delete(i)
        if not self.glossary_data or not source_text: return
        current_lang = "unknown"
        if self.current_file: current_lang = get_target_language(self.current_file)
        source_lower = source_text.lower()
        for entry in self.glossary_data:
            if entry['lang'] and current_lang != "unknown":
                if not current_lang.lower().startswith(entry['lang'].lower()): continue
            term = entry['source']
            if term.lower() in source_lower: self.gloss_tree.insert("", "end", values=(term, entry['target']))

    def insert_glossary_term(self, event):
        sel = self.gloss_tree.selection()
        if not sel: return
        val = self.gloss_tree.item(sel[0], 'values')
        self.txt_target.insert(tk.INSERT, val[1]); self.txt_target.focus_set()

    # --- HOTKEYS ---
    def setup_hotkeys(self):
        self.txt_target.bind("<Control-Return>", lambda e: self.save_and_next())
        self.txt_target.bind("<Control-Up>", lambda e: self.navigate_grid(-1))
        self.txt_target.bind("<Control-Down>", lambda e: self.navigate_grid(1))
        self.txt_target.bind("<Alt-s>", lambda e: self.replace_edit_with_source())
        self.txt_target.bind("<Alt-c>", lambda e: self.copy_source_to_clipboard())
        self.tree.bind("<Control-Up>", lambda e: self.navigate_grid(-1))
        self.tree.bind("<Control-Down>", lambda e: self.navigate_grid(1))
        
        # --- NEW ADMIN TOGGLE KEY (Ctrl+Shift+Q) ---
        self.bind_all("<Control-Q>", self.toggle_admin_mode) 

    # --- NAVIGATION ---
    def navigate_grid(self, direction):
        current_selection = self.tree.selection()
        all_items = self.tree.get_children()
        if not all_items: return
        if not current_selection: new_index = 0
        else:
            try: new_index = all_items.index(current_selection[0]) + direction
            except ValueError: new_index = 0
        if 0 <= new_index < len(all_items):
            new_item = all_items[new_index]
            self.tree.selection_set(new_item); self.tree.see(new_item)
            self.on_row_select(None); self.txt_target.focus_set()
            return "break"

    def save_and_next(self): self.save_segment(); self.navigate_grid(1); return "break"
    def copy_source_to_clipboard(self): src = self.txt_source.get("1.0", "end-1c"); self.clipboard_clear(); self.clipboard_append(src); return "break"

    # --- FILE LOADING ---
    def load_project_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.current_folder = Path(folder)
        for i in self.file_tree.get_children(): self.file_tree.delete(i)
        self.file_map = {}
        xliffs = list(self.current_folder.glob("*.xliff"))
        if not xliffs: messagebox.showwarning("Empty", "No .xliff files found."); return
        for f in xliffs:
            lang = get_target_language(f)
            if lang not in self.file_map: self.file_map[lang] = []
            self.file_map[lang].append(f)
        for lang, files in self.file_map.items():
            lang_node = self.file_tree.insert("", "end", text=lang, open=True)
            for f in files: self.file_tree.insert(lang_node, "end", text=f.name, values=(str(f),))

    def on_file_select(self, event):
        sel = self.file_tree.selection()
        if not sel: return
        item = self.file_tree.item(sel[0])
        if not item['values']: return 
        self.load_file(item['values'][0])

    def load_file(self, path):
        self.current_file = path
        try:
            self.xml_tree = etree.parse(path)
            self.data_store = []
            for i in self.tree.get_children(): self.tree.delete(i)
            for tu in self.xml_tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                uid = tu.get('id')
                src = (tu.find('xliff:source', namespaces=self.namespaces).text or "") if tu.find('xliff:source', namespaces=self.namespaces) is not None else ""
                tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
                tgt = (tgt_node.text or "") if tgt_node is not None else ""
                status = tgt_node.get('state', 'new') if tgt_node is not None else 'new'
                self.data_store.append({'id': uid, 'source': src, 'target': tgt, 'status': status, 'node': tu})
            self.apply_filter()
        except Exception as e: messagebox.showerror("Error", f"Could not load file: {e}")

    def apply_filter(self, event=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        status_filter = self.filter_var.get().lower(); search = self.search_var.get().lower()
        for rec in self.data_store:
            if status_filter != "all" and str(rec['status']).lower().replace(" ", "") != status_filter.replace(" ", ""): continue
            if search and (search not in str(rec['source']).lower() and search not in str(rec['target']).lower() and search not in str(rec['id']).lower()): continue
            tag = str(rec['status']).lower().replace(" ", "_")
            self.tree.insert("", "end", values=(rec['id'], rec['status'], rec['source'].replace('\n', ' '), rec['target'].replace('\n', ' ')), tags=(tag,))
        self.tree.tag_configure('new', foreground='#ff4d4d'); self.tree.tag_configure('needs_review', foreground='#ffad33')
        self.tree.tag_configure('translated', foreground='#33cc33'); self.tree.tag_configure('final', foreground='#3399ff')

    def on_row_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        uid = self.tree.item(sel[0])['values'][0]
        rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
        if rec:
            self.current_edit_id = uid
            self.txt_source.config(state=NORMAL); self.txt_source.delete("1.0", END); self.txt_source.insert("1.0", rec['source']); self.txt_source.config(state=DISABLED)
            self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", rec['target'])
            self.edit_status_var.set(rec['status'])
            self.check_glossary_matches(rec['source'])

    def save_segment(self):
        if not self.current_edit_id: return
        new_txt = self.txt_target.get("1.0", "end-1c"); new_status = self.edit_status_var.get()
        rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
        if rec: self._update_single_record(rec, new_txt, new_status); self._save_and_refresh()

    def _update_single_record(self, rec, text, status):
        rec['target'] = text; rec['status'] = status
        tgt_node = rec['node'].find('xliff:target', namespaces=self.namespaces)
        if tgt_node is None: tgt_node = etree.SubElement(rec['node'], f"{{{self.namespaces['xliff']}}}target")
        tgt_node.text = text; tgt_node.set('state', status)

    def _save_and_refresh(self):
        try:
            self.xml_tree.write(self.current_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)
            sel = self.tree.selection(); self.apply_filter()
            valid = [i for i in sel if self.tree.exists(i)]
            if valid: self.tree.selection_set(valid); self.on_row_select(None)
        except Exception as e: messagebox.showerror("Error", f"Failed to save: {e}")

    def create_context_menus(self):
        self.menu_grid = tk.Menu(self, tearoff=0)
        for s in ["new", "needs-review", "translated", "final"]: self.menu_grid.add_command(label=f"Mark as {s.title()}", command=lambda x=s: self.bulk_set_status(x))
        self.menu_grid.add_separator(); self.menu_grid.add_command(label="Copy Source -> Target", command=self.copy_source_to_target)
        self.menu_source_txt = tk.Menu(self, tearoff=0); self.menu_source_txt.add_command(label="Copy", command=lambda: self.text_copy(self.txt_source))
        self.menu_target_txt = tk.Menu(self, tearoff=0); self.menu_target_txt.add_command(label="Cut", command=lambda: self.text_cut(self.txt_target))
        self.menu_target_txt.add_command(label="Copy", command=lambda: self.text_copy(self.txt_target)); self.menu_target_txt.add_command(label="Paste", command=lambda: self.text_paste(self.txt_target))
        self.menu_target_txt.add_separator(); self.menu_target_txt.add_command(label="Replace with Source (Alt+S)", command=self.replace_edit_with_source)

    def show_grid_menu(self, event):
        if self.tree.identify_row(event.y) not in self.tree.selection(): self.tree.selection_set(self.tree.identify_row(event.y)); self.on_row_select(None)
        if self.tree.selection(): self.menu_grid.post(event.x_root, event.y_root)
    def show_source_menu(self, event): self.menu_source_txt.post(event.x_root, event.y_root)
    def show_target_menu(self, event): self.menu_target_txt.post(event.x_root, event.y_root)

    def text_copy(self, w): 
        try: self.clipboard_clear(); self.clipboard_append(w.get("sel.first", "sel.last"))
        except: pass
    def text_cut(self, w): 
        try: self.text_copy(w); w.delete("sel.first", "sel.last")
        except: pass
    def text_paste(self, w): 
        try: w.insert(tk.INSERT, self.clipboard_get())
        except: pass
    def replace_edit_with_source(self): self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", self.txt_source.get("1.0", "end-1c")); return "break"
    def copy_source_to_target(self):
        for i in self.tree.selection():
            uid = self.tree.item(i, 'values')[0]; rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
            if rec: self._update_single_record(rec, rec['source'], "translated")
        self._save_and_refresh()
    def bulk_set_status(self, st):
        for i in self.tree.selection():
            uid = self.tree.item(i, 'values')[0]; rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
            if rec: self._update_single_record(rec, rec['target'], st)
        self._save_and_refresh()

    def open_find_replace_dialog(self):
        if not self.current_folder: messagebox.showwarning("Warning", "Open project first."); return
        d = ttk.Toplevel(self); d.title("Find & Replace"); d.geometry("700x800")
        f1 = ttk.Frame(d, padding=10); f1.pack(fill=X)
        ttk.Label(f1, text="Find:").pack(anchor=W); e_find = ttk.Entry(f1); e_find.pack(fill=X)
        ttk.Label(f1, text="Replace:").pack(anchor=W); e_repl = ttk.Entry(f1); e_repl.pack(fill=X)
        f2 = ttk.Frame(d, padding=10); f2.pack(fill=X)
        var_case = tk.BooleanVar(); ttk.Checkbutton(f2, text="Match Case", variable=var_case).pack(anchor=W)
        var_regex = tk.BooleanVar(); ttk.Checkbutton(f2, text="Regex", variable=var_regex).pack(anchor=W)
        var_back = tk.BooleanVar(value=True); ttk.Checkbutton(f2, text="Backup", variable=var_back).pack(anchor=W)
        var_scope = tk.StringVar(value="current_file"); ttk.Radiobutton(f2, text="Current File", variable=var_scope, value="current_file").pack(anchor=W); ttk.Radiobutton(f2, text="All Files", variable=var_scope, value="all_files").pack(anchor=W)
        prog = ttk.Progressbar(d, mode='determinate'); prog.pack(fill=X, padx=10, pady=10)
        res_tree = ttk.Treeview(d, columns=("file", "id", "txt"), show="headings"); res_tree.pack(fill=BOTH, expand=True, padx=10)
        res_tree.heading("file", text="File"); res_tree.heading("id", text="ID"); res_tree.heading("txt", text="Text")
        def jump(event):
            sel = res_tree.selection()
            if not sel: return
            item = res_tree.item(sel[0]); f = item['tags'][0]; tid = item['values'][1]
            if str(self.current_file) != str(f): self.load_file(f)
            self.tree.selection_remove(self.tree.selection())
            for c in self.tree.get_children():
                if str(self.tree.item(c, 'values')[0]) == str(tid): self.tree.selection_set(c); self.tree.see(c); self.on_row_select(None); break
        res_tree.bind("<Double-1>", jump)
        def run(mode):
            find = e_find.get(); repl = e_repl.get()
            if mode != "rollback" and not find: return
            files = [Path(self.current_file)] if var_scope.get() == "current_file" else [f for l in self.file_map.values() for f in l]
            pat = None
            if mode != "rollback" and var_regex.get():
                try: pat = re.compile(find, 0 if var_case.get() else re.I)
                except: messagebox.showerror("Error", "Bad Regex"); return
            prog['maximum'] = len(files); hits = 0; mods = 0
            for i, fp in enumerate(files):
                try:
                    t = etree.parse(str(fp)); dirty = False
                    for tu in t.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                        tn = tu.find('xliff:target', namespaces=self.namespaces)
                        if tn is not None and tn.text:
                            orig = tn.text; new = orig; found = False
                            if var_regex.get(): 
                                if pat.search(orig): found=True; new=pat.sub(repl, orig) if mode=="replace" else orig
                            else:
                                if var_case.get(): found=(find in orig); new=orig.replace(find, repl) if found and mode=="replace" else orig
                                else: found=(find.lower() in orig.lower()); new=re.compile(re.escape(find), re.I).sub(repl, orig) if found and mode=="replace" else orig
                            if found:
                                hits+=1
                                if mode=="find": res_tree.insert("", "end", values=(fp.name, tu.get('id'), orig[:50]), tags=(str(fp),))
                                if mode=="replace" and new!=orig: tn.text=new; tn.set('state', 'translated'); dirty=True
                    if dirty and mode=="replace":
                        mods+=1; 
                        if var_back.get(): shutil.copy2(fp, str(fp)+".bak")
                        t.write(str(fp), encoding="UTF-8", xml_declaration=True, pretty_print=True)
                except: pass
                prog['value'] = i+1; d.update_idletasks()
            if mode=="replace": messagebox.showinfo("Done", f"Replaced {hits} in {mods} files."); 
            if self.current_file: self.load_file(self.current_file)
        ttk.Button(d, text="Find", command=lambda: threading.Thread(target=lambda: run("find")).start()).pack(side=LEFT, padx=10)
        ttk.Button(d, text="Replace All", command=lambda: threading.Thread(target=lambda: run("replace")).start()).pack(side=LEFT, padx=10)
