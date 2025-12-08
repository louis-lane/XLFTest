import tkinter as tk
from tkinter import filedialog, messagebox
# --- CRITICAL IMPORT: Rename standard ttk so we can use its PanedWindow ---
from tkinter import ttk as tk_ttk 
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language, log_errors
import shutil
import re
import threading
import os

class EditorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_folder = None
        self.current_file = None
        self.file_map = {} 
        
        # --- MAIN LAYOUT: 3 PANES (Sidebar | Grid | Editor) ---
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

        # 2. RIGHT CONTENT AREA
        self.content_area = ttk.Frame(self.main_split)
        self.main_split.add(self.content_area, weight=4)

        # --- TOP CONTROLS ---
        top_controls = ttk.Frame(self.content_area, padding=(0, 0, 0, 5))
        top_controls.pack(fill=X)

        ttk.Label(top_controls, text="Search:").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top_controls, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=LEFT, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.apply_filter)

        ttk.Label(top_controls, text="Filter Status:").pack(side=LEFT, padx=(10, 5))
        self.filter_var = tk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(top_controls, textvariable=self.filter_var, values=("All", "New", "Needs Review", "Translated", "Final"), state="readonly", width=15)
        self.filter_combo.pack(side=LEFT)
        self.filter_combo.bind("<<ComboboxSelected>>", self.apply_filter)

        ttk.Button(top_controls, text="🔍 Find & Replace", command=self.open_find_replace_dialog, bootstyle="warning-outline").pack(side=RIGHT)

        # --- EDITOR SPLIT ---
        self.editor_split = tk_ttk.PanedWindow(self.content_area, orient=VERTICAL)
        self.editor_split.pack(fill=BOTH, expand=True)
        
        # Grid Pane
        self.grid_frame = ttk.Frame(self.editor_split)
        self.editor_split.add(self.grid_frame, weight=2)
        
        cols = ("id", "status", "source", "target")
        self.tree = ttk.Treeview(self.grid_frame, columns=cols, show="headings", selectmode="extended") 
        
        self.tree.heading("id", text="ID")
        self.tree.heading("status", text="Status")
        self.tree.heading("source", text="Original Source")
        self.tree.heading("target", text="Translated Target")
        
        self.tree.column("id", width=60, stretch=False)
        self.tree.column("status", width=100, stretch=False)
        self.tree.column("source", width=300)
        self.tree.column("target", width=300)
        
        grid_scroll = ttk.Scrollbar(self.grid_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=grid_scroll.set)
        grid_scroll.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        
        # Context Menus
        self.create_context_menus()
        self.tree.bind("<Button-3>", self.show_grid_menu)
        self.tree.bind("<Button-2>", self.show_grid_menu) 

        # --- EDIT PANEL (With Scrollbars) ---
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=1)
        
        # 1. Pack Controls at BOTTOM (So they stay visible)
        controls_bot = ttk.Frame(self.edit_panel)
        controls_bot.pack(side=BOTTOM, fill=X, pady=5)

        ttk.Label(controls_bot, text="Status:").pack(side=LEFT, padx=(0, 5))
        self.edit_status_var = tk.StringVar()
        self.status_dropdown = ttk.Combobox(controls_bot, textvariable=self.edit_status_var, values=("new", "needs-review", "translated", "final"), state="readonly", width=15)
        self.status_dropdown.pack(side=LEFT)

        btn_nav_frame = ttk.Frame(controls_bot)
        btn_nav_frame.pack(side=RIGHT)
        ttk.Button(btn_nav_frame, text="Previous", command=lambda: self.navigate_grid(-1), bootstyle="secondary-outline").pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_nav_frame, text="Next", command=lambda: self.navigate_grid(1), bootstyle="secondary-outline").pack(side=LEFT, padx=(0, 5))
        ttk.Button(btn_nav_frame, text="Save & Next", command=self.save_and_next, bootstyle="success").pack(side=LEFT)
        ttk.Label(self.edit_panel, text="[Ctrl+Enter: Save & Next]", font=("Helvetica", 8), foreground="gray").pack(side=BOTTOM, anchor=E)

        # 2. Pack Text Areas in remaining space (Expandable)
        
        # Source Text Area
        ttk.Label(self.edit_panel, text="Original Source:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        src_frame = ttk.Frame(self.edit_panel)
        src_frame.pack(fill=BOTH, expand=True, pady=(0, 5))
        
        src_scroll = ttk.Scrollbar(src_frame, orient=VERTICAL)
        self.txt_source = tk.Text(src_frame, height=4, bg="white", fg="black", state=DISABLED, wrap="word", yscrollcommand=src_scroll.set)
        src_scroll.config(command=self.txt_source.yview)
        
        src_scroll.pack(side=RIGHT, fill=Y)
        self.txt_source.pack(side=LEFT, fill=BOTH, expand=True)
        self.txt_source.bind("<Button-3>", self.show_source_menu)
        
        # Target Text Area
        ttk.Label(self.edit_panel, text="Translation Target:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        tgt_frame = ttk.Frame(self.edit_panel)
        tgt_frame.pack(fill=BOTH, expand=True, pady=(0, 5))
        
        tgt_scroll = ttk.Scrollbar(tgt_frame, orient=VERTICAL)
        self.txt_target = tk.Text(tgt_frame, height=4, bg="white", fg="black", insertbackground="black", wrap="word", yscrollcommand=tgt_scroll.set)
        tgt_scroll.config(command=self.txt_target.yview)
        
        tgt_scroll.pack(side=RIGHT, fill=Y)
        self.txt_target.pack(side=LEFT, fill=BOTH, expand=True)
        self.txt_target.bind("<Button-3>", self.show_target_menu)
        
        # Setup State & Keys
        self.xml_tree = None
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.data_store = []
        self.current_edit_id = None
        self.setup_hotkeys()

    # --- HOTKEYS ---
    def setup_hotkeys(self):
        self.txt_target.bind("<Control-Return>", lambda e: self.save_and_next())
        self.txt_target.bind("<Control-Up>", lambda e: self.navigate_grid(-1))
        self.txt_target.bind("<Control-Down>", lambda e: self.navigate_grid(1))
        self.txt_target.bind("<Alt-s>", lambda e: self.replace_edit_with_source())
        self.txt_target.bind("<Alt-c>", lambda e: self.copy_source_to_clipboard())
        self.tree.bind("<Control-Up>", lambda e: self.navigate_grid(-1))
        self.tree.bind("<Control-Down>", lambda e: self.navigate_grid(1))

    # --- NAVIGATION LOGIC ---
    def navigate_grid(self, direction):
        current_selection = self.tree.selection()
        all_items = self.tree.get_children()
        if not all_items: return
        
        if not current_selection:
            new_index = 0
        else:
            current_id = current_selection[0]
            try:
                current_index = all_items.index(current_id)
                new_index = current_index + direction
            except ValueError: new_index = 0
        
        if 0 <= new_index < len(all_items):
            new_item = all_items[new_index]
            self.tree.selection_set(new_item)
            self.tree.see(new_item)
            self.on_row_select(None)
            self.txt_target.focus_set()
            return "break"

    def save_and_next(self):
        self.save_segment()
        self.navigate_grid(1)
        return "break"

    def copy_source_to_clipboard(self):
        src = self.txt_source.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(src)
        return "break"

    # --- LOADING LOGIC ---
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
        file_path = item['values'][0]
        self.load_file(file_path)

    def load_file(self, path):
        self.current_file = path
        try:
            self.xml_tree = etree.parse(path)
            self.data_store = []
            for i in self.tree.get_children(): self.tree.delete(i)
            for tu in self.xml_tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                uid = tu.get('id')
                src_node = tu.find('xliff:source', namespaces=self.namespaces)
                src = (src_node.text or "") if src_node is not None else ""
                tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
                tgt = (tgt_node.text or "") if tgt_node is not None else ""
                status = tgt_node.get('state', 'new') if tgt_node is not None else 'new'
                self.data_store.append({'id': uid, 'source': src, 'target': tgt, 'status': status, 'node': tu})
            self.apply_filter()
        except Exception as e: messagebox.showerror("Error", f"Could not load file: {e}")

    def apply_filter(self, event=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        filter_status = self.filter_var.get().lower()
        search_term = self.search_var.get().lower()
        for rec in self.data_store:
            s_status = str(rec['status']).lower()
            if filter_status != "all" and s_status.replace(" ", "") != filter_status.replace(" ", ""): continue
            s_src = str(rec['source']).lower(); s_tgt = str(rec['target']).lower(); s_id = str(rec['id']).lower()
            if search_term and (search_term not in s_src and search_term not in s_tgt and search_term not in s_id): continue
            display_src = rec['source'].replace('\n', ' '); display_tgt = rec['target'].replace('\n', ' ')
            tag = s_status.replace(" ", "_")
            self.tree.insert("", "end", values=(rec['id'], rec['status'], display_src, display_tgt), tags=(tag,))
        self.tree.tag_configure('new', foreground='#ff4d4d') 
        self.tree.tag_configure('needs_review', foreground='#ffad33')
        self.tree.tag_configure('translated', foreground='#33cc33')
        self.tree.tag_configure('final', foreground='#3399ff')

    def on_row_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        uid = self.tree.item(sel[0])['values'][0]
        rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
        if rec:
            self.current_edit_id = uid
            self.txt_source.config(state=NORMAL)
            self.txt_source.delete("1.0", END); self.txt_source.insert("1.0", rec['source'])
            self.txt_source.config(state=DISABLED)
            self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", rec['target'])
            self.edit_status_var.set(rec['status'])

    def save_segment(self):
        if not self.current_edit_id: return
        new_txt = self.txt_target.get("1.0", "end-1c")
        new_status = self.edit_status_var.get()
        rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
        if not rec: return
        self._update_single_record(rec, new_txt, new_status)
        try:
            self.xml_tree.write(self.current_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)
            self.apply_filter()
            for child in self.tree.get_children():
                if str(self.tree.item(child, 'values')[0]) == str(self.current_edit_id):
                    self.tree.selection_set(child); self.tree.see(child); break
        except Exception as e: messagebox.showerror("Error", f"Failed to save: {e}")

    # --- CONTEXT MENUS & HELPERS ---
    def create_context_menus(self):
        self.menu_grid = tk.Menu(self, tearoff=0)
        self.menu_grid.add_command(label="Mark as New", command=lambda: self.bulk_set_status("new"))
        self.menu_grid.add_command(label="Mark as Needs Review", command=lambda: self.bulk_set_status("needs-review"))
        self.menu_grid.add_command(label="Mark as Translated", command=lambda: self.bulk_set_status("translated"))
        self.menu_grid.add_command(label="Mark as Final", command=lambda: self.bulk_set_status("final"))
        self.menu_grid.add_separator()
        self.menu_grid.add_command(label="Copy Source", command=lambda: self.copy_grid_to_clipboard("source"))
        self.menu_grid.add_command(label="Copy Target", command=lambda: self.copy_grid_to_clipboard("target"))
        self.menu_grid.add_command(label="Paste to Target", command=self.paste_to_grid_target)
        self.menu_grid.add_separator()
        self.menu_grid.add_command(label="Copy Source -> Target", command=self.copy_source_to_target)

        self.menu_source_txt = tk.Menu(self, tearoff=0)
        self.menu_source_txt.add_command(label="Copy", command=lambda: self.text_copy(self.txt_source))

        self.menu_target_txt = tk.Menu(self, tearoff=0)
        self.menu_target_txt.add_command(label="Cut", command=lambda: self.text_cut(self.txt_target))
        self.menu_target_txt.add_command(label="Copy", command=lambda: self.text_copy(self.txt_target))
        self.menu_target_txt.add_command(label="Paste", command=lambda: self.text_paste(self.txt_target))
        self.menu_target_txt.add_separator()
        self.menu_target_txt.add_command(label="Replace with Source (Alt+S)", command=self.replace_edit_with_source)

    def show_grid_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            if item_id not in self.tree.selection(): self.tree.selection_set(item_id); self.on_row_select(None)
        if self.tree.selection(): self.menu_grid.post(event.x_root, event.y_root)

    def show_source_menu(self, event): self.menu_source_txt.post(event.x_root, event.y_root)
    def show_target_menu(self, event): self.menu_target_txt.post(event.x_root, event.y_root)

    def text_copy(self, widget):
        try: txt = widget.get("sel.first", "sel.last"); self.clipboard_clear(); self.clipboard_append(txt)
        except: pass
    def text_cut(self, widget):
        try: self.text_copy(widget); widget.delete("sel.first", "sel.last")
        except: pass
    def text_paste(self, widget):
        try: txt = self.clipboard_get(); widget.insert(tk.INSERT, txt)
        except: pass
    def replace_edit_with_source(self):
        src = self.txt_source.get("1.0", "end-1c")
        self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", src)
        return "break"

    def copy_grid_to_clipboard(self, col):
        selected_items = self.tree.selection()
        if not selected_items: return
        text_list = []
        for item_id in selected_items:
            vals = self.tree.item(item_id, 'values')
            idx = 2 if col == "source" else 3
            text_list.append(str(vals[idx]))
        self.clipboard_clear(); self.clipboard_append("\n".join(text_list))

    def paste_to_grid_target(self):
        try: text = self.clipboard_get()
        except: return 
        self.bulk_update_text(text)

    def copy_source_to_target(self):
        selected_items = self.tree.selection()
        if not selected_items: return
        for item_id in selected_items:
            uid = self.tree.item(item_id, 'values')[0]
            rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
            if rec: self._update_single_record(rec, rec['source'], "translated")
        self._save_and_refresh()

    def bulk_update_text(self, new_text):
        selected_items = self.tree.selection()
        if not selected_items: return
        for item
