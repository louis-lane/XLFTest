import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk as tk_ttk 
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language, log_errors, CONFIG, center_window
import shutil
import re
import threading
import os
import pandas as pd

# --- IMPORTS FROM SPLIT MODULES ---
from modules.editor.popups import ToolTip, FindReplacePane, AddTermDialog
from modules.editor.logic import EditorLogic

class EditorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.logic = EditorLogic()
        
        self.current_folder = None
        self.current_file = None
        self.file_map = {} 
        self.xml_tree = None 
        self.data_store = []
        self.current_edit_id = None
        
        self.sidebar_visible = True
        self.glossary_visible = True
        self.find_visible = False
        self.admin_mode_active = False 
        
        self.setup_ui()
        self.setup_hotkeys()
        self.logic.load_glossary()

    def setup_ui(self):
        # 1. GLOBAL TOOLBAR
        self.toolbar = ttk.Frame(self, padding=(5, 5))
        self.toolbar.pack(side=TOP, fill=X)

        self.btn_toggle_sidebar = ttk.Button(self.toolbar, text="🗖", command=self.toggle_sidebar, bootstyle="secondary-outline", width=3)
        self.btn_toggle_sidebar.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.btn_toggle_sidebar, "Toggle File Sidebar")
        
        ttk.Label(self.toolbar, text="Tag Syntax:").pack(side=LEFT, padx=(0, 5))
        self.tag_syntax_var = tk.StringVar(value="Standard XML <>")
        self.combo_syntax = ttk.Combobox(self.toolbar, textvariable=self.tag_syntax_var, values=("Standard XML <>", "Gomo []"), state="readonly", width=15)
        self.combo_syntax.pack(side=LEFT, padx=(0, 15))
        self.combo_syntax.bind("<<ComboboxSelected>>", self.on_syntax_change)
        ToolTip(self.combo_syntax, "Select tag format")

        btn_copy = ttk.Button(self.toolbar, text="➜ Source", command=self.copy_source_to_target, bootstyle="link")
        btn_copy.pack(side=LEFT)
        btn_clear = ttk.Button(self.toolbar, text="✖ Clear", command=self.clear_target, bootstyle="link")
        btn_clear.pack(side=LEFT)
        
        ttk.Separator(self.toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)

        # Filter Area
        filter_frame = ttk.Frame(self.toolbar)
        filter_frame.pack(side=LEFT, padx=20)
        ttk.Label(filter_frame, text="Search:").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=LEFT, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.apply_filter)
        
        self.filter_var = tk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var, values=("All", "New", "Needs Review", "Translated", "Final"), state="readonly", width=12)
        self.filter_combo.pack(side=LEFT)
        self.filter_combo.bind("<<ComboboxSelected>>", self.apply_filter)

        self.btn_toggle_find = ttk.Button(self.toolbar, text="🔍 Find", command=self.toggle_find_replace, bootstyle="warning-outline")
        self.btn_toggle_find.pack(side=RIGHT, padx=5)
        self.btn_toggle_glossary = ttk.Button(self.toolbar, text="📖 Glossary", command=self.toggle_glossary, bootstyle="info-outline")
        self.btn_toggle_glossary.pack(side=RIGHT, padx=5)

        # 2. PANED WINDOWS
        self.main_split = tk_ttk.PanedWindow(self, orient=HORIZONTAL)
        self.main_split.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # Left Sidebar
        self.sidebar_frame = ttk.Frame(self.main_split)
        self.main_split.add(self.sidebar_frame, weight=1)
        ttk.Button(self.sidebar_frame, text="📂 Open Project", command=self.load_project_folder, bootstyle="info-outline").pack(fill=X, pady=(0, 5))
        self.file_tree = ttk.Treeview(self.sidebar_frame, show="tree headings", selectmode="browse")
        self.file_tree.heading("#0", text="Project Files")
        self.file_tree.pack(fill=BOTH, expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)

        # Center Content
        self.content_area = ttk.Frame(self.main_split)
        self.main_split.add(self.content_area, weight=4)
        
        self.editor_split = tk_ttk.PanedWindow(self.content_area, orient=VERTICAL)
        self.editor_split.pack(fill=BOTH, expand=True)
        
        # Grid
        self.grid_frame = ttk.Frame(self.editor_split)
        self.editor_split.add(self.grid_frame, weight=3)
        cols = ("id", "source", "target", "status")
        self.tree = ttk.Treeview(self.grid_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("id", text="ID"); self.tree.column("id", width=50)
        self.tree.heading("source", text="Original Source"); self.tree.column("source", width=300)
        self.tree.heading("target", text="Translation Target"); self.tree.column("target", width=300)
        self.tree.heading("status", text="St"); self.tree.column("status", width=40, anchor="center")
        self.tree.tag_configure('new', foreground='#ff4d4d')
        self.tree.tag_configure('needs_review', foreground='#ffad33')
        self.tree.tag_configure('translated', foreground='#33cc33')
        self.tree.tag_configure('final', foreground='#3399ff')
        
        grid_scroll = ttk.Scrollbar(self.grid_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=grid_scroll.set)
        grid_scroll.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        
        self.create_context_menus()
        self.tree.bind("<Button-3>", self.show_grid_menu)

        # Edit Panel
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=2)
        
        h = ttk.Frame(self.edit_panel); h.pack(side=TOP, fill=X, pady=(0, 10))
        ttk.Label(h, text="Status:").pack(side=LEFT)
        self.edit_status_var = tk.StringVar()
        self.status_dropdown = ttk.Combobox(h, textvariable=self.edit_status_var, values=("new", "needs-review", "translated", "final"), state="readonly", width=12)
        self.status_dropdown.pack(side=LEFT, padx=5)
        
        ttk.Button(h, text="B", width=2, command=lambda: self.format_text("b"), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        ttk.Button(h, text="I", width=2, command=lambda: self.format_text("i"), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        ttk.Button(h, text="U", width=2, command=lambda: self.format_text("u"), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        
        self.mb_tags = ttk.Menubutton(h, text="</>", bootstyle="secondary-outline")
        self.mb_tags.pack(side=LEFT, padx=(5, 1))
        self.menu_tags = tk.Menu(self.mb_tags, tearoff=0)
        self.mb_tags['menu'] = self.menu_tags
        ToolTip(self.mb_tags, "Insert Source Tags")

        ttk.Separator(h, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)
        ttk.Button(h, text="↶", width=2, command=lambda: self.txt_target.edit_undo(), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        ttk.Button(h, text="↷", width=2, command=lambda: self.txt_target.edit_redo(), bootstyle="secondary-outline").pack(side=LEFT, padx=1)

        f_right = ttk.Frame(h); f_right.pack(side=RIGHT)
        ttk.Label(f_right, text="[Ctrl+Enter to Save]", font=("Helvetica", 8), foreground="gray").pack(side=LEFT, padx=10)
        ttk.Button(f_right, text="<", width=3, command=lambda: self.navigate_grid(-1), bootstyle="secondary-outline").pack(side=LEFT)
        ttk.Button(f_right, text=">", width=3, command=lambda: self.navigate_grid(1), bootstyle="secondary-outline").pack(side=LEFT, padx=2)
        ttk.Button(f_right, text="Save & Next", command=self.save_and_next, bootstyle="success").pack(side=LEFT, padx=5)

        ttk.Label(self.edit_panel, text="Source:", bootstyle="inverse-secondary").pack(anchor=W)
        self.txt_source = tk.Text(self.edit_panel, height=4, state=DISABLED, wrap="word")
        self.txt_source.pack(fill=BOTH, expand=True, pady=(0, 5))
        self.txt_source.bind("<Button-3>", self.show_source_menu)
        
        ttk.Label(self.edit_panel, text="Target:", bootstyle="inverse-secondary").pack(anchor=W)
        self.txt_target = tk.Text(self.edit_panel, height=4, undo=True, maxundo=50, wrap="word")
        self.txt_target.pack(fill=BOTH, expand=True)
        self.txt_target.bind("<Button-3>", self.show_target_menu)
        self.txt_target.bind("<ButtonRelease-1>", self.on_target_click)

        # 3. RIGHT SIDEBAR (CONTAINER)
        self.right_sidebar = ttk.Frame(self.main_split)
        self.main_split.add(self.right_sidebar, weight=1)
        
        # Glossary Pane (Initially Visible)
        self.glossary_frame = ttk.Labelframe(self.right_sidebar, text="Glossary", padding=5, bootstyle="info")
        self.glossary_frame.pack(side=TOP, fill=BOTH, expand=True, padx=5, pady=5)
        
        self.gloss_tree = ttk.Treeview(self.glossary_frame, columns=("term", "trans"), show="headings")
        self.gloss_tree.heading("term", text="Term"); self.gloss_tree.heading("trans", text="Trans")
        self.gloss_tree.pack(fill=BOTH, expand=True)
        self.gloss_tree.bind("<Double-1>", self.insert_glossary_term)
        
        self.gloss_ctrl = ttk.Frame(self.glossary_frame); self.gloss_ctrl.pack(side=BOTTOM, fill=X)
        # THIS was the line causing the error because the function it pointed to didn't exist
        self.btn_add_term = ttk.Button(self.gloss_ctrl, text="+ Add", command=self.open_add_term_dialog, bootstyle="info-outline-sm")
        self.btn_add_term.pack(side=RIGHT)

        # Find Pane (Initially Hidden)
        self.find_pane = FindReplacePane(self.right_sidebar, self)

    # --- LAYOUT LOGIC (New Functions Added) ---
    def toggle_sidebar(self):
        """Toggles the Left File Explorer sidebar."""
        if self.sidebar_visible:
            self.main_split.forget(self.sidebar_frame)
            self.btn_toggle_sidebar.configure(bootstyle="secondary") 
        else:
            self.main_split.insert(0, self.sidebar_frame, weight=1)
            self.btn_toggle_sidebar.configure(bootstyle="secondary-outline")
        self.sidebar_visible = not self.sidebar_visible

    def update_sidebar_visibility(self):
        if not self.glossary_visible and not self.find_visible:
            self.main_split.forget(self.right_sidebar)
        else:
            if self.main_split.index(self.right_sidebar) < 0: 
                self.main_split.add(self.right_sidebar, weight=1)
    
    def toggle_glossary(self):
        if self.glossary_visible:
            self.glossary_frame.pack_forget(); self.btn_toggle_glossary.configure(bootstyle="info")
        else:
            self.glossary_frame.pack(side=TOP, fill=BOTH, expand=True, padx=5, pady=5)
            self.btn_toggle_glossary.configure(bootstyle="info-outline")
        self.glossary_visible = not self.glossary_visible
        self.update_sidebar_visibility()

    def toggle_find_replace(self):
        if self.find_visible:
            self.find_pane.pack_forget(); self.btn_toggle_find.configure(bootstyle="warning-outline")
        else:
            self.find_pane.pack(side=BOTTOM, fill=X, padx=5, pady=5)
            self.btn_toggle_find.configure(bootstyle="warning")
        self.find_visible = not self.find_visible
        self.update_sidebar_visibility()

    def open_find_replace_dialog(self):
        if not self.find_visible: self.toggle_find_replace()

    # --- POPUP LOGIC (New Function Added) ---
    def open_add_term_dialog(self):
        # Initializes the AddTermDialog with self as parent and the logic engine
        AddTermDialog(self, self.logic)
        
        # After dialog closes, refresh glossary if a segment is selected
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.refresh_glossary_view(rec['source'])

    # --- TAG LOGIC ---
    def on_syntax_change(self, event):
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.update_tag_menu(rec['source'])

    def update_tag_menu(self, source_text):
        self.menu_tags.delete(0, END)
        syntax = self.tag_syntax_var.get()
        tags = self.logic.extract_tags(source_text, syntax)
        if not tags: self.menu_tags.add_command(label="(No tags found)", state=DISABLED); return
        for tag in tags:
            self.menu_tags.add_command(label=tag, command=lambda t=tag: self.insert_smart_tag(t))

    def insert_smart_tag(self, opener):
        closer = ""
        syntax = self.tag_syntax_var.get()
        if syntax == "Gomo []":
            content = opener.strip("[]"); tag_name = content.split(" ")[0]; closer = f"[/{tag_name}]"
        else:
            content = opener.strip("<>"); tag_name = content.split(" ")[0]; closer = f"</{tag_name}>"
        try:
            if not self.txt_target.tag_ranges("sel"):
                self.txt_target.insert(tk.INSERT, f"{opener}{closer}")
                self.txt_target.mark_set(tk.INSERT, f"insert - {len(closer)}c")
            else:
                sel_first = self.txt_target.index("sel.first"); sel_last = self.txt_target.index("sel.last")
                text = self.txt_target.get(sel_first, sel_last)
                if text.startswith(opener) and text.endswith(closer):
                    inner = text[len(opener):-len(closer)]
                    self.txt_target.delete(sel_first, sel_last); self.txt_target.insert(sel_first, inner)
                    self.txt_target.tag_add("sel", sel_first, f"{sel_first} + {len(inner)}c")
                else:
                    self.txt_target.delete(sel_first, sel_last); self.txt_target.insert(sel_first, f"{opener}{text}{closer}")
        except: pass
        self.txt_target.focus_set()

    def format_text(self, tag_type):
        syntax = self.tag_syntax_var.get()
        opener = f"[{tag_type}]" if syntax == "Gomo []" else f"<{tag_type}>"
        self.insert_smart_tag(opener)

    def on_target_click(self, event):
        try:
            index = self.txt_target.index(f"@{event.x},{event.y}")
            line_start = f"{index.split('.')[0]}.0"
            line_text = self.txt_target.get(line_start, f"{line_start} lineend")
            char_offset = int(index.split('.')[1])
            mode = self.tag_syntax_var.get()
            pattern = r"\[/?[a-zA-Z0-9_\-]+[^\]]*\]" if mode == "Gomo []" else r"</?[a-zA-Z0-9]+[^>]*>"
            open_char = '[' if mode == "Gomo []" else '<'
            close_char = ']' if mode == "Gomo []" else '>'
            tags = re.finditer(pattern, line_text)
            clicked_tag = None; tag_start = None; tag_end = None
            for match in tags:
                s, e = match.span()
                if s <= char_offset <= e: clicked_tag = match.group(); tag_start = s; tag_end = e; break
            if clicked_tag:
                is_closing = clicked_tag.startswith(f"{open_char}/")
                clean_content = re.sub(r"[\[\]<>/]", "", clicked_tag).split(" ")[0]
                start_sel = None; end_sel = None
                if not is_closing:
                    rest_of_line = line_text[tag_end:]
                    closer = f"{open_char}/{clean_content}{close_char}"
                    close_idx = rest_of_line.find(closer)
                    if close_idx != -1: start_sel = f"{index.split('.')[0]}.{tag_start}"; end_sel = f"{index.split('.')[0]}.{tag_end + close_idx + len(closer)}"
                else:
                    prev_line = line_text[:tag_start]
                    opener_base = f"{open_char}{clean_content}"
                    open_idx = prev_line.rfind(opener_base)
                    if open_idx != -1: start_sel = f"{index.split('.')[0]}.{open_idx}"; end_sel = f"{index.split('.')[0]}.{tag_end}"
                if start_sel and end_sel: self.txt_target.tag_remove("sel", "1.0", END); self.txt_target.tag_add("sel", start_sel, end_sel)
        except: pass

    # --- STANDARD METHODS ---
    def load_project_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.current_folder = Path(folder)
        for i in self.file_tree.get_children(): self.file_tree.delete(i)
        self.file_map = {}
        xliffs = list(self.current_folder.glob("*.xliff"))
        for f in xliffs:
            lang = get_target_language(f)
            if lang not in self.file_map: self.file_map[lang] = []
            self.file_map[lang].append(f)
        for lang, files in self.file_map.items():
            node = self.file_tree.insert("", "end", text=lang, open=True)
            for f in files: self.file_tree.insert(node, "end", text=f.name, values=(str(f),))

    def on_file_select(self, event):
        sel = self.file_tree.selection()
        if not sel: return
        item = self.file_tree.item(sel[0])
        if not item['values']: return 
        self.load_file(item['values'][0])

    def load_file(self, path):
        self.current_file = path
        try:
            self.xml_tree, self.data_store = self.logic.load_xliff(path)
            self.apply_filter()
        except Exception as e: messagebox.showerror("Error", str(e))

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
            self.refresh_glossary_view(rec['source'])
            self.update_tag_menu(rec['source'])

    def refresh_glossary_view(self, source_text):
        for i in self.gloss_tree.get_children(): self.gloss_tree.delete(i)
        matches = self.logic.find_glossary_matches(source_text, self.current_file)
        for term, trans in matches: self.gloss_tree.insert("", "end", values=(term, trans))

    def insert_glossary_term(self, event):
        sel = self.gloss_tree.selection()
        if not sel: return
        translation = self.gloss_tree.item(sel[0], 'values')[1]
        self.txt_target.focus_set()
        try: self.txt_target.delete("sel.first", "sel.last")
        except: pass
        self.txt_target.insert(tk.INSERT, translation)

    def save_and_next(self):
        # NOTE: logic.save_segment or similar needs to be called here.
        # Assuming you will implement save_segment or it's handled in logic.py
        pass 

    def navigate_grid(self, direction):
        sel = self.tree.selection(); items = self.tree.get_children()
        if not items: return
        new_idx = 0
        if sel: new_idx = max(0, min(len(items)-1, items.index(sel[0]) + direction))
        self.tree.selection_set(items[new_idx]); self.tree.see(items[new_idx]); self.on_row_select(None)

    def setup_hotkeys(self):
        self.txt_target.bind("<Control-Return>", lambda e: self.save_and_next())
        self.txt_target.bind("<Control-b>", lambda e: self.format_text("b") or "break")
        self.txt_target.bind("<Control-i>", lambda e: self.format_text("i") or "break")
        self.txt_target.bind("<Control-u>", lambda e: self.format_text("u") or "break")
        self.bind_all("<Control-Q>", self.toggle_admin_mode)
        
    def toggle_admin_mode(self, event=None):
        self.admin_mode_active = not self.admin_mode_active
        # Add visual feedback or logic for admin mode here if needed
        print(f"Admin mode: {self.admin_mode_active}")

    def create_context_menus(self):
        self.menu_grid = tk.Menu(self, tearoff=0)
        self.menu_grid.add_command(label="Copy Source", command=self.copy_source_to_target)
        self.menu_source = tk.Menu(self, tearoff=0); self.menu_source.add_command(label="Copy", command=lambda: self.text_copy(self.txt_source))
        self.menu_target = tk.Menu(self, tearoff=0); self.menu_target.add_command(label="Copy", command=lambda: self.text_copy(self.txt_target))
        self.menu_target.add_command(label="Paste", command=lambda: self.text_paste(self.txt_target))

    def show_grid_menu(self, event):
        if self.tree.identify_row(event.y): self.menu_grid.post(event.x_root, event.y_root)
    def show_source_menu(self, event): self.menu_source.post(event.x_root, event.y_root)
    def show_target_menu(self, event): self.menu_target.post(event.x_root, event.y_root)
    
    def copy_source_to_target(self):
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", rec['source'])
    def clear_target(self): self.txt_target.delete("1.0", END)
    def text_copy(self, w): 
        try: self.clipboard_clear(); self.clipboard_append(w.get("sel.first", "sel.last"))
        except: pass
    def text_paste(self, w):
        try: w.insert(tk.INSERT, self.clipboard_get())
        except: pass
    
    # --- RE-ADDED MISSING FILTER FUNCTION ---
    def apply_filter(self, event=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        status_filter = self.filter_var.get().lower(); search = self.search_var.get().lower()
        status_map = {'new': '🔴', 'needs-review': '🟠', 'translated': '🟢', 'final': '☑️'}
        for rec in self.data_store:
            rec_status = str(rec['status']).lower().replace(" ", "").replace("-", "")
            filter_clean = status_filter.replace(" ", "").replace("-", "")
            if status_filter != "all" and rec_status != filter_clean: continue
            if search and (search not in str(rec['source']).lower() and search not in str(rec['target']).lower() and search not in str(rec['id']).lower()): continue
            tag = str(rec['status']).lower().replace(" ", "_").replace("-", "_")
            icon = status_map.get(str(rec['status']).lower(), '❓')
            self.tree.insert("", "end", values=(rec['id'], rec['source'].replace('\n', ' '), rec['target'].replace('\n', ' '), icon), tags=(tag,))
