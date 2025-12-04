import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk as tk_ttk # Standard for PanedWindow
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from utils.shared import get_target_language

class EditorTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.current_folder = None
        self.current_file = None
        self.file_map = {} # { "French": ["path/to/file1.xliff", ...], "German": ... }
        
        # --- MAIN LAYOUT: 3 PANES (Sidebar | Grid | Editor) ---
        # We split Horizontally first: [Sidebar] | [Main Content]
        self.main_split = tk_ttk.PanedWindow(self, orient=HORIZONTAL)
        self.main_split.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 1. LEFT SIDEBAR (Project Explorer)
        self.sidebar_frame = ttk.Frame(self.main_split)
        self.main_split.add(self.sidebar_frame, weight=1)
        
        # Sidebar Controls
        sb_controls = ttk.Frame(self.sidebar_frame)
        sb_controls.pack(fill=X, pady=(0, 5))
        ttk.Button(sb_controls, text="📂 Open Project Folder", command=self.load_project_folder, bootstyle="info-outline").pack(fill=X)

        # File Tree
        self.file_tree = ttk.Treeview(self.sidebar_frame, show="tree headings", selectmode="browse")
        self.file_tree.heading("#0", text="Project Files")
        sb_scroll = ttk.Scrollbar(self.sidebar_frame, orient=VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscroll=sb_scroll.set)
        
        sb_scroll.pack(side=RIGHT, fill=Y)
        self.file_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)

        # 2. RIGHT CONTENT AREA (The Editor)
        # This holds the existing Vertical Split (Grid on Top, Edit Panel on Bottom)
        self.content_area = ttk.Frame(self.main_split)
        self.main_split.add(self.content_area, weight=4)

        # --- COPY THE EXISTING EDITOR UI HERE ---
        # (I am condensing the layout code we built previously for brevity)
        
        self.editor_split = tk_ttk.PanedWindow(self.content_area, orient=VERTICAL)
        self.editor_split.pack(fill=BOTH, expand=True)
        
        # Top: Grid
        self.grid_frame = ttk.Frame(self.editor_split)
        self.editor_split.add(self.grid_frame, weight=2)
        cols = ("id", "status", "source", "target")
        self.tree = ttk.Treeview(self.grid_frame, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c.title())
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        # Bottom: Edit Panel
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10)
        self.editor_split.add(self.edit_panel, weight=1)
        
        self.txt_source = tk.Text(self.edit_panel, height=3, bg="white", fg="black", state=DISABLED)
        self.txt_source.pack(fill=X, pady=2)
        self.txt_target = tk.Text(self.edit_panel, height=3, bg="white", fg="black", insertbackground="black")
        self.txt_target.pack(fill=X, pady=2)
        ttk.Button(self.edit_panel, text="Save Segment", command=self.save_segment, bootstyle="success").pack(anchor=E)

        # Variables for State
        self.xml_tree = None
        self.namespaces = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        self.data_store = []
        self.current_edit_id = None

    def load_project_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.current_folder = Path(folder)
        
        # Clear Tree
        for i in self.file_tree.get_children(): self.file_tree.delete(i)
        self.file_map = {}

        # Scan XLIFFs
        xliffs = list(self.current_folder.glob("*.xliff"))
        if not xliffs:
            messagebox.showwarning("Empty", "No .xliff files found.")
            return

        # Group by Language (Lazy Load)
        for f in xliffs:
            lang = get_target_language(f)
            if lang not in self.file_map: self.file_map[lang] = []
            self.file_map[lang].append(f)

        # Populate Sidebar
        for lang, files in self.file_map.items():
            lang_node = self.file_tree.insert("", "end", text=lang, open=True)
            for f in files:
                self.file_tree.insert(lang_node, "end", text=f.name, values=(str(f),))

    def on_file_select(self, event):
        sel = self.file_tree.selection()
        if not sel: return
        
        # Check if it's a file (has values path)
        item = self.file_tree.item(sel[0])
        if not item['values']: return # It's a folder node
        
        file_path = item['values'][0]
        self.load_file(file_path)

    def load_file(self, path):
        self.current_file = path
        self.xml_tree = etree.parse(path)
        self.data_store = []
        # Clear Grid
        for i in self.tree.get_children(): self.tree.delete(i)
        
        # Parse XML
        for tu in self.xml_tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
            uid = tu.get('id')
            src = (tu.find('xliff:source', namespaces=self.namespaces).text or "")
            tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
            tgt = (tgt_node.text or "") if tgt_node is not None else ""
            status = tgt_node.get('state', 'new') if tgt_node is not None else 'new'
            
            self.data_store.append({'id': uid, 'source': src, 'target': tgt, 'status': status, 'node': tu})
            
            # Add to Grid (Simplified for brevity)
            self.tree.insert("", "end", values=(uid, status, src.replace('\n', ' '), tgt.replace('\n', ' ')))

    def on_row_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        uid = self.tree.item(sel[0])['values'][0]
        # Find data
        rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
        if rec:
            self.current_edit_id = uid
            self.txt_source.config(state=NORMAL); self.txt_source.delete("1.0", END); self.txt_source.insert("1.0", rec['source']); self.txt_source.config(state=DISABLED)
            self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", rec['target'])

    def save_segment(self):
        if not self.current_edit_id: return
        new_txt = self.txt_target.get("1.0", "end-1c")
        
        # Update Memory & XML
        rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
        rec['target'] = new_txt
        tgt_node = rec['node'].find('xliff:target', namespaces=self.namespaces)
        if tgt_node is None: tgt_node = etree.SubElement(rec['node'], f"{{{self.namespaces['xliff']}}}target")
        tgt_node.text = new_txt
        
        # Save to Disk
        self.xml_tree.write(self.current_file, encoding="UTF-8", xml_declaration=True)
        # Refresh Grid (Simplified)
        self.load_file(self.current_file)