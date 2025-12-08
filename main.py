import ttkbootstrap as ttk
from modules.converter.gui import ConverterTab
from modules.editor.gui import EditorTab
import os
from pathlib import Path
import sys

class MainApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly") 
        
        self.title("Localization Toolkit")
        self.geometry("1000x750")

        # --- SET ICON ---
        # Handles paths for both script and compiled exe
        if getattr(sys, 'frozen', False):
            app_path = Path(sys.executable).parent
        else:
            app_path = Path(__file__).parent

        icon_path = app_path / "globe.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass # Fail silently if icon has format issues

        # --- HEADER ---
        # Title text removed as requested
        header = ttk.Frame(self, padding=10)
        header.pack(fill='x')
        
        # Kept the Config button, moved to the far right
        ttk.Button(header, text="⚙ Config", command=self.open_config, bootstyle="secondary-outline").pack(side='right')

        # --- TABS ---
        self.notebook = ttk.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1
        self.tab1 = ConverterTab(self.notebook)
        self.notebook.add(self.tab1, text="Converter Tools")

        # Tab 2
        self.tab2 = EditorTab(self.notebook)
        self.notebook.add(self.tab2, text="XLIFF Editor")

    def open_config(self):
        config_path = Path("config.json")
        if config_path.exists(): os.startfile("config.json")

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
