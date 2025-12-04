import ttkbootstrap as ttk
from modules.converter.gui import ConverterTab
from modules.editor.gui import EditorTab
import os
from pathlib import Path

class MainApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title("Localization Toolkit (Modular)")
        self.geometry("1000x700")

        # Header
        header = ttk.Frame(self, padding=10)
        header.pack(fill='x')
        ttk.Label(header, text="Localization Toolkit", font=("Helvetica", 16, "bold")).pack(side='left')
        ttk.Button(header, text="Config", command=self.open_config, bootstyle="outline-secondary").pack(side='right')

        # Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1
        self.tab1 = ConverterTab(self.notebook)
        self.notebook.add(self.tab1, text="Converter Tools")

        # Tab 2 (With Sidebar!)
        self.tab2 = EditorTab(self.notebook)
        self.notebook.add(self.tab2, text="XLIFF Editor")

    def open_config(self):
        if Path("config.json").exists(): os.startfile("config.json")

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()