import tkinter as tk_ttk
from tkinter import filedialog, messagebox
# --- CRITICAL IMPORT: Rename standard ttk so we can use its PanedWindow ---
from tkinter import ttk as tk_ttk 
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
        self.file_map = {} 
        
        # --- MAIN LAYOUT: 3 PANES (Sidebar | Grid | Editor) ---
        
        # 1. Main Horizontal Split: [Sidebar] | [Content Area]
        # We use tk_ttk.PanedWindow here to avoid the AttributeError
        self.main_split = tk_ttk.PanedWindow(self, orient=HORIZONTAL)
        self.main_split.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 2. LEFT SIDEBAR (Project Explorer)
        self.sidebar_frame = ttk.Frame(self.main_split)
        self.main_split.add(self.sidebar_frame, weight=1)
        
        # Sidebar Controls
        sb_controls = ttk.Frame(self.sidebar_frame)
        sb_controls.pack(fill=X, pady=(0, 5))
        ttk.Button(sb_controls, text="📂 Open Project", command=self.load_project_folder, bootstyle="info-outline").pack(fill=X)

        # File Tree
        self.file_tree = ttk.Treeview(self.sidebar_frame, show="tree headings", selectmode="browse")
        self.file_tree.heading("#0", text="Project Files")
        
        sb_scroll = ttk.Scrollbar(self.sidebar_frame, orient=VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscroll=sb_scroll.set)
        
        sb_scroll.pack(side=RIGHT, fill=Y)
        self.file_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)

        # 3. RIGHT CONTENT AREA (Holds Grid + Editor)
        self.content_area = ttk.Frame(self.main_split)
        self.main_split.add(self.content_area, weight=4)

        # --- EDITOR SPLIT: [Grid] / [Edit Panel] ---
        # Vertical split inside the right content area
        self.editor_split = tk_ttk.PanedWindow(self.content_area, orient=VERTICAL)
        self.editor_split.pack(fill=BOTH, expand=True)
        
        # Top: Grid
        self.grid_frame = ttk.Frame(self.editor_split)
        self.editor_split.add(self.grid_frame, weight=2)
        
        cols = ("id", "status", "source", "target")
        self.tree = ttk.Treeview(self.grid_frame, columns=cols, show="headings", selectmode="browse")
        
        self.tree.heading("id", text="ID")
        self.tree.heading("status", text="Status")
        self.tree.heading("source", text="Original Source")
        self.tree.heading("target", text="Translated Target")
        
        self.tree.column("id", width=60, stretch=False)
        self.tree.column("status", width=100, stretch=False)
        self.tree.column("source", width=300)
        self.tree.column("target", width=300)
        
        # Scrollbar for grid
        grid_scroll = ttk.Scrollbar(self.grid_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=grid_scroll.set)
        grid_scroll.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        # Bottom: Edit Panel
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=1)
        
        # Layout for Text Boxes
        ttk.Label(self.edit_panel, text="Original Source:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        self.txt_source = tk.Text(self.edit_panel, height=3, bg="white", fg="black", state=DISABLED)
        self.txt_source.pack(fill=X, pady=(0, 5))
        
        ttk.Label(self.edit_panel, text="Translation Target:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        self.txt_target = tk.Text(self.edit_panel, height=3, bg="white", fg="black", insertbackground="black")
        self.txt_target.pack(fill=X, pady=(0, 5))
        
        # Controls
        controls_bot = ttk.Frame(self.edit_panel)
        controls_bot.pack(fill=X)
        ttk.Button(controls_bot, text="Save Segment", command=self.save_segment, bootstyle="success").pack(side=RIGHT)

        # Internal Data State
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
        
        item = self.file_tree.item(sel[0])
        if not item['values']: return # It's a folder node/language group
        
        file_path = item['values'][0]
        self.load_file(file_path)

    def load_file(self, path):
        self.current_file = path
        try:
            self.xml_tree = etree.parse(path)
            self.data_store = []
            
            # Clear Grid
            for i in self.tree.get_children(): self.tree.delete(i)
            
            # Parse XML
            for tu in self.xml_tree.xpath('//xliff:trans-unit', namespaces=self.namespaces):
                uid = tu.get('id')
                src_node = tu.find('xliff:source', namespaces=self.namespaces)
                src = (src_node.text or "") if src_node is not None else ""
                
                tgt_node = tu.find('xliff:target', namespaces=self.namespaces)
                tgt = (tgt_node.text or "") if tgt_node is not None else ""
                status = tgt_node.get('state', 'new') if tgt_node is not None else 'new'
                
                self.data_store.append({'id': uid, 'source': src, 'target': tgt, 'status': status, 'node': tu})
                
                # Add to Grid (Flatten newlines for display)
                display_src = src.replace('\n', ' ')
                display_tgt = tgt.replace('\n', ' ')
                
                # Color Coding
                tag = status.lower().replace(" ", "_")
                self.tree.insert("", "end", values=(uid, status, display_src, display_tgt), tags=(tag,))

            # Colors
            self.tree.tag_configure('new', foreground='#ff4d4d') 
            self.tree.tag_configure('needs_review', foreground='#ffad33')
            self.tree.tag_configure('translated', foreground='#33cc33')
            self.tree.tag_configure('final', foreground='#3399ff')

        except Exception as e:
            messagebox.showerror("Error", f"Could not load file: {e}")

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

    def save_segment(self):
        if not self.current_edit_id: return
        new_txt = self.txt_target.get("1.0", "end-1c")
        
        # Update Memory
        rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
        if not rec: return
        
        rec['target'] = new_txt
        rec['status'] = 'translated' # Auto-update status on save
        
        # Update XML Node
        tgt_node = rec['node'].find('xliff:target', namespaces=self.namespaces)
        if tgt_node is None:
            tgt_node = etree.SubElement(rec['node'], f"{{{self.namespaces['xliff']}}}target")
        
        tgt_node.text = new_txt
        tgt_node.set('state', 'translated')
        
        # Save to Disk
        try:
            self.xml_tree.write(self.current_file, encoding="UTF-8", xml_declaration=True, pretty_print=True)
            # Refresh View (Keep simple for now)
            self.load_file(self.current_file)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
