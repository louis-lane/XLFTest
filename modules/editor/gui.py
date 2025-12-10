import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk as tk_ttk 
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from utils.core import get_target_language, log_errors, CONFIG
from utils.gui_utils import center_window
import shutil
import re
import threading
import os
import pandas as pd

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
        
        # State Flags
        self.sidebar_visible = True
        self.glossary_visible = True
        self.find_visible = False
        self.admin_mode_active = False
        self.segment_dirty = False  # Track if text has been modified
        
        self.setup_ui()
        self.setup_hotkeys()
        self.logic.load_glossary()

        # Apply initial layout
        self.update_sidebar_visibility()

    def setup_ui(self):
        # 1. GLOBAL TOOLBAR
        self.toolbar = ttk.Frame(self, padding=(5, 5))
        self.toolbar.pack(side=TOP, fill=X)

        # File Sidebar Toggle
        self.btn_toggle_sidebar = ttk.Button(self.toolbar, text="🗖", command=self.toggle_sidebar, bootstyle="secondary-outline", width=3)
        self.btn_toggle_sidebar.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.btn_toggle_sidebar, "Toggle File Sidebar")
        
        # Save Button (Manual)
        self.btn_save_file = ttk.Button(self.toolbar, text="💾 Save File", command=lambda: self.save_file(silent=False), bootstyle="success")
        self.btn_save_file.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.btn_save_file, "Save changes to file")

        # Tag Syntax
        ttk.Label(self.toolbar, text="Tag Syntax:").pack(side=LEFT, padx=(0, 5))
        self.tag_syntax_var = tk.StringVar(value="Standard XML <>")
        self.combo_syntax = ttk.Combobox(self.toolbar, textvariable=self.tag_syntax_var, values=("Standard XML <>", "Gomo []"), state="readonly", width=15)
        self.combo_syntax.pack(side=LEFT, padx=(0, 15))
        self.combo_syntax.bind("<<ComboboxSelected>>", self.on_syntax_change)
        ToolTip(self.combo_syntax, "Select tag format")

        # Copy/Clear Buttons
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

        # Right Sidebar Toggles
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
        
        # Save Button: Commits segment AND writes to disk
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
        # Track unsaved changes
        self.txt_target.bind("<KeyRelease>", self.on_text_modified)

        # 3. RIGHT SIDEBAR (CONTAINER)
        self.right_sidebar = ttk.Frame(self.main_split)
        self.main_split.add(self.right_sidebar, weight=1)
        
        # Glossary Pane
        self.glossary_frame = ttk.Labelframe(self.right_sidebar, text="Glossary", padding=5, bootstyle="info")
        
        self.gloss_tree = ttk.Treeview(self.glossary_frame, columns=("term", "trans"), show="headings")
        self.gloss_tree.heading("term", text="Term"); self.gloss_tree.heading("trans", text="Trans")
        self.gloss_tree.pack(fill=BOTH, expand=True)
        self.gloss_tree.bind("<Double-1>", self.insert_glossary_term)
        
        self.gloss_ctrl = ttk.Frame(self.glossary_frame); self.gloss_ctrl.pack(side=BOTTOM, fill=X)
        self.btn_add_term = ttk.Button(self.gloss_ctrl, text="+ Add", command=self.open_add_term_dialog, bootstyle="info-outline-sm")
        self.btn_add_term.pack(side=RIGHT)

        # Find Pane
        self.find_pane = FindReplacePane(self.right_sidebar, self)

    # --- LAYOUT LOGIC ---
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
        """Handles showing/hiding the right sidebar and dynamic resizing of its panes."""
        # 1. Manage the Main Container (Right Sidebar)
        if not self.glossary_visible and not self.find_visible:
            # Hide the entire right panel if both tools are off
            try: self.main_split.forget(self.right_sidebar)
            except: pass
        else:
            # Show the panel if it's hidden but needs to be visible
            if str(self.right_sidebar) not in self.main_split.panes():
                self.main_split.add(self.right_sidebar, weight=1)

        # 2. Manage the Panes inside (Glossary vs Find)
        self.glossary_frame.pack_forget()
        self.find_pane.pack_forget()

        if self.glossary_visible and self.find_visible:
            self.glossary_frame.pack(side=TOP, fill=BOTH, expand=True, padx=5, pady=5)
            self.find_pane.pack(side=BOTTOM, fill=X, padx=5, pady=5)
        elif self.glossary_visible:
            self.glossary_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        elif self.find_visible:
            self.find_pane.pack(fill=BOTH, expand=True, padx=5, pady=5)
    
    def toggle_glossary(self):
        self.glossary_visible = not self.glossary_visible
        if self.glossary_visible:
            self.btn_toggle_glossary.configure(bootstyle="info-outline")
        else:
            self.btn_toggle_glossary.configure(bootstyle="info")
        self.update_sidebar_visibility()

    def toggle_find_replace(self):
        self.find_visible = not self.find_visible
        if self.find_visible:
            self.btn_toggle_find.configure(bootstyle="warning")
        else:
            self.btn_toggle_find.configure(bootstyle="warning-outline")
        self.update_sidebar_visibility()

    def open_find_replace_dialog(self):
        if not self.find_visible: self.toggle_find_replace()

    # --- POPUP LOGIC ---
    def open_add_term_dialog(self):
        AddTermDialog(self, self.logic)
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.refresh_glossary_view(rec['source'])

    # --- TAG LOGIC ---
    def on_syntax_change(self, event):
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.update_tag_menu(rec['source'])

    # NEW: Updated to show Standard + Context tags
    def update_tag_menu(self, source_text):
        self.menu_tags.delete(0, END)
        syntax = self.tag_syntax_var.get()
        
        # Get structured tags from logic
        tags = self.logic.get_tag_suggestions(source_text, syntax)
        standard = tags['standard']
        context = tags['context']

        if not standard and not context:
            self.menu_tags.add_command(label="(No tags available)", state=DISABLED)
            return

        # 1. Add Standard Tags (Always available)
        if standard:
            for tag in standard:
                self.menu_tags.add_command(label=tag, command=lambda t=tag: self.insert_smart_tag(t))
        
        # 2. Add Separator if both exist
        if standard and context:
            self.menu_tags.add_separator()
            self.menu_tags.add_command(label="From Context:", state=DISABLED)

        # 3. Add Context Tags
        if context:
            for tag in context:
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

    # --- UNSAVED CHANGES LOGIC ---
    def on_text_modified(self, event):
        # Ignore non-editing keys to prevent false positives
        if event.keysym in ("Up", "Down", "Left", "Right", "Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"):
            return
        self.segment_dirty = True

    def check_unsaved_changes(self):
        """Returns True if it's safe to proceed, False if cancelled."""
        if self.segment_dirty:
            resp = messagebox.askyesnocancel("Unsaved Changes", "You have edited this segment but not saved.\nSave before continuing?")
            if resp is None: # Cancel
                return False
            if resp: # Yes, save and proceed
                self.save_segment()
            else: # No, discard and proceed
                self.segment_dirty = False
        return True

    # --- DATA & IO METHODS ---
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
        # Check for unsaved changes before switching files
        if not self.check_unsaved_changes():
            return 

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
            self.segment_dirty = False # Reset dirty flag on load
        except Exception as e: messagebox.showerror("Error", str(e))
    
    def request_file_switch(self, target_path):
        """
        Called by external panes (e.g., FindReplacePane) to safely switch files.
        Checks for unsaved changes, loads the file, and syncs the visual tree.
        """
        # 1. Safety Check
        if not self.check_unsaved_changes():
            return False
        
        # 2. Load File
        self.load_file(target_path)
        
        # 3. Sync Visual Tree Selection
        self.select_file_in_tree(target_path)
        return True

    def select_file_in_tree(self, file_path):
        """Visually selects the specified file in the sidebar tree."""
        target_str = str(file_path)
        # Iterate over language nodes
        for lang_node in self.file_tree.get_children():
            # Iterate over file nodes
            for file_node in self.file_tree.get_children(lang_node):
                values = self.file_tree.item(file_node, 'values')
                if values and values[0] == target_str:
                    self.file_tree.selection_set(file_node)
                    self.file_tree.see(file_node)
                    return

    def save_file(self, silent=False):
        if not self.current_file or not self.xml_tree:
            if not silent: messagebox.showwarning("Warning", "No file loaded.")
            return
        try:
            self.logic.save_xliff(self.xml_tree, self.current_file)
            if not silent:
                messagebox.showinfo("Success", f"File saved: {Path(self.current_file).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def on_row_select(self, event):
        # Check for unsaved changes before switching rows
        if not self.check_unsaved_changes():
            return

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
            self.segment_dirty = False # Reset dirty flag after loading new row

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
        self.segment_dirty = True

    def save_segment(self):
        if not self.current_edit_id: return
        
        # 1. Capture Data
        new_target = self.txt_target.get("1.0", "end-1c")
        new_status = self.edit_status_var.get()
        
        # 2. Update Internal Model
        rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
        if rec:
            rec['target'] = new_target
            rec['status'] = new_status
            
            # 3. Update UI Grid (Treeview)
            status_map = {'new': '🔴', 'needs-review': '🟠', 'translated': '🟢', 'final': '☑️'}
            icon = status_map.get(str(new_status).lower(), '❓')
            tag = str(new_status).lower().replace(" ", "_").replace("-", "_")
            
            for child in self.tree.get_children():
                if str(self.tree.item(child, 'values')[0]) == str(self.current_edit_id):
                    self.tree.item(child, values=(rec['id'], rec['source'].replace('\n', ' '), new_target.replace('\n', ' '), icon), tags=(tag,))
                    break
            
            # 4. Update XML Object
            if 'node' in rec:
                tu = rec['node']
                ns = self.logic.namespaces
                tgt_node = tu.find('xliff:target', namespaces=ns)
                if tgt_node is None:
                    tgt_node = etree.SubElement(tu, f"{{{ns['xliff']}}}target")
                tgt_node.text = new_target
                tgt_node.set('state', new_status)
        
        # 5. Write to Disk Immediately
        self.save_file(silent=True)
        self.segment_dirty = False

    def save_and_next(self):
        self.save_segment()
        self.navigate_grid(1)

    def navigate_grid(self, direction):
        sel = self.tree.selection(); items = self.tree.get_children()
        if not items: return
        new_idx = 0
        if sel: new_idx = max(0, min(len(items)-1, items.index(sel[0]) + direction))
        self.tree.selection_set(items[new_idx]); self.tree.see(items[new_idx]); self.on_row_select(None)

    def setup_hotkeys(self):
        # Added 'break' to prevent newline insertion on Ctrl+Enter
        self.txt_target.bind("<Control-Return>", lambda e: self.save_and_next() or "break")
        self.txt_target.bind("<Control-b>", lambda e: self.format_text("b") or "break")
        self.txt_target.bind("<Control-i>", lambda e: self.format_text("i") or "break")
        self.txt_target.bind("<Control-u>", lambda e: self.format_text("u") or "break")
        self.bind_all("<Control-Q>", self.toggle_admin_mode)
        self.bind_all("<Control-s>", lambda e: self.save_file())
        
    def toggle_admin_mode(self, event=None):
        self.admin_mode_active = not self.admin_mode_active
        print(f"Admin mode: {self.admin_mode_active}")

    # --- NEW: Enhanced Context Menus (Bulk Actions) ---
    def create_context_menus(self):
        # 1. Grid Context Menu (Bulk Actions)
        self.menu_grid = tk.Menu(self, tearoff=0)
        
        # Revert Action
        self.menu_grid.add_command(label="↺ Revert to Source", command=self.bulk_revert_to_source)
        self.menu_grid.add_separator()
        
        # Clipboard Actions
        self.menu_grid.add_command(label="📄 Copy Source Text", command=lambda: self.copy_selection_to_clipboard("source"))
        self.menu_grid.add_command(label="📄 Copy Target Text", command=lambda: self.copy_selection_to_clipboard("target"))
        self.menu_grid.add_separator()
        
        # Status Submenu
        self.status_menu = tk.Menu(self.menu_grid, tearoff=0)
        self.menu_grid.add_cascade(label="Set Status", menu=self.status_menu)
        
        self.status_menu.add_command(label="🔴 New", command=lambda: self.bulk_set_status("new"))
        self.status_menu.add_command(label="🟠 Needs Review", command=lambda: self.bulk_set_status("needs-review"))
        self.status_menu.add_command(label="🟢 Translated", command=lambda: self.bulk_set_status("translated"))
        self.status_menu.add_command(label="☑️ Final", command=lambda: self.bulk_set_status("final"))

        # 2. Text Box Context Menus (Standard)
        self.menu_source = tk.Menu(self, tearoff=0)
        self.menu_source.add_command(label="Copy", command=lambda: self.text_copy(self.txt_source))
        
        self.menu_target = tk.Menu(self, tearoff=0)
        self.menu_target.add_command(label="Copy", command=lambda: self.text_copy(self.txt_target))
        self.menu_target.add_command(label="Paste", command=lambda: self.text_paste(self.txt_target))

    def show_grid_menu(self, event):
        if self.tree.identify_row(event.y): self.menu_grid.post(event.x_root, event.y_root)
    def show_source_menu(self, event): self.menu_source.post(event.x_root, event.y_root)
    def show_target_menu(self, event): self.menu_target.post(event.x_root, event.y_root)
    
    def copy_source_to_target(self):
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", rec['source']); self.segment_dirty = True
            
    def get_selected_ids(self):
        """Returns a list of XLIFF IDs for all currently selected rows."""
        return [self.tree.item(i)['values'][0] for i in self.tree.selection()]

    def bulk_set_status(self, new_status):
        ids = self.get_selected_ids()
        if not ids: return

        # Visual map for updating the tree immediately
        status_map = {'new': '🔴', 'needs-review': '🟠', 'translated': '🟢', 'final': '☑️'}
        icon = status_map.get(new_status, '❓')
        tag = new_status.replace("-", "_")

        count = 0
        for uid in ids:
            rec = next((r for r in self.data_store if str(r['id']) == str(uid)), None)
            if rec:
                # Update Data Store
                rec['status'] = new_status

                # Update XML
                if 'node' in rec:
                    tgt_node = rec['node'].find('xliff:target', namespaces=self.logic.namespaces)
                    if tgt_node is None:
                        tgt_node = etree.SubElement(rec['node'], f"{{{self.logic.namespaces['xliff']}}}target")
                        tgt_node.text = rec['target']
                    tgt_node.set('state', new_status)

                # Update Treeview (Visuals)
                for child in self.tree.get_children():
                    if str(self.tree.item(child, 'values')[0]) == str(uid):
                        vals = list(self.tree.item(child, 'values'))
                        vals[3] = icon # Status column
                        self.tree.item(child, values=vals, tags=(tag,))
                        break
                count += 1

        if count > 0:
            self.save_file(silent=True)
            # Update the editor panel if the currently edited row was changed
            if self.current_edit_id in ids:
                self.edit_status_var.set(new_status)

    def bulk_revert_to_source(self):
        ids = self.get_selected_ids()
        if not ids: return

        if not messagebox.askyesno("Confirm Revert", f"Are you sure you want to revert {len(ids)} segments to their source text?"):
            return

        count = 0
        for uid in ids:
            rec = next((r for r in self.data_store if str(r['id']) == str(uid)), None)
            if rec:
                new_text = rec['source']
                rec['target'] = new_text
                
                # Update XML
                if 'node' in rec:
                    tgt_node = rec['node'].find('xliff:target', namespaces=self.logic.namespaces)
                    if tgt_node is None:
                        tgt_node = etree.SubElement(rec['node'], f"{{{self.logic.namespaces['xliff']}}}target")
                    tgt_node.text = new_text

                # Update Treeview
                for child in self.tree.get_children():
                    if str(self.tree.item(child, 'values')[0]) == str(uid):
                        vals = list(self.tree.item(child, 'values'))
                        vals[2] = new_text.replace('\n', ' ') # Target column
                        self.tree.item(child, values=vals)
                        break
                count += 1

        if count > 0:
            self.save_file(silent=True)
            if self.current_edit_id in ids:
                self.txt_target.delete("1.0", END)
                self.txt_target.insert("1.0", self.txt_source.get("1.0", END).strip())

    def copy_selection_to_clipboard(self, mode="source"):
        ids = self.get_selected_ids()
        text_lines = []
        for uid in ids:
            rec = next((r for r in self.data_store if str(r['id']) == str(uid)), None)
            if rec:
                val = rec['source'] if mode == "source" else rec['target']
                if val: text_lines.append(val)

        if text_lines:
            full_text = "\n".join(text_lines)
            self.clipboard_clear()
            self.clipboard_append(full_text)

    def clear_target(self): self.txt_target.delete("1.0", END); self.segment_dirty = True
    def text_copy(self, w): 
        try: self.clipboard_clear(); self.clipboard_append(w.get("sel.first", "sel.last"))
        except: pass
    def text_paste(self, w):
        try: w.insert(tk.INSERT, self.clipboard_get()); self.segment_dirty = True
        except: pass
    
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
