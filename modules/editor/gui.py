import tkinter as tk
from tkinter import filedialog, messagebox
# --- CRITICAL IMPORT: Rename standard ttk so we can use its PanedWindow ---
from tkinter import ttk as tk_ttk 
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language
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

        # Edit Panel Pane
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=1)
        
        ttk.Label(self.edit_panel, text="Original Source:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        self.txt_source = tk.Text(self.edit_panel, height=3, bg="white", fg="black", state=DISABLED)
        self.txt_source.pack(fill=X, pady=(0, 5))
        
        ttk.Label(self.edit_panel, text="Translation Target:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        self.txt_target = tk.Text(self.edit_panel, height=3, bg="white", fg="black", insertbackground="black")
        self.txt_target.pack(fill=X, pady=(0, 5))
        
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
            if filter_status != "all" and s_status.replace(" ", "") != filter_status.replace(" ", ""):
                continue
            
            s_src = str(rec['source']).lower()
            s_tgt = str(rec['target']).lower()
            s_id = str(rec['id']).lower()
            
            if search_term and (search_term not in s_src and search_term not in s_tgt and search_term not in s_id):
                continue
                
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
            self.txt_source.delete("1.0", END)
            self.txt_source.insert("1.0", rec['source'])
            self.txt_source.config(state=DISABLED)
            
            self.txt_target.delete("1.0", END)
            self.txt_target.insert("1.0", rec['target'])
            self.edit_status_var.set(rec['status'])

    def save_segment(self):
        if not self.current_edit_id: return
        new_txt = self.txt_target.get("1.0", "end-1c")
        new_status = self.edit_status_var.get()
        
        rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
        if not rec: return
        
        rec['target'] = new_txt
        rec['status'] = new_status
        
        tgt_node = rec['node'].find('xliff:target', namespaces=self.namespaces)
        if tgt_node is None:
            tgt_node = etree.SubElement(rec['node'], f"{{{self.namespaces['xliff']}}}target")
        
        tgt_node.text = new_txt
        tgt_node.set('state', new_status)
        
        try:
            self.xml_tree.write(self.current_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)
            self.apply_filter()
            for child in self.tree.get_children():
                if str(self.tree.item(child, 'values')[0]) == str(self.current_edit_id):
                    self.tree.selection_set(child)
                    self.tree.see(child)
                    break
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    # --- ADVANCED FIND / REPLACE / ROLLBACK ---
    
    def open_find_replace_dialog(self):
        if not self.current_folder:
            messagebox.showwarning("Warning", "Please open a project folder first.")
            return

        dialog = ttk.Toplevel(self)
        dialog.title("Find & Replace")
        dialog.geometry("500x650")
        
        # --- INPUTS ---
        ttk.Label(dialog, text="Find what:").pack(anchor=W, padx=10, pady=(10,0))
        entry_find = ttk.Entry(dialog)
        entry_find.pack(fill=X, padx=10, pady=2)
        
        ttk.Label(dialog, text="Replace with:").pack(anchor=W, padx=10, pady=(10,0))
        entry_replace = ttk.Entry(dialog)
        entry_replace.pack(fill=X, padx=10, pady=2)
        
        # --- OPTIONS ---
        options_frame = ttk.Labelframe(dialog, text="Options", padding=10)
        options_frame.pack(fill=X, padx=10, pady=10)
        
        match_case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Match Case", variable=match_case_var).pack(anchor=W)
        
        exact_match_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Match Whole Content Only", variable=exact_match_var).pack(anchor=W)
        
        regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Use Regular Expressions", variable=regex_var).pack(anchor=W)
        
        backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Create Backups (.bak)", variable=backup_var).pack(anchor=W)

        # --- SCOPE ---
        scope_frame = ttk.Labelframe(dialog, text="Scope", padding=10)
        scope_frame.pack(fill=X, padx=10, pady=5)
        
        scope_var = tk.StringVar(value="current_file")
        current_lang = "Unknown"
        if self.current_file:
            current_lang = get_target_language(self.current_file)

        ttk.Radiobutton(scope_frame, text="Current File Only", variable=scope_var, value="current_file").pack(anchor=W)
        
        rb_lang = ttk.Radiobutton(scope_frame, text=f"All '{current_lang}' Files", variable=scope_var, value="current_lang")
        rb_lang.pack(anchor=W)
        if not self.current_file: rb_lang.config(state=DISABLED)
        
        ttk.Radiobutton(scope_frame, text="Entire Project (All Files)", variable=scope_var, value="all_files").pack(anchor=W)

        # --- PROGRESS ---
        progress = ttk.Progressbar(dialog, mode='determinate', bootstyle="success-striped")
        progress.pack(fill=X, padx=10, pady=(15, 5))

        # --- WORKER LOGIC ---
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

            # Regex Prep
            pattern = None
            if mode != "rollback" and use_regex:
                try:
                    flags = 0 if match_case else re.IGNORECASE
                    pattern = re.compile(find_text, flags)
                except re.error as e:
                    messagebox.showerror("Regex Error", f"Invalid Pattern: {e}")
                    return

            total_hits = 0
            files_mod = 0
            matches_in_current_file = [] 

            progress['maximum'] = len(files_to_process)
            progress['value'] = 0

            # ROLLBACK LOGIC
            if mode == "rollback":
                restored_count = 0
                for idx, file_path in enumerate(files_to_process):
                    bak_path = Path(str(file_path) + ".bak")
                    if bak_path.exists():
                        try:
                            shutil.copy2(bak_path, file_path)
                            restored_count += 1
                        except Exception as e:
                            print(f"Restore failed: {e}")
                    progress['value'] = idx + 1
                    dialog.update_idletasks()
                
                messagebox.showinfo("Rollback Complete", f"Restored {restored_count} files from backups.")
                if self.current_file and any(str(p) == str(self.current_file) for p in files_to_process):
                    self.load_file(self.current_file)
                return

            # FIND / REPLACE LOGIC
            for idx, file_path in enumerate(files_to_process):
                try:
                    is_current = (self.current_file and str(file_path) == str(self.current_file))
                    tree = etree.parse(str(file_path))
                    file_dirty = False
                    
                    for tu in tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                        tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
                        
                        if tgt_node is not None and tgt_node.text:
                            original_text = tgt_node.text
                            new_text = original_text
                            
                            found = False
                            
                            # --- LOGIC SELECTION ---
                            if use_regex:
                                if pattern.search(original_text):
                                    found = True
                                    if mode == "replace": new_text = pattern.sub(replace_text, original_text)
                            elif exact_match:
                                # MATCH WHOLE CONTENT
                                if match_case:
                                    if original_text == find_text:
                                        found = True
                                        if mode == "replace": new_text = replace_text
                                else:
                                    if original_text.lower() == find_text.lower():
                                        found = True
                                        if mode == "replace": new_text = replace_text
                            else:
                                # SUBSTRING SEARCH
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
                                if is_current and mode == "find":
                                    matches_in_current_file.append(tu.get('id'))

                                if mode == "replace" and new_text != original_text:
                                    tgt_node.text = new_text
                                    tgt_node.set('state', 'translated')
                                    file_dirty = True

                    if file_dirty and mode == "replace":
                        files_mod += 1
                        if make_backup:
                            shutil.copy2(file_path, str(file_path) + ".bak")
                        tree.write(str(file_path), encoding="UTF-8", xml_declaration=True, pretty_print=True)

                except Exception as e:
                    print(f"Error {file_path}: {e}")
                
                progress['value'] = idx + 1
                dialog.update_idletasks()

            # RESULTS
            if mode == "replace":
                messagebox.showinfo("Complete", f"Replaced {total_hits} occurrences.\nModified {files_mod} files.")
                # Reload if current changed
                if self.current_file and any(str(p) == str(self.current_file) for p in files_to_process):
                    self.load_file(self.current_file)
            elif mode == "find":
                messagebox.showinfo("Find Results", f"Found {total_hits} matches in {len(files_to_process)} files.")
                # Highlight in grid if Current File
                if scope_var.get() == "current_file":
                    self.tree.selection_remove(self.tree.selection())
                    for child in self.tree.get_children():
                        uid = self.tree.item(child, 'values')[0]
                        if uid in matches_in_current_file:
                            self.tree.selection_add(child)
                            self.tree.see(child) 

        # --- BUTTONS ---
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=X, padx=10, pady=20)

        # Threading Helpers
        def thread_find(): threading.Thread(target=lambda: run_processing("find")).start()
        def thread_replace(): threading.Thread(target=lambda: run_processing("replace")).start()
        def thread_rollback(): threading.Thread(target=lambda: run_processing("rollback")).start()

        ttk.Button(btn_frame, text="Find All", command=thread_find, bootstyle="info-outline").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="Replace All", command=thread_replace, bootstyle="danger").pack(side=LEFT, padx=5)
        
        # Separator / Right Side
        ttk.Button(btn_frame, text="Close", command=dialog.destroy, bootstyle="secondary").pack(side=RIGHT)
        ttk.Button(btn_frame, text="Restore Backups", command=thread_rollback, bootstyle="warning-outline").pack(side=RIGHT, padx=20)
