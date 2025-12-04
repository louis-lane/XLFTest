import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import pandas as pd
from lxml import etree
from pathlib import Path
import re
from openpyxl.styles import PatternFill
from datetime import datetime
import os
import zlib
import base64
import json
import sys
import threading

# --- CONFIG & HELPER FUNCTIONS REMAIN THE SAME ---
# (I am keeping your existing helper functions here to ensure the full file works)

DEFAULT_CONFIG = {
    "folder_names": {
        "excel_export": "1_Excel_for_Translation",
        "xliff_output": "2_Translated_XLIFFs",
        "master_repo": "master_localization_files"
    },
    "protected_languages": ["English", "Spanish", "French"] # Truncated for brevity
}

def load_config():
    if getattr(sys, 'frozen', False):
        application_path = Path(sys.executable).parent
    else:
        application_path = Path(__file__).parent
    config_path = application_path / "config.json"
    current_config = DEFAULT_CONFIG.copy()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                if "folder_names" in user_config: current_config["folder_names"].update(user_config["folder_names"])
                if "protected_languages" in user_config: current_config["protected_languages"] = user_config["protected_languages"]
        except: pass
    current_config["protected_set"] = {x.lower() for x in current_config["protected_languages"]}
    return current_config

CONFIG = load_config()

# ... [Include all your existing helper functions here: get_target_language, compress_ids, etc.] ...
# ... [Include logic functions: apply_deepl_translations, export_to_excel, etc.] ...
# FOR BREVITY, I AM ASSUMING THE HELPER FUNCTIONS ARE ABOVE THIS LINE. 
# IF COPY-PASTING, ENSURE process_standard_files, log_errors_to_file, etc. ARE HERE.

def log_errors_to_file(root_path, errors):
    log_path = Path(root_path) / "error_log.txt"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n--- Log Entry: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        for error in errors: f.write(f"- {error}\n")

# --- NEW: XLIFF EDITOR LOGIC CLASS ---

class XliffEditorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        self.tree = None
        self.current_file_path = None
        self.xml_tree = None
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.data_store = [] # List of dicts to hold current file data in memory

        # --- TOP CONTROLS ---
        controls_frame = ttk.Frame(self)
        controls_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Button(controls_frame, text="📂 Open XLIFF", command=self.load_file, bootstyle="info").pack(side=LEFT, padx=(0, 10))
        ttk.Button(controls_frame, text="💾 Save Changes", command=self.save_file, bootstyle="success").pack(side=LEFT)
        
        # Filter
        ttk.Label(controls_frame, text="Filter by Status:").pack(side=LEFT, padx=(20, 5))
        self.filter_var = tk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(controls_frame, textvariable=self.filter_var, state="readonly", width=15)
        self.filter_combo['values'] = ("All", "New", "Needs Review", "Translated", "Final")
        self.filter_combo.pack(side=LEFT)
        self.filter_combo.bind("<<ComboboxSelected>>", self.apply_filter)

        # --- TABLE VIEW ---
        # Columns: ID, Status, Source, Target
        cols = ("id", "status", "source", "target")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("id", text="ID")
        self.tree.heading("status", text="Status")
        self.tree.heading("source", text="Original Source")
        self.tree.heading("target", text="Translated Target")
        
        self.tree.column("id", width=50, stretch=False)
        self.tree.column("status", width=100, stretch=False)
        self.tree.column("source", width=300)
        self.tree.column("target", width=300)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)

        # Bind Double Click to Edit
        self.tree.bind("<Double-1>", self.on_double_click)

    def load_file(self):
        filepath = filedialog.askopenfilename(title="Select XLIFF File", filetypes=[("XLIFF Files", "*.xliff"), ("All Files", "*.*")])
        if not filepath: return
        
        self.current_file_path = filepath
        try:
            self.xml_tree = etree.parse(filepath)
            self.data_store = []
            
            # Parse XML into memory list
            for trans_unit in self.xml_tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                unit_id = trans_unit.get('id')
                
                source_node = trans_unit.find('xliff:source', namespaces=self.namespaces)
                source_text = source_node.text if source_node is not None else ""
                
                target_node = trans_unit.find('xliff:target', namespaces=self.namespaces)
                if target_node is not None:
                    target_text = target_node.text or ""
                    # Map XLIFF state attribute to our UI status
                    status = target_node.get('state', 'New') 
                else:
                    target_text = ""
                    status = "New" # Default if no target exists

                self.data_store.append({
                    "id": unit_id,
                    "source": source_text,
                    "target": target_text,
                    "status": status,
                    "xml_node": trans_unit # Keep reference to XML node for easy saving
                })
            
            self.apply_filter() # Populate tree
            messagebox.showinfo("Loaded", f"Loaded {len(self.data_store)} text blocks.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not parse file: {e}")

    def apply_filter(self, event=None):
        # Clear current view
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        filter_val = self.filter_var.get().lower()
        
        for item in self.data_store:
            # Simple filter logic
            if filter_val == "all" or item['status'].lower().replace(" ", "") == filter_val.replace(" ", ""):
                # Add tag for color coding
                tag = item['status'].lower().replace(" ", "_")
                self.tree.insert("", "end", values=(item['id'], item['status'], item['source'], item['target']), tags=(tag,))

        # Optional: Color coding rows
        self.tree.tag_configure('new', foreground='red')
        self.tree.tag_configure('needs_review', foreground='orange')
        self.tree.tag_configure('translated', foreground='green')
        self.tree.tag_configure('final', foreground='blue')

    def on_double_click(self, event):
        item_id = self.tree.selection()
        if not item_id: return
        
        # Get data index
        item_values = self.tree.item(item_id, 'values')
        xliff_id = item_values[0]
        
        # Find record in data_store
        record = next((r for r in self.data_store if r['id'] == xliff_id), None)
        if record:
            self.open_edit_dialog(record)

    def open_edit_dialog(self, record):
        # Create Popup
        editor = ttk.Toplevel(self)
        editor.title(f"Edit Segment: {record['id']}")
        editor.geometry("500x400")
        
        # Source (Read Only)
        ttk.Label(editor, text="Original Source:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=5)
        source_txt = tk.Text(editor, height=4, width=50, bg="#f0f0f0")
        source_txt.insert("1.0", record['source'])
        source_txt.config(state=DISABLED)
        source_txt.pack(padx=10, fill=X)
        
        # Target (Editable)
        ttk.Label(editor, text="Translation Target:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=5)
        target_txt = tk.Text(editor, height=4, width=50)
        target_txt.insert("1.0", record['target'])
        target_txt.pack(padx=10, fill=X, expand=True)
        
        # Status Dropdown
        ttk.Label(editor, text="Status:", font=("Helvetica", 10, "bold")).pack(anchor=W, padx=10, pady=5)
        status_var = tk.StringVar(value=record['status'])
        # Use standard XLIFF 1.2 compatible states mostly
        combo = ttk.Combobox(editor, textvariable=status_var, values=("new", "needs-review", "translated", "final"), state="readonly")
        combo.pack(padx=10, fill=X)
        
        # Save Button
        def save_edit():
            new_target = target_txt.get("1.0", "end-1c")
            new_status = status_var.get()
            
            # Update Memory List
            record['target'] = new_target
            record['status'] = new_status
            
            # Update XML Node Immediately
            trans_unit = record['xml_node']
            target_node = trans_unit.find('xliff:target', namespaces=self.namespaces)
            
            # Create target node if it doesn't exist
            if target_node is None:
                target_node = etree.SubElement(trans_unit, f"{{{self.namespaces['xliff']}}}target")
            
            target_node.text = new_target
            target_node.set('state', new_status)
            
            # Refresh Tree View
            self.apply_filter()
            editor.destroy()

        ttk.Button(editor, text="Update Segment", command=save_edit, bootstyle="success").pack(pady=10)

    def save_file(self):
        if not self.current_file_path or not self.xml_tree:
            messagebox.showwarning("Warning", "No file loaded.")
            return
            
        try:
            self.xml_tree.write(self.current_file_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            messagebox.showinfo("Success", f"File saved successfully:\n{self.current_file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")

# --- UPDATED GUI CLASS ---

class FinalConverterApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title("Translation Project Tool")
        self.geometry("700x650") # Made slightly larger for the editor
        self.glossary_path = None
        
        # --- HEADER ---
        header_frame = ttk.Frame(self, padding=10)
        header_frame.pack(fill=X)
        ttk.Label(header_frame, text="Localization Toolkit", font=("Helvetica", 16, "bold")).pack(side=LEFT)
        ttk.Button(header_frame, text="⚙ Config", command=self.open_config, bootstyle="outline-secondary").pack(side=RIGHT)

        # --- NOTEBOOK (TABS) ---
        self.notebook = ttk.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # TAB 1: CONVERTER (Your original tools)
        self.tab_converter = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_converter, text="Converter Tools")
        self.build_converter_tab()

        # TAB 2: XLIFF EDITOR (The new feature)
        self.tab_editor = XliffEditorTab(self.notebook)
        self.notebook.add(self.tab_editor, text="XLIFF Editor")

        # --- STATUS BAR ---
        self.status_frame = ttk.Frame(self, padding=10)
        self.status_frame.pack(side=BOTTOM, fill=X)
        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate', bootstyle="success-striped")
        self.status_label = ttk.Label(self.status_frame, text="Ready", font=("Helvetica", 9))
        self.status_label.pack(side=LEFT)

        self.auto_load_glossary()

    def build_converter_tab(self):
        # 1. ANALYSIS
        lc = ttk.Labelframe(self.tab_converter, text="1. Analysis & Setup", padding=10, bootstyle="info")
        lc.pack(fill=X, pady=5)
        col1 = ttk.Frame(lc)
        col1.pack(fill=X)
        self.glossary_label = ttk.Label(col1, text="No glossary loaded", foreground="orange")
        self.glossary_label.pack(side=LEFT, padx=5)
        ttk.Button(col1, text="Load Glossary", command=self.load_glossary, bootstyle="secondary-sm").pack(side=RIGHT)
        ttk.Separator(lc, orient=HORIZONTAL).pack(fill=X, pady=10)
        ttk.Button(lc, text="Analyze Project Statistics", command=lambda: self.start_thread(self.run_analysis), bootstyle="info").pack(fill=X)

        # 2. EXPORT
        l1 = ttk.Labelframe(self.tab_converter, text="2. Export for Translation", padding=10, bootstyle="primary")
        l1.pack(fill=X, pady=10)
        ttk.Button(l1, text="Create Excel Masters (Step 1)", command=lambda: self.start_thread(self.run_export), bootstyle="primary").pack(fill=X, pady=2)
        ttk.Button(l1, text="Apply DeepL Translations (Step 1.5)", command=lambda: self.start_thread(self.run_apply_deepl), bootstyle="primary-outline").pack(fill=X, pady=2)

        # 3. IMPORT
        l2 = ttk.Labelframe(self.tab_converter, text="3. Import & Reconstruct", padding=10, bootstyle="success")
        l2.pack(fill=X, pady=5)
        ttk.Button(l2, text="Reconstruct XLIFFs (Step 2)", command=lambda: self.start_thread(self.run_import), bootstyle="success").pack(fill=X)

    # ... [Keep all your existing GUI helper methods: start_thread, run_wrapper, open_config, run_export, etc.] ...
    # I am omitting them here to save space, but they should be identical to the previous version.
    
    def start_thread(self, target_func):
        self.progress.pack(side=RIGHT, fill=X, expand=True, padx=10)
        self.progress.start(10)
        self.status_label.config(text="Processing... Please wait.")
        thread = threading.Thread(target=self.run_wrapper, args=(target_func,))
        thread.start()

    def run_wrapper(self, func):
        try: func() 
        finally: self.after(0, self.stop_progress)

    def stop_progress(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.status_label.config(text="Ready")

    def open_config(self):
        config_path = Path("config.json")
        if config_path.exists(): os.startfile(config_path)
        else: messagebox.showwarning("Missing", "config.json not found.")

    def run_apply_deepl(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        # Insert your apply_deepl_translations logic call here inside start_thread...
        pass # (Paste your logic from previous message)

    def run_export(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        # Insert your export logic call here...
        pass # (Paste your logic from previous message)

    def run_import(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        # Insert your import logic call here...
        pass # (Paste your logic from previous message)

    def run_analysis(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        # Insert your analysis logic call here...
        pass # (Paste your logic from previous message)
        
    def display_analysis_report(self, data):
        # Insert your display logic here...
        pass # (Paste your logic from previous message)

    def export_report_to_text(self, data):
        # Insert your export logic here...
        pass # (Paste your logic from previous message)
        
    def auto_load_glossary(self):
        default_path = Path("glossary.xlsx")
        if default_path.exists(): self.set_glossary(default_path)

    def load_glossary(self):
        filepath = filedialog.askopenfilename(title="Select Glossary Excel File", filetypes=[("Excel files", "*.xlsx")])
        if filepath: self.set_glossary(filepath)

    def set_glossary(self, path):
        self.glossary_path = path
        filename = Path(path).name
        self.glossary_label.config(text=f"Using: {filename}", foreground="green")

if __name__ == "__main__":
    app = FinalConverterApp()
    app.mainloop()
