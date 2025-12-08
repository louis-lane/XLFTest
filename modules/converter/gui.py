import threading
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
from utils.shared import CONFIG, log_errors
# Import logic
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
        
        col1 = ttk.Frame(lc)
        col1.pack(fill=X)
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
        
        # Status Bar
        self.progress = ttk.Progressbar(self, mode='indeterminate', bootstyle="success-striped")

    # --- THREADING HELPERS ---
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

    # --- THE ANALYSIS LOGIC ---
    def run_analysis(self):
        # 1. Ask for folder (Must be on main thread)
        root = filedialog.askdirectory(title="Select Root Folder to Analyze")
        if not root: return

        # 2. Run heavy logic in thread
        def worker():
            try:
                data = perform_analysis(Path(root), self.glossary_path)
                # 3. Show Report (Must be on main thread)
                self.after(0, lambda: self.display_analysis_report(data))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        self.start_thread(worker)

    def display_analysis_report(self, data):
        report_window = ttk.Toplevel(self)
        report_window.title("Translation Analysis Report")
        report_window.geometry("800x500")
        
        # Top Controls
        top_frame = ttk.Frame(report_window, padding=10)
        top_frame.pack(fill=X)
        ttk.Button(top_frame, text="Export to Text File", command=lambda: self.export_report_to_text(data), bootstyle="info-outline").pack(side=RIGHT)
        ttk.Label(top_frame, text="Project Breakdown", font=("Helvetica", 12, "bold")).pack(side=LEFT)

        # Table
        cols = ['Language', 'Total Words', 'Repetitions', 'Glossary Matches', 'New Words']
        tree = ttk.Treeview(report_window, columns=cols, show="headings", bootstyle="info")
        
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor='center')
        
        # Calculate Totals
        totals = {key: 0 for key in ['Total Words', 'Repetitions', 'Glossary Matches', 'New Words']}
        
        for lang, metrics in data.items():
            row = (lang, metrics['Total Words'], metrics['Repetitions'], metrics['Glossary Matches'], metrics['New Words'])
            tree.insert("", "end", values=row)
            for key in totals:
                totals[key] += metrics.get(key, 0)
        
        # Add Total Row
        tree.insert("", "end", values=()) # Spacer
        total_row = ('TOTAL (All Langs)', totals['Total Words'], totals['Repetitions'], totals['Glossary Matches'], totals['New Words'])
        tree.insert("", "end", values=total_row, tags=('totalrow',))
        tree.tag_configure('totalrow', font=('Helvetica', 10, 'bold'), background="#f0f0f0") # Light grey background for total
        
        tree.pack(expand=True, fill="both", padx=10, pady=10)

    def export_report_to_text(self, data):
        filepath = filedialog.asksaveasfilename(title="Save Report As", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
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
                    for i, key in enumerate(totals):
                        totals[key] += row_values[i+1]
                f.write(f"{'-' * sum(widths)}\n")
                total_values = ['TOTAL', totals['Total Words'], totals['Repetitions'], totals['Glossary Matches'], totals['New Words']]
                f.write("".join(str(v).ljust(w) for v, w in zip(total_values, widths)) + "\n")
            messagebox.showinfo("Success", f"Report saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def run_export(self):
        root = filedialog.askdirectory(title="Select Root Folder")
        if not root: return
        def worker():
            try:
                c, l, e = export_to_excel_with_glossary(Path(root), self.glossary_path)
                msg = f"Processed {c} files ({l} langs)."
                if e > 0: msg += f"\nErrors: {e} (See log)"
                self.after(0, lambda: messagebox.showinfo("Export Result", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self.start_thread(worker)

    def run_import(self):
        root = filedialog.askdirectory(title="Select Root Folder")
        if not root: return
        def worker():
            try:
                c, e = import_and_reconstruct_with_glossary(Path(root), self.glossary_path)
                msg = f"Reconstructed {c} files."
                if e > 0: msg += f"\nErrors: {e} (See log)"
                self.after(0, lambda: messagebox.showinfo("Import Result", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self.start_thread(worker)

    def run_apply_deepl(self):
        root = filedialog.askdirectory(title="Select Root Folder")
        if not root: return
        # Ask for DeepL folder immediately on main thread
        deepl_folder = filedialog.askdirectory(title="Select DeepL Translations Folder")
        if not deepl_folder: return

        def worker():
            try:
                # Pass both paths to logic
                u, t, e = apply_deepl_translations(Path(root), Path(deepl_folder))
                msg = f"Updated {u}/{t} files."
                if e: msg += f"\nErrors: {len(e)} (See log)"
                self.after(0, lambda: messagebox.showinfo("DeepL Result", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        self.start_thread(worker)
