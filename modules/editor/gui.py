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

        # Find & Replace Button
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
        
        # --- CONTEXT MENUS ---
        self.create_context_menus()
        # Bind Grid Right-Click
        self.tree.bind("<Button-3>", self.show_grid_menu)
        self.tree.bind("<Button-2>", self.show_grid_menu) # Mac

        # Edit Panel Pane
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=1)
        
        ttk.Label(self.edit_panel, text="Original Source:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        self.txt_source = tk.Text(self.edit_panel, height=3, bg="white", fg="black", state=DISABLED)
        self.txt_source.pack(fill=X, pady=(0, 5))
        # Bind Source Text Right-Click
        self.txt_source.bind("<Button-3>", self.show_source_menu)
        self.txt_source.bind("<Button-2>", self.show_source_menu)
        
        ttk.Label(self.edit_panel, text="Translation Target:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        self.txt_target = tk.Text(self.edit_panel, height=3, bg="white", fg="black", insertbackground="black")
        self.txt_target.pack(fill=X, pady=(0, 5))
        # Bind Target Text Right-Click
        self.txt_target.bind("<Button-3>", self.show_target_menu)
        self.txt_target.bind("<Button-2>", self.show_target_menu)
        
        # Controls
        controls_bot = ttk.Frame(self.edit_panel)
        controls_bot.pack(fill=X, pady=5)

        ttk.Label(controls_bot, text="Status:").pack(side=LEFT, padx=(0, 5))
        self.edit_status_var = tk.StringVar()
        self.status_dropdown = ttk.Combobox(controls_bot, textvariable=self.edit_status_var, values=("new", "needs-review", "translated", "final"), state="readonly", width=15)
        self.status_dropdown.pack(side=LEFT)

        ttk.Button(controls_bot, text="Save Segment", command=self.save_segment, bootstyle="success").pack(side=RIGHT)

        # Internal Data State
        self.xml_tree = None
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.data_store = []
        self.current_edit_id = None

    # --- CONTEXT MENUS LOGIC ---
    def create_context_menus(self):
        # 1. Grid Menu
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

        # 2. Source Text Menu (Read Only)
        self.menu_source_txt = tk.Menu(self, tearoff=0)
        self.menu_source_txt.add_command(label="Copy", command=lambda: self.text_copy(self.txt_source))

        # 3. Target Text Menu (Editable)
        self.menu_target_txt = tk.Menu(self, tearoff=0)
        self.menu_target_txt.add_command(label="Cut", command=lambda: self.text_cut(self.txt_target))
        self.menu_target_txt.add_command(label="Copy", command=lambda: self.text_copy(self.txt_target))
        self.menu_target_txt.add_command(label="Paste", command=lambda: self.text_paste(self.txt_target))
        self.menu_target_txt.add_separator()
        self.menu_target_txt.add_command(label="Replace with Source", command=self.replace_edit_with_source)

    # --- SHOW MENU HANDLERS ---
    def show_grid_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            if item_id not in self.tree.selection():
                self.tree.selection_set(item_id)
                self.on_row_select(None)
        if self.tree.selection():
            self.menu_grid.post(event.x_root, event.y_root)

    def show_source_menu(self, event):
        self.menu_source_txt.post(event.x_root, event.y_root)

    def show_target_menu(self, event):
        self.menu_target_txt.post(event.x_root, event.y_root)

    # --- TEXT BOX HELPERS ---
    def text_copy(self, widget):
        try:
            txt = widget.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(txt)
        except: pass

    def text_cut(self, widget):
        try:
            self.text_copy(widget)
            widget.delete("sel.first", "sel.last")
        except: pass

    def text_paste(self, widget):
        try:
            txt = self.clipboard_get()
            widget.insert(tk.INSERT, txt)
        except: pass

    def replace_edit_with_source(self):
        src = self.txt_source.get("1.0", "end-1c")
        self.txt_target.delete("1.0", END)
        self.txt_target.insert("1.0", src)

    # --- GRID HELPERS ---
    def copy_grid_to_clipboard(self, col):
        selected_items = self.tree.selection()
        if not selected_items: return
        text_list = []
        for item_id in selected_items:
            vals = self.tree.item(item_id, 'values')
            idx = 2 if col == "source" else 3
            text_list.append(str(vals[idx]))
        self.clipboard_clear()
        self.clipboard_append("\n".join(text_list))

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
        for item_id in selected_items:
            uid = self.tree.item(item_id, 'values')[0]
            rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
            if rec: self._update_single_record(rec, new_text, "translated")
        self._save_and_refresh()

    def bulk_set_status(self, new_status):
        selected_items = self.tree.selection()
        if not selected_items: return
        for item_id in selected_items:
            uid = self.tree.item(item_id, 'values')[0]
            rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
            if rec: self._update_single_record(rec, rec['target'], new_status)
        self._save_and_refresh()

    def _update_single_record(self, rec, text, status):
        rec['target'] = text
        rec['status'] = status
        tgt_node = rec['node'].find('xliff:target', namespaces=self.namespaces)
        if tgt_node is None: tgt_node = etree.SubElement(rec['node'], f"{{{self.namespaces['xliff']}}}target")
        tgt_node.text = text
        tgt_node.set('state', status)

    def _save_and_refresh(self):
        try:
            self.xml_tree.write(self.current_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)
            current_selection = self.tree.selection()
            self.apply_filter()
            valid_selection = [item for item in current_selection if self.tree.exists(item)]
            if valid_selection:
                self.tree.selection_set(valid_selection)
                self.on_row_select(None)
        except Exception as e: messagebox.showerror("Error", f"Failed to save: {e}")

    # --- HELPER: JUMP TO ID ---
    def jump_to_id(self, target_id):
        self.tree.selection_remove(self.tree.selection())
        for child in self.tree.get_children():
            item_id = self.tree.item(child, 'values')[0]
            if str(item_id) == str(target_id):
                self.tree.selection_set(child)
                self.tree.focus(child)
                self.tree.see(child)
                self.on_row_select(None)
                return

    # --- LOADING LOGIC ---
    def load_project_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.current_folder = Path(folder)
        
        for i in self.file_tree.get_children(): self.file_tree.delete(i)
        self.file_map = {}

        xliffs = list(self.current_folder.glob("*.xliff"))
        if not xliffs:
            messagebox.showwarning("Empty", "No .xliff files found.")
            return

        for f in xliffs:
            lang = get_target_language(f)
            if lang not in self.file_map: self.file_map[lang] = []
            self.file_map[lang].append(f)

        for lang, files in self.file_map.items():
            lang_node = self.file_tree.insert("", "end", text=lang, open=True)
            for f in files:
                self.file_tree.insert(lang_node, "end", text=f.name, values=(str(f),))

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

        except Exception as e:
            messagebox.showerror("Error", f"Could not load file: {e}")

    def apply_filter(self, event=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        filter_status = self.filter_var.get().lower()
        search_term = self.search_var.get().lower()
        
        for rec in self.data_store:
            s_status = str(rec['status']).lower()
            if filter_status != "all" and s_status.replace(" ", "") != filter_status.replace(" ", ""): continue
            
            s_src = str(rec['source']).lower()
            s_tgt = str(rec['target']).lower()
            s_id = str(rec['id']).lower()
            
            if search_term and (search_term not in s_src and search_term not in s_tgt and search_term not in s_id): continue
                
            display_src = rec['source'].replace('\n', ' ')
            display_tgt = rec['target'].replace('\n', ' ')
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

    # --- ADVANCED FIND / REPLACE / ROLLBACK ---
    def open_find_replace_dialog(self):
        if not self.current_folder:
            messagebox.showwarning("Warning", "Please open a project folder first.")
            return

        dialog = ttk.Toplevel(self)
        dialog.title("Find & Replace")
        dialog.geometry("700x800")
        
        input_frame = ttk.Frame(dialog, padding=10)
        input_frame.pack(fill=X)
        ttk.Label(input_frame, text="Find what:").pack(anchor=W)
        entry_find = ttk.Entry(input_frame)
        entry_find.pack(fill=X, pady=(0, 10))
        ttk.Label(input_frame, text="Replace with:").pack(anchor=W)
        entry_replace = ttk.Entry(input_frame)
        entry_replace.pack(fill=X, pady=(0, 10))
        
        mid_frame = ttk.Frame(dialog, padding=10)
        mid_frame.pack(fill=X)
        
        options_frame = ttk.Labelframe(mid_frame, text="Options", padding=10)
        options_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))
        match_case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Match Case", variable=match_case_var).pack(anchor=W)
        exact_match_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Match Whole Content", variable=exact_match_var).pack(anchor=W)
        regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Use Regex", variable=regex_var).pack(anchor=W)
        backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Create Backups", variable=backup_var).pack(anchor=W)

        scope_frame = ttk.Labelframe(mid_frame, text="Scope", padding=10)
        scope_frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=(5, 0))
        scope_var = tk.StringVar(value="current_file")
        current_lang = "Unknown"
        if self.current_file: current_lang = get_target_language(self.current_file)
        ttk.Radiobutton(scope_frame, text="Current File", variable=scope_var, value="current_file").pack(anchor=W)
        rb_lang = ttk.Radiobutton(scope_frame, text=f"All '{current_lang}' Files", variable=scope_var, value="current_lang")
        rb_lang.pack(anchor=W)
        if not self.current_file: rb_lang.config(state=DISABLED)
        ttk.Radiobutton(scope_frame, text="Entire Project", variable=scope_var, value="all_files").pack(anchor=W)

        btn_frame = ttk.Frame(dialog, padding=10)
        btn_frame.pack(fill=X)
        progress = ttk.Progressbar(dialog, mode='determinate', bootstyle="success-striped")
        
        results_frame = ttk.Labelframe(dialog, text="Search Results (Double-click to Jump)", padding=10)
        results_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        res_cols = ("file", "id", "context")
        results_tree = ttk.Treeview(results_frame, columns=res_cols, show="headings", selectmode="browse")
        results_tree.heading("file", text="File"); results_tree.column("file", width=150)
        results_tree.heading("id", text="ID"); results_tree.column("id", width=60)
        results_tree.heading("context", text="Matched Text"); results_tree.column("context", width=300)
        res_scroll = ttk.Scrollbar(results_frame, orient=VERTICAL, command=results_tree.yview)
        results_tree.configure(yscroll=res_scroll.set)
        res_scroll.pack(side=RIGHT, fill=Y)
        results_tree.pack(fill=BOTH, expand=True)

        def on_result_double_click(event):
            sel = results_tree.selection()
            if not sel: return
            item = results_tree.item(sel[0])
            full_path = item['tags'][0]
            target_id = item['values'][1]
            if str(self.current_file) != str(full_path): self.load_file(full_path)
            self.jump_to_id(target_id)

        results_tree.bind("<Double-1>", on_result_double_click)

        def get_file_list():
            scope = scope_var.get()
            files_to_process = []
            if scope == "current_file":
                if self.current_file: files_to_process = [Path(self.current_file)]
            elif scope == "current_lang":
                if current_lang in self.file_map: files_to_process = self.file_map[current_lang]
            elif scope == "all_files":
                for file_list in self.file_map.values(): files_to_process.extend(file_list)
            return files_to_process

        def run_processing(mode="find"):
            find_text = entry_find.get()
            replace_text = entry_replace.get()
            match_case = match_case_var.get()
            use_regex = regex_var.get()
            make_backup = backup_var.get()
            exact_match = exact_match_var.get()
            
            if mode != "rollback" and not find_text: return
            files_to_process = get_file_list()
            if not files_to_process:
                messagebox.showinfo("Info", "No files selected.")
                return

            for i in results_tree.get_children(): results_tree.delete(i)
            progress.pack(fill=X, padx=10, pady=(0, 10))

            pattern = None
            if mode != "rollback" and use_regex:
                try:
                    flags = 0 if match_case else re.IGNORECASE
                    pattern = re.compile(find_text, flags)
                except re.error as e:
                    messagebox.showerror("Regex Error", f"Invalid Pattern: {e}"); return

            total_hits = 0; files_mod = 0; process_errors = []
            progress['maximum'] = len(files_to_process); progress['value'] = 0

            if mode == "rollback":
                restored_count = 0
                for idx, file_path in enumerate(files_to_process):
                    bak_path = Path(str(file_path) + ".bak")
                    if bak_path.exists():
                        try:
                            shutil.copy2(bak_path, file_path)
                            restored_count += 1
                        except Exception as e: process_errors.append(f"Failed to restore {file_path.name}: {e}")
                    progress['value'] = idx + 1
                    dialog.update_idletasks()
                
                if process_errors:
                    log_errors(self.current_folder, process_errors)
                    messagebox.showwarning("Rollback Warnings", f"Restored {restored_count} files.\nSome errors occurred (see log).")
                else: messagebox.showinfo("Rollback", f"Restored {restored_count} files.")
                if self.current_file: self.load_file(self.current_file)
                progress.pack_forget()
                return

            for idx, file_path in enumerate(files_to_process):
                try:
                    tree = etree.parse(str(file_path))
                    file_dirty = False
                    for tu in tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                        tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
                        if tgt_node is not None and tgt_node.text:
                            original_text = tgt_node.text
                            new_text = original_text
                            found = False
                            
                            if use_regex:
                                if pattern.search(original_text):
                                    found = True
                                    if mode == "replace": new_text = pattern.sub(replace_text, original_text)
                            elif exact_match:
                                if match_case:
                                    if original_text == find_text:
                                        found = True
                                        if mode == "replace": new_text = replace_text
                                else:
                                    if original_text.lower() == find_text.lower():
                                        found = True
                                        if mode == "replace": new_text = replace_text
                            else:
                                if match_case:
                                    if find_text in original_text:
                                        found = True
                                        if mode == "replace": new_text = original_text.replace(find_text, replace_text)
                                else:
                                    if find_text.lower() in original_text.lower():
                                        found = True
                                        if mode == "replace":
                                            esc_pattern = re.compile(re.escape(find_text), re.IGNORECASE)
                                            new_text = esc_pattern.sub(replace_text, original_text)

                            if found:
                                total_hits += 1
                                if mode == "find":
                                    display_txt = original_text.replace('\n', ' ')[:50]
                                    results_tree.insert("", "end", values=(file_path.name, tu.get('id'), display_txt), tags=(str(file_path),))
                                if mode == "replace" and new_text != original_text:
                                    tgt_node.text = new_text; tgt_node.set('state', 'translated'); file_dirty = True

                    if file_dirty and mode == "replace":
                        files_mod += 1
                        if make_backup: shutil.copy2(file_path, str(file_path) + ".bak")
                        tree.write(str(file_path), encoding="UTF-8", xml_declaration=True, pretty_print=True)

                except Exception as e: process_errors.append(f"Error {file_path.name}: {e}")
                progress['value'] = idx + 1
                dialog.update_idletasks()

            progress.pack_forget()
            if process_errors:
                log_errors(self.current_folder, process_errors)
                err_msg = "\n(Some files failed - check error_log.txt)"
            else: err_msg = ""

            if mode == "replace":
                messagebox.showinfo("Complete", f"Replaced {total_hits} occurrences.\nModified {files_mod} files.{err_msg}")
                if self.current_file: self.load_file(self.current_file)
            elif mode == "find":
                if total_hits == 0: messagebox.showinfo("Result", f"No matches found.{err_msg}")
                elif err_msg: messagebox.showwarning("Warning", f"Found {total_hits} matches.{err_msg}")

        def thread_find(): threading.Thread(target=lambda: run_processing("find")).start()
        def thread_replace(): threading.Thread(target=lambda: run_processing("replace")).start()
        def thread_rollback(): threading.Thread(target=lambda: run_processing("rollback")).start()

        ttk.Button(btn_frame, text="Find All", command=thread_find, bootstyle="info-outline").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Replace All", command=thread_replace, bootstyle="danger").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy, bootstyle="secondary").pack(side=RIGHT)
        ttk.Button(btn_frame, text="Restore Backups", command=thread_rollback, bootstyle="warning-outline").pack(side=RIGHT, padx=20)
