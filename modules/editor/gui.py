import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk as tk_ttk 
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language, log_errors, CONFIG
import shutil
import re
import threading
import os
import pandas as pd

class EditorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_folder = None
        self.current_file = None
        self.file_map = {} 
        self.glossary_data = [] 
        
        self.sidebar_visible = True
        self.glossary_visible = True
        self.admin_mode_active = False 
        
        # --- 1. GLOBAL TOOLBAR ---
        self.toolbar = ttk.Frame(self, padding=(5, 5))
        self.toolbar.pack(side=TOP, fill=X)

        self.btn_toggle_sidebar = ttk.Button(self.toolbar, text="🗖", command=self.toggle_sidebar, bootstyle="secondary-outline", width=3)
        self.btn_toggle_sidebar.pack(side=LEFT, padx=(0, 10))
        
        ttk.Button(self.toolbar, text="➜ Source", command=self.copy_source_to_target, bootstyle="link").pack(side=LEFT)
        ttk.Button(self.toolbar, text="✖ Clear", command=self.clear_target, bootstyle="link").pack(side=LEFT)
        ttk.Separator(self.toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)

        ttk.Button(self.toolbar, text="B", command=lambda: self.insert_tag("b"), bootstyle="secondary-outline", width=2).pack(side=LEFT, padx=2)
        ttk.Button(self.toolbar, text="I", command=lambda: self.insert_tag("i"), bootstyle="secondary-outline", width=2).pack(side=LEFT, padx=2)
        ttk.Button(self.toolbar, text="U", command=lambda: self.insert_tag("u"), bootstyle="secondary-outline", width=2).pack(side=LEFT, padx=2)
        
        filter_frame = ttk.Frame(self.toolbar)
        filter_frame.pack(side=LEFT, padx=20)

        ttk.Label(filter_frame, text="Search:").pack(side=LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=LEFT, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.apply_filter)

        self.filter_var = tk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var, values=("All", "New", "Needs Review", "Translated", "Final"), state="readonly", width=12)
        self.filter_combo.pack(side=LEFT)
        self.filter_combo.bind("<<ComboboxSelected>>", self.apply_filter)

        ttk.Button(self.toolbar, text="🔍 Find", command=self.open_find_replace_dialog, bootstyle="warning-outline").pack(side=RIGHT, padx=5)
        self.btn_toggle_glossary = ttk.Button(self.toolbar, text="📖 Glossary", command=self.toggle_glossary, bootstyle="info-outline")
        self.btn_toggle_glossary.pack(side=RIGHT, padx=5)

        # --- 2. MAIN LAYOUT: 3 COLUMNS ---
        self.main_split = tk_ttk.PanedWindow(self, orient=HORIZONTAL)
        self.main_split.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # LEFT SIDEBAR
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

        # CENTER CONTENT
        self.content_area = ttk.Frame(self.main_split)
        self.main_split.add(self.content_area, weight=4)

        # --- CENTER SPLIT ---
        self.editor_split = tk_ttk.PanedWindow(self.content_area, orient=VERTICAL)
        self.editor_split.pack(fill=BOTH, expand=True)
        
        # Grid Pane
        self.grid_frame = ttk.Frame(self.editor_split)
        self.editor_split.add(self.grid_frame, weight=3)
        
        # UPDATED COLUMNS: ID -> Source -> Target -> Status (Far Right)
        cols = ("id", "source", "target", "status")
        self.tree = ttk.Treeview(self.grid_frame, columns=cols, show="headings", selectmode="extended") 
        
        self.tree.heading("id", text="ID")
        self.tree.column("id", width=50, stretch=False)
        
        self.tree.heading("source", text="Original Source")
        self.tree.column("source", width=300)
        
        self.tree.heading("target", text="Translation Target")
        self.tree.column("target", width=300)
        
        # Status Column (Narrow, Centered, Icon)
        self.tree.heading("status", text="St")
        self.tree.column("status", width=40, anchor="center", stretch=False)
        
        grid_scroll = ttk.Scrollbar(self.grid_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=grid_scroll.set)
        grid_scroll.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        
        self.create_context_menus()
        self.tree.bind("<Button-3>", self.show_grid_menu)
        self.tree.bind("<Button-2>", self.show_grid_menu) 

        # --- EDIT PANEL ---
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=2)
        
        controls_header = ttk.Frame(self.edit_panel)
        controls_header.pack(side=TOP, fill=X, pady=(0, 10))

        ttk.Label(controls_header, text="Set Status:").pack(side=LEFT, padx=(0, 5))
        self.edit_status_var = tk.StringVar()
        self.status_dropdown = ttk.Combobox(controls_header, textvariable=self.edit_status_var, values=("new", "needs-review", "translated", "final"), state="readonly", width=15)
        self.status_dropdown.pack(side=LEFT)

        btn_nav_frame = ttk.Frame(controls_header)
        btn_nav_frame.pack(side=RIGHT)
        ttk.Label(btn_nav_frame, text="[Ctrl+Enter to Save]", font=("Helvetica", 8), foreground="gray").pack(side=LEFT, padx=10)
        ttk.Button(btn_nav_frame, text="<", command=lambda: self.navigate_grid(-1), bootstyle="secondary-outline", width=3).pack(side=LEFT, padx=2)
        ttk.Button(btn_nav_frame, text=">", command=lambda: self.navigate_grid(1), bootstyle="secondary-outline", width=3).pack(side=LEFT, padx=2)
        ttk.Button(btn_nav_frame, text="Save & Next", command=self.save_and_next, bootstyle="success").pack(side=LEFT, padx=(10, 0))

        ttk.Label(self.edit_panel, text="Original Source:", font=("Helvetica", 9, "bold"), bootstyle="inverse-secondary").pack(anchor=W)
        src_frame = ttk.Frame(self.edit_panel)
        src_frame.pack(fill=BOTH, expand=True, pady=(0, 5))
        src_scroll = ttk.Scrollbar(src_frame, orient=VERTICAL)
        self.txt_source = tk.Text(src_frame, height=4, bg="white", fg="black", state=DISABLED, wrap="word", yscrollcommand=src_scroll.set)
        src_scroll.config(command=self.txt_source.yview)
        src_scroll.pack(side=RIGHT, fill=Y)
        self.txt_source.pack(side=LEFT, fill=BOTH, expand=True)
        self.txt_source.bind("<Button-3>", self.show_source_menu)
        
        ttk.Label(self.edit_panel, text="Translation Target:", font=("Helvetica", 9, "bold"), bootstyle="inverse-secondary").pack(anchor=W)
        tgt_frame = ttk.Frame(self.edit_panel)
        tgt_frame.pack(fill=BOTH, expand=True, pady=(0, 5))
        tgt_scroll = ttk.Scrollbar(tgt_frame,
