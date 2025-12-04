import threading
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
from utils.shared import CONFIG, log_errors
# Import your logic functions here
from .logic import export_to_excel_with_glossary, import_and_reconstruct_with_glossary, perform_analysis, apply_deepl_translations

class ConverterTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        self.glossary_path = None
        self.build_ui()
        self.auto_load_glossary()

    def build_ui(self):
        # 1. Analysis
        lc = ttk.Labelframe(self, text="1. Analysis & Setup", padding=10, bootstyle="info")
        lc.pack(fill=X, pady=5)
        col1 = ttk.Frame(lc); col1.pack(fill=X)
        self.glossary_label = ttk.Label(col1, text="No glossary loaded", foreground="orange")
        self.glossary_label.pack(side=LEFT, padx=5)
        ttk.Button(col1, text="Load Glossary", command=self.load_glossary, bootstyle="secondary-sm").pack(side=RIGHT)
        ttk.Separator(lc, orient=HORIZONTAL).pack(fill=X, pady=10)
        ttk.Button(lc, text="Analyze Project Statistics", command=lambda: self.start_thread(self.run_analysis), bootstyle="info").pack(fill=X)

        # 2. Export
        l1 = ttk.Labelframe(self, text="2. Export for Translation", padding=10, bootstyle="primary")
        l1.pack(fill=X, pady=10)
        ttk.Button(l1, text="Create Excel Masters", command=lambda: self.start_thread(self.run_export), bootstyle="primary").pack(fill=X, pady=2)
        ttk.Button(l1, text="Apply DeepL Translations", command=lambda: self.start_thread(self.run_apply_deepl), bootstyle="primary-outline").pack(fill=X, pady=2)

        # 3. Import
        l2 = ttk.Labelframe(self, text="3. Import & Reconstruct", padding=10, bootstyle="success")
        l2.pack(fill=X, pady=5)
        ttk.Button(l2, text="Reconstruct XLIFFs", command=lambda: self.start_thread(self.run_import), bootstyle="success").pack(fill=X)
        
        # Status Bar (Local to tab or passed from main - kept simple here)
        self.progress = ttk.Progressbar(self, mode='indeterminate', bootstyle="success-striped")

    def start_thread(self, target_func):
        self.progress.pack(fill=X, pady=5)
        self.progress.start(10)
        threading.Thread(target=self.run_wrapper, args=(target_func,)).start()

    def run_wrapper(self, func):
        try: func()
        finally: self.after(0, self.stop_progress)

    def stop_progress(self):
        self.progress.stop()
        self.progress.pack_forget()

    # --- LOGIC WRAPPERS ---
    def load_glossary(self):
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if path:
            self.glossary_path = path
            self.glossary_label.config(text=f"Using: {Path(path).name}", foreground="green")

    def auto_load_glossary(self):
        if Path("glossary.xlsx").exists():
            self.glossary_path = "glossary.xlsx"
            self.glossary_label.config(text="Using: glossary.xlsx", foreground="green")

    def run_analysis(self):
        root = filedialog.askdirectory()
        if not root: return
        try:
            data = perform_analysis(Path(root), self.glossary_path)
            messagebox.showinfo("Analysis", f"Analyzed {len(data)} languages.")
            # (You can add the report window logic here)
        except Exception as e: messagebox.showerror("Error", str(e))

    def run_export(self):
        root = filedialog.askdirectory()
        if not root: return
        try:
            c, l, e = export_to_excel_with_glossary(Path(root), self.glossary_path)
            messagebox.showinfo("Result", f"Exported {c} files. Errors: {e}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def run_import(self):
        root = filedialog.askdirectory()
        if not root: return
        try:
            c, e = import_and_reconstruct_with_glossary(Path(root), self.glossary_path)
            messagebox.showinfo("Result", f"Imported {c} files. Errors: {e}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def run_apply_deepl(self):
        root = filedialog.askdirectory()
        if not root: return
        try:
            u, t, e = apply_deepl_translations(Path(root))
            messagebox.showinfo("Result", f"Updated {u}/{t} files. Errors: {len(e)}")
        except Exception as e: messagebox.showerror("Error", str(e))