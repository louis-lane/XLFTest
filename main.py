import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from modules.converter.gui import ConverterTab
from modules.editor.gui import EditorTab
from utils.shared import center_window
import os
from pathlib import Path
import sys

class MainApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly") 
        self.title("Localization Toolkit")
        
        # Set a default size just in case, but attempt to maximize immediately
        self.geometry("1400x900")
        try:
            self.state('zoomed')
        except:
            # Fallback for some Linux environments that handle this differently
            self.attributes('-zoomed', True)

        # --- SET ICON ---
        if getattr(sys, 'frozen', False):
            app_path = Path(sys.executable).parent
        else:
            app_path = Path(__file__).parent

        icon_path = app_path / "globe.ico"
        if icon_path.exists():
            try: self.iconbitmap(str(icon_path))
            except: pass 

        # --- HEADER ---
        header = ttk.Frame(self, padding=10)
        header.pack(fill='x')
        
        # RIGHT SIDE BUTTONS
        ttk.Button(header, text="⚙ Config", command=self.open_config, bootstyle="secondary-outline").pack(side='right', padx=5)
        ttk.Button(header, text="?", command=self.show_help, bootstyle="info-outline", width=3).pack(side='right', padx=5)

        # --- TABS ---
        self.notebook = ttk.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab1 = ConverterTab(self.notebook)
        self.notebook.add(self.tab1, text="Converter Tools")

        self.tab2 = EditorTab(self.notebook)
        self.notebook.add(self.tab2, text="XLIFF Editor")

    def open_config(self):
        config_path = Path("config.json")
        if config_path.exists(): os.startfile("config.json")

    def show_help(self):
        help_win = ttk.Toplevel(self)
        help_win.title("Keyboard Shortcuts")
        
        # Use shared center function
        center_window(help_win, 500, 600, self) 
        
        content = ttk.Frame(help_win, padding=20)
        content.pack(fill='both', expand=True)
        
        ttk.Label(content, text="Editor Shortcuts", font=("Helvetica", 14, "bold"), bootstyle="info").pack(pady=(0, 20))
        
        def add_hotkey_row(keys, desc):
            row = ttk.Frame(content)
            row.pack(fill='x', pady=5)
            ttk.Label(row, text=keys, font=("Consolas", 10, "bold"), width=15, bootstyle="inverse-secondary").pack(side='left')
            ttk.Label(row, text=desc, font=("Helvetica", 10)).pack(side='left', padx=10)

        add_hotkey_row("Ctrl + Enter", "Save & Go to Next")
        add_hotkey_row("Ctrl + Up", "Previous Segment")
        add_hotkey_row("Ctrl + Down", "Next Segment")
        ttk.Separator(content, orient='horizontal').pack(fill='x', pady=15)
        
        add_hotkey_row("Ctrl + B/I/U", "Bold / Italic / Underline")
        add_hotkey_row("Ctrl + Z/Y", "Undo / Redo")
        add_hotkey_row("Alt + S", "Replace with Source")
        add_hotkey_row("Alt + C", "Copy Source Text")
        
        ttk.Separator(content, orient='horizontal').pack(fill='x', pady=15)
        
        ttk.Label(content, text="Context Menus", font=("Helvetica", 12, "bold"), bootstyle="info").pack(pady=(10, 10))
        ttk.Label(content, text="• Right-click the Grid to bulk update status.", font=("Helvetica", 9)).pack(anchor='w', pady=2)
        ttk.Label(content, text="• Right-click text boxes for Copy/Paste.", font=("Helvetica", 9)).pack(anchor='w', pady=2)

        ttk.Button(content, text="Close", command=help_win.destroy, bootstyle="secondary").pack(side='bottom', pady=20)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
