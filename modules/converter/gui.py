import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
import threading
from utils.shared import center_window
# --- FIX: Import from new logic file ---
from modules.converter.logic import apply_deepl_translations, export_to_excel_with_glossary, import_and_reconstruct_with_glossary, perform_analysis

class ConverterTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        self.glossary_path = None
        self.build_ui()
        self.auto_load_glossary()

    def build_ui(self):
        lc = ttk.Labelframe(self, text="1. Analysis & Setup", padding=10, bootstyle="info")
        lc.pack(fill=X, pady=5)
        
        col1 = ttk.Frame(lc)
        col1.pack(fill=X)
        self.glossary_label = ttk.Label(col1, text="No glossary loaded", foreground="orange")
        self.glossary_label.pack(side=LEFT, padx=5)
        ttk.Button(col1, text="Load Glossary", command=self.load_glossary, bootstyle="secondary-sm").pack(side=RIGHT)
        
        ttk.Separator(lc, orient=HORIZONTAL).pack(fill=X, pady=10)
        ttk.Button(lc, text="Analyze Project Statistics", command=lambda: self.start_thread(self.run_analysis), bootstyle="info").pack(fill=X)

        l1 = ttk.Labelframe(self, text="2. Export for Translation", padding=10, bootstyle="primary")
        l1.pack(fill=X, pady=10)
        ttk.Button(l1, text="Create Excel Masters (Step 1)", command=lambda: self.start_thread(self.run_export), bootstyle="primary").pack(fill=X, pady=2)
        ttk.Button(l1, text="Apply DeepL Translations (Step 1.5)", command=lambda: self.start_thread(self.run_apply_deepl), bootstyle="primary-outline").pack(fill=X, pady=2)

        l2 = ttk.Labelframe(self, text="3. Import & Reconstruct", padding=10, bootstyle="success")
        l2.pack(fill=X, pady=5)
        ttk.Button(l2, text="Reconstruct XLIFFs (Step 2)", command=lambda: self.start_thread(self.run_import), bootstyle="success").pack(fill=X)

        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(side=BOTTOM, fill=X, pady=10)
        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate', bootstyle="success-striped")
        self.status_label = ttk.Label(self.status_frame, text="Ready", font=("Helvetica", 9))
        self.status_label.pack(side=LEFT)

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

    def run_apply_deepl(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        def worker():
            try:
                updated, total, errors = apply_deepl_translations(Path(root_dir))
                msg = f"Updated {updated}/{total} files."
                if errors: msg += " Check error_log.txt."
                messagebox.showinfo("Result", msg)
            except Exception as e: messagebox.showerror("Error", str(e))
        self.start_thread(worker)

    def run_export(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        def worker():
            try:
                fc, lc, ec = export_to_excel_with_glossary(Path(root_dir), self.glossary_path)
                messagebox.showinfo("Result", f"Processed {fc} files ({lc} langs). Errors: {ec}")
            except Exception as e: messagebox.showerror("Error", str(e))
        self.start_thread(worker)

    def run_import(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        def worker():
            try:
                pc, ec = import_and_reconstruct_with_glossary(Path(root_dir), self.glossary_path)
                messagebox.showinfo("Result", f"Reconstructed {pc} files. Errors: {ec}")
            except Exception as e: messagebox.showerror("Error", str(e))
        self.start_thread(worker)

    def run_analysis(self):
        root_dir = filedialog.askdirectory(title="Select Root Folder")
        if not root_dir: return
        def worker():
            try:
                data = perform_analysis(Path(root_dir), self.glossary_path)
                self.after(0, lambda: self.display_analysis_report(data))
            except Exception as e: messagebox.showerror("Error", str(e))
        self.start_thread(worker)

    def display_analysis_report(self, data):
        report_window = ttk.Toplevel(self)
        report_window.title("Translation Analysis Report")
        center_window(report_window, 800, 500, self) 
        
        top_frame = ttk.Frame(report_window, padding=10)
        top_frame.pack(fill=X)
        ttk.Button(top_frame, text="Export to TXT", command=lambda: self.export_report_to_text(data)).pack()
        
        cols = ['Language', 'Total Words', 'Repetitions', 'Glossary Matches', 'New Words']
        tree = ttk.Treeview(report_window, columns=cols, show="headings", bootstyle="info")
        
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor='center')
        
        totals = {key: 0 for key in ['Total Words', 'Repetitions', 'Glossary Matches', 'New Words']}
        for lang, metrics in data.items():
            row = (lang, metrics['Total Words'], metrics['Repetitions'], metrics['Glossary Matches'], metrics['New Words'])
            tree.insert("", "end", values=row)
            for key in totals: totals[key] += metrics.get(key, 0)
        
        tree.insert("", "end", values=())
        total_row = ('TOTAL', totals['Total Words'], totals['Repetitions'], totals['Glossary Matches'], totals['New Words'])
        tree.insert("", "end", values=total_row, tags=('totalrow',))
        tree.tag_configure('totalrow', font=('Helvetica', 10, 'bold'))
        tree.pack(expand=True, fill="both", padx=10, pady=10)

    def export_report_to_text(self, data):
        filepath = filedialog.asksaveasfilename(title="Save Report As", defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                headers = ['Language', 'Total Words', 'Repetitions', 'Glossary Matches', 'New Words']
                widths = [20, 15, 15, 18, 15]
                header_line = "".join(h.ljust(w) for h, w in zip(headers, widths))
                f.write(f"{header_line}\n")
                f.write(f"{'-' * sum(widths)}\n")
                totals = {key: 0 for key in ['Total Words', 'Repetitions', 'Glossary Matches', 'New Words']}
                for lang, metrics in data.items():
                    row_values = [lang, metrics.get('Total Words', 0), metrics.get('Repetitions', 0), metrics.get('Glossary Matches', 0), metrics.get('New Words', 0)]
                    f.write("".join(str(v).ljust(w) for v, w in zip(row_values, widths)) + "\n")
                    for i, key in enumerate(totals): totals[key] += row_values[i+1]
                f.write(f"{'-' * sum(widths)}\n")
                total_values = ['TOTAL', totals['Total Words'], totals['Repetitions'], totals['Glossary Matches'], totals['New Words']]
                f.write("".join(str(v).ljust(w) for v, w in zip(total_values, widths)) + "\n")
            messagebox.showinfo("Success", f"Report successfully saved to:\n{filepath}")
        except Exception as e: messagebox.showerror("Export Error", f"Could not save the report: {e}")
