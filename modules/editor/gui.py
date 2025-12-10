import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk as tk_ttk 
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from lxml import etree
from pathlib import Path
from typing import List, Optional, Any, Tuple
import re

# Internal Modules
from utils.core import get_target_language, log_errors, CONFIG
from utils.gui_utils import center_window
from modules.editor.popups import ToolTip, FindReplacePane, AddTermDialog
from modules.editor.logic import EditorLogic

class EditorTab(ttk.Frame):
    """
    Main Editor GUI Tab.
    Handles the split-pane layout, treeview grid, and text editing panels.
    """
    
    def __init__(self, parent: ttk.Notebook) -> None:
        super().__init__(parent)
        self.logic = EditorLogic()
        
        self.current_folder: Optional[Path] = None
        self.current_file: Optional[Path] = None
        self.file_map: dict = {} 
        self.xml_tree: Optional[etree._ElementTree] = None 
        self.data_store: List[dict] = []
        self.current_edit_id: Optional[str] = None
        
        # State Flags
        self.sidebar_visible: bool = True
        self.glossary_visible: bool = True
        self.find_visible: bool = False
        self.admin_mode_active: bool = False
        self.segment_dirty: bool = False
        
        # Drag & Drop State
        self.dragging_tag: bool = False
        self.drag_start_index: Optional[str] = None
        self.drag_end_index: Optional[str] = None
        self.dragged_tag_text: Optional[str] = None
        
        # Threshold & Visuals State
        self.drag_start_xy: Optional[Tuple[int, int]] = None
        self.drag_threshold_passed: bool = False
        self.original_cursor_color: Optional[str] = None
        
        self.setup_ui()
        self.setup_hotkeys()
        self.logic.load_glossary()

        # Apply initial layout
        self.update_sidebar_visibility()

    def setup_ui(self) -> None:
        # 1. GLOBAL TOOLBAR
        self.toolbar = ttk.Frame(self, padding=(5, 5))
        self.toolbar.pack(side=TOP, fill=X)

        self.btn_toggle_sidebar = ttk.Button(self.toolbar, text="🗖", command=self.toggle_sidebar, bootstyle="secondary-outline", width=3)
        self.btn_toggle_sidebar.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.btn_toggle_sidebar, "Toggle File Sidebar")
        
        self.btn_save_file = ttk.Button(self.toolbar, text="💾 Save File", command=lambda: self.save_file(silent=False), bootstyle="success")
        self.btn_save_file.pack(side=LEFT, padx=(0, 10))
        ToolTip(self.btn_save_file, "Save changes to file")

        ttk.Label(self.toolbar, text="Tag Syntax:").pack(side=LEFT, padx=(0, 5))
        self.tag_syntax_var = tk.StringVar(value="Standard XML <>")
        self.combo_syntax = ttk.Combobox(self.toolbar, textvariable=self.tag_syntax_var, values=("Standard XML <>", "Gomo []"), state="readonly", width=15)
        self.combo_syntax.pack(side=LEFT, padx=(0, 15))
        self.combo_syntax.bind("<<ComboboxSelected>>", self.on_syntax_change)
        ToolTip(self.combo_syntax, "Select tag format")

        btn_copy = ttk.Button(self.toolbar, text="➜ Source", command=self.copy_source_to_target, bootstyle="link")
        btn_copy.pack(side=LEFT)
        btn_clear = ttk.Button(self.toolbar, text="✖ Clear", command=self.clear_target, bootstyle="link")
        btn_clear.pack(side=LEFT)
        
        ttk.Separator(self.toolbar, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)

        # Filter Area
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

        # Right Sidebar Toggles
        self.btn_toggle_find = ttk.Button(self.toolbar, text="🔍 Find", command=self.toggle_find_replace, bootstyle="warning-outline")
        self.btn_toggle_find.pack(side=RIGHT, padx=5)
        self.btn_toggle_glossary = ttk.Button(self.toolbar, text="📖 Glossary", command=self.toggle_glossary, bootstyle="info-outline")
        self.btn_toggle_glossary.pack(side=RIGHT, padx=5)

        # 2. PANED WINDOWS
        self.main_split = tk_ttk.PanedWindow(self, orient=HORIZONTAL)
        self.main_split.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # Left Sidebar
        self.sidebar_frame = ttk.Frame(self.main_split)
        self.main_split.add(self.sidebar_frame, weight=1)
        ttk.Button(self.sidebar_frame, text="📂 Open Project", command=self.load_project_folder, bootstyle="info-outline").pack(fill=X, pady=(0, 5))
        self.file_tree = ttk.Treeview(self.sidebar_frame, show="tree headings", selectmode="browse")
        self.file_tree.heading("#0", text="Project Files")
        self.file_tree.pack(fill=BOTH, expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)

        # Center Content
        self.content_area = ttk.Frame(self.main_split)
        self.main_split.add(self.content_area, weight=4)
        
        self.editor_split = tk_ttk.PanedWindow(self.content_area, orient=VERTICAL)
        self.editor_split.pack(fill=BOTH, expand=True)
        
        # Grid
        self.grid_frame = ttk.Frame(self.editor_split)
        self.editor_split.add(self.grid_frame, weight=3)
        cols = ("id", "source", "target", "status")
        self.tree = ttk.Treeview(self.grid_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("id", text="ID"); self.tree.column("id", width=50)
        self.tree.heading("source", text="Original Source"); self.tree.column("source", width=300)
        self.tree.heading("target", text="Translation Target"); self.tree.column("target", width=300)
        self.tree.heading("status", text="St"); self.tree.column("status", width=40, anchor="center")
        self.tree.tag_configure('new', foreground='#ff4d4d')
        self.tree.tag_configure('needs_review', foreground='#ffad33')
        self.tree.tag_configure('translated', foreground='#33cc33')
        self.tree.tag_configure('final', foreground='#3399ff')
        
        grid_scroll = ttk.Scrollbar(self.grid_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=grid_scroll.set)
        grid_scroll.pack(side=RIGHT, fill=Y)
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        
        # Context Menus
        self.create_context_menus()
        self.tree.bind("<Button-3>", self.show_grid_menu)

        # Edit Panel
        self.edit_panel = ttk.Labelframe(self.editor_split, text="Edit Segment", padding=10, bootstyle="secondary")
        self.editor_split.add(self.edit_panel, weight=2)
        
        h = ttk.Frame(self.edit_panel); h.pack(side=TOP, fill=X, pady=(0, 10))
        ttk.Label(h, text="Status:").pack(side=LEFT)
        self.edit_status_var = tk.StringVar()
        self.status_dropdown = ttk.Combobox(h, textvariable=self.edit_status_var, values=("new", "needs-review", "translated", "final"), state="readonly", width=12)
        self.status_dropdown.pack(side=LEFT, padx=5)
        
        ttk.Button(h, text="B", width=2, command=lambda: self.format_text("b"), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        ttk.Button(h, text="I", width=2, command=lambda: self.format_text("i"), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        ttk.Button(h, text="U", width=2, command=lambda: self.format_text("u"), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        
        # Grid Popup Button
        self.btn_tags = ttk.Button(h, text="</>", bootstyle="secondary-outline", command=self.show_tag_grid_popup)
        self.btn_tags.pack(side=LEFT, padx=(5, 1))
        ToolTip(self.btn_tags, "Insert Smart Tag")

        ttk.Separator(h, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=5)
        ttk.Button(h, text="↶", width=2, command=lambda: self.txt_target.edit_undo(), bootstyle="secondary-outline").pack(side=LEFT, padx=1)
        ttk.Button(h, text="↷", width=2, command=lambda: self.txt_target.edit_redo(), bootstyle="secondary-outline").pack(side=LEFT, padx=1)

        f_right = ttk.Frame(h); f_right.pack(side=RIGHT)
        ttk.Label(f_right, text="[Ctrl+Enter to Save]", font=("Helvetica", 8), foreground="gray").pack(side=LEFT, padx=10)
        ttk.Button(f_right, text="<", width=3, command=lambda: self.navigate_grid(-1), bootstyle="secondary-outline").pack(side=LEFT)
        ttk.Button(f_right, text=">", width=3, command=lambda: self.navigate_grid(1), bootstyle="secondary-outline").pack(side=LEFT, padx=2)
        
        ttk.Button(f_right, text="Save & Next", command=self.save_and_next, bootstyle="success").pack(side=LEFT, padx=5)

        ttk.Label(self.edit_panel, text="Source:", bootstyle="inverse-secondary").pack(anchor=W)
        self.txt_source = tk.Text(self.edit_panel, height=4, state=DISABLED, wrap="word")
        self.txt_source.pack(fill=BOTH, expand=True, pady=(0, 5))
        self.txt_source.bind("<Button-3>", self.show_source_menu)
        
        ttk.Label(self.edit_panel, text="Target:", bootstyle="inverse-secondary").pack(anchor=W)
        self.txt_target = tk.Text(self.edit_panel, height=4, undo=True, maxundo=50, wrap="word")
        self.txt_target.pack(fill=BOTH, expand=True)
        # NEW: Configure Tag Style
        self.txt_target.tag_configure("tag_highlight", foreground="#00bfff") # Same blue as cursor
        
        self.txt_target.bind("<Button-3>", self.show_target_menu)
        
        # --- DRAG AND DROP & SELECTION BINDINGS ---
        self.txt_target.bind("<Button-1>", self.on_target_click)
        self.txt_target.bind("<B1-Motion>", self.on_target_drag)
        self.txt_target.bind("<ButtonRelease-1>", self.on_target_release)
        self.txt_target.bind("<Double-Button-1>", self.on_target_double_click)
        self.txt_target.bind("<KeyRelease>", self.on_text_modified)

        # 3. RIGHT SIDEBAR
        self.right_sidebar = ttk.Frame(self.main_split)
        self.main_split.add(self.right_sidebar, weight=1)
        
        self.glossary_frame = ttk.Labelframe(self.right_sidebar, text="Glossary", padding=5, bootstyle="info")
        
        self.gloss_tree = ttk.Treeview(self.glossary_frame, columns=("term", "trans"), show="headings")
        self.gloss_tree.heading("term", text="Term"); self.gloss_tree.heading("trans", text="Trans")
        self.gloss_tree.pack(fill=BOTH, expand=True)
        self.gloss_tree.bind("<Double-1>", self.insert_glossary_term)
        
        self.gloss_ctrl = ttk.Frame(self.glossary_frame); self.gloss_ctrl.pack(side=BOTTOM, fill=X)
        self.btn_add_term = ttk.Button(self.gloss_ctrl, text="+ Add", command=self.open_add_term_dialog, bootstyle="info-outline-sm")
        self.btn_add_term.pack(side=RIGHT)

        self.find_pane = FindReplacePane(self.right_sidebar, self)

    # --- SYNTAX HIGHLIGHTING (New) ---
    def highlight_syntax(self) -> None:
        """Applies blue highlighting to all tags in the target text."""
        self.txt_target.tag_remove("tag_highlight", "1.0", END)
        
        mode = self.tag_syntax_var.get()
        pattern = self.logic.get_tag_pattern(mode)
        
        text_content = self.txt_target.get("1.0", "end-1c")
        
        for match in re.finditer(pattern, text_content):
            start_index = f"1.0 + {match.start()} chars"
            end_index = f"1.0 + {match.end()} chars"
            self.txt_target.tag_add("tag_highlight", start_index, end_index)

    # --- DRAG & DROP LOGIC ---
    def get_tag_at_index(self, index: str) -> Optional[Tuple[str, str, str]]:
        """Checks if the given index falls within a tag. Returns (text, start, end)."""
        try:
            line_num = index.split('.')[0]
            line_text = self.txt_target.get(f"{line_num}.0", f"{line_num}.end")
            col = int(index.split('.')[1])
            
            mode = self.tag_syntax_var.get()
            pattern = self.logic.get_tag_pattern(mode)
            
            for match in re.finditer(pattern, line_text):
                start, end = match.span()
                if start <= col < end:
                    return (match.group(), f"{line_num}.{start}", f"{line_num}.{end}")
            return None
        except Exception:
            return None

    def on_target_click(self, event: Any) -> Any:
        # Check if we clicked on a tag
        index = self.txt_target.index(f"@{event.x},{event.y}")
        tag_info = self.get_tag_at_index(index)
        
        if tag_info:
            self.dragging_tag = True
            self.dragged_tag_text, self.drag_start_index, self.drag_end_index = tag_info
            
            # Record start pos for Threshold Check
            self.drag_start_xy = (event.x, event.y)
            self.drag_threshold_passed = False
            
            # Select the tag visually
            self.txt_target.tag_remove("sel", "1.0", END)
            self.txt_target.tag_add("sel", self.drag_start_index, self.drag_end_index)
            
            # Prevent default cursor placement so we can drag
            return "break"
        
        self.dragging_tag = False
        return None

    def on_target_drag(self, event: Any) -> Any:
        if self.dragging_tag:
            # 1. Check Threshold (5 pixels)
            if not self.drag_threshold_passed:
                start_x, start_y = self.drag_start_xy
                dist = ((event.x - start_x)**2 + (event.y - start_y)**2)**0.5
                if dist < 5:
                    return "break" # Block drag until moved enough
                self.drag_threshold_passed = True
                
                # VISUAL FEEDBACK: Change cursor to Blue
                self.original_cursor_color = self.txt_target.cget('insertbackground')
                self.txt_target.config(insertbackground='#00bfff', insertwidth=3)

            # 2. Handle Movement Logic
            x, y = event.x, event.y
            raw_index = self.txt_target.index(f"@{x},{y}")
            
            # Check for Shift key (bit 0)
            is_shift_held = (event.state & 0x0001) != 0
            
            if is_shift_held:
                # Character granularity
                target_index = raw_index
            else:
                # Word granularity (default)
                target_index = self.txt_target.index(f"{raw_index} wordstart")
                
            # Move insertion cursor to show where it will land
            self.txt_target.mark_set("insert", target_index)
            
            # Ensure the selection stays on the tag we are dragging
            if self.drag_start_index and self.drag_end_index:
                self.txt_target.tag_remove("sel", "1.0", END)
                self.txt_target.tag_add("sel", self.drag_start_index, self.drag_end_index)
            
            return "break"
        return None

    def on_target_release(self, event: Any) -> Any:
        # RESET VISUALS: Always restore cursor
        if self.original_cursor_color:
            self.txt_target.config(insertbackground=self.original_cursor_color, insertwidth=1)
            self.original_cursor_color = None

        if self.dragging_tag:
            # If we never passed the threshold, treat it as a click/selection only
            if not self.drag_threshold_passed:
                self.dragging_tag = False
                self.drag_start_xy = None
                return "break"

            drop_index = self.txt_target.index("insert") 
            
            # Prevent dropping inside itself
            if self.txt_target.compare(drop_index, ">=", self.drag_start_index) and \
               self.txt_target.compare(drop_index, "<=", self.drag_end_index):
                self.dragging_tag = False
                return "break"

            # Perform Move
            self.txt_target.delete(self.drag_start_index, self.drag_end_index)
            self.txt_target.insert(drop_index, self.dragged_tag_text)
            
            self.segment_dirty = True
            self.dragging_tag = False
            
            # Re-apply syntax highlighting immediately after move
            self.highlight_syntax()
            
            # Clear selection
            self.txt_target.tag_remove("sel", "1.0", END)
            return "break"
        return None

    # --- DOUBLE CLICK SELECTION ---
    def on_target_double_click(self, event: Any) -> Any:
        """Restores the ability to select text between paired tags."""
        try:
            index = self.txt_target.index(f"@{event.x},{event.y}")
            tag_info = self.get_tag_at_index(index)
            
            if not tag_info: return None # Let default behavior handle non-tag double clicks
            
            clicked_tag, t_start, t_end = tag_info
            
            # Determine if it's an opening or closing tag
            mode = self.tag_syntax_var.get()
            is_closing = clicked_tag.startswith("[/") or clicked_tag.startswith("</")
            
            # Extract core tag name
            clean_content = re.sub(r"[\[\]<>/]", "", clicked_tag).split(" ")[0]
            
            open_char = '[' if mode == "Gomo []" else '<'
            close_char = ']' if mode == "Gomo []" else '>'
            
            start_sel = None
            end_sel = None
            
            if not is_closing:
                # Find matching closer forward
                closer = f"{open_char}/{clean_content}{close_char}"
                search_res = self.txt_target.search(closer, t_end, stopindex=END)
                if search_res:
                    start_sel = t_start
                    end_sel = f"{search_res} + {len(closer)}c"
            else:
                # Find matching opener backward
                opener = f"{open_char}{clean_content}" 
                search_res = self.txt_target.search(opener, t_start, stopindex="1.0", backwards=True)
                if search_res:
                    start_sel = search_res
                    end_sel = t_end

            if start_sel and end_sel:
                self.txt_target.tag_remove("sel", "1.0", END)
                self.txt_target.tag_add("sel", start_sel, end_sel)
                return "break" # Stop default double-click selection
                
        except Exception:
            pass
        return None

    # --- LAYOUT LOGIC ---
    def toggle_sidebar(self) -> None:
        if self.sidebar_visible:
            self.main_split.forget(self.sidebar_frame)
            self.btn_toggle_sidebar.configure(bootstyle="secondary") 
        else:
            self.main_split.insert(0, self.sidebar_frame, weight=1)
            self.btn_toggle_sidebar.configure(bootstyle="secondary-outline")
        self.sidebar_visible = not self.sidebar_visible

    def update_sidebar_visibility(self) -> None:
        if not self.glossary_visible and not self.find_visible:
            try: self.main_split.forget(self.right_sidebar)
            except: pass
        else:
            if str(self.right_sidebar) not in self.main_split.panes():
                self.main_split.add(self.right_sidebar, weight=1)

        self.glossary_frame.pack_forget()
        self.find_pane.pack_forget()

        if self.glossary_visible and self.find_visible:
            self.glossary_frame.pack(side=TOP, fill=BOTH, expand=True, padx=5, pady=5)
            self.find_pane.pack(side=BOTTOM, fill=X, padx=5, pady=5)
        elif self.glossary_visible:
            self.glossary_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        elif self.find_visible:
            self.find_pane.pack(fill=BOTH, expand=True, padx=5, pady=5)
    
    def toggle_glossary(self) -> None:
        self.glossary_visible = not self.glossary_visible
        if self.glossary_visible:
            self.btn_toggle_glossary.configure(bootstyle="info-outline")
        else:
            self.btn_toggle_glossary.configure(bootstyle="info")
        self.update_sidebar_visibility()

    def toggle_find_replace(self) -> None:
        self.find_visible = not self.find_visible
        if self.find_visible:
            self.btn_toggle_find.configure(bootstyle="warning")
        else:
            self.btn_toggle_find.configure(bootstyle="warning-outline")
        self.update_sidebar_visibility()

    def open_find_replace_dialog(self) -> None:
        if not self.find_visible: self.toggle_find_replace()

    # --- POPUP LOGIC ---
    def open_add_term_dialog(self) -> None:
        AddTermDialog(self, self.logic)
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.refresh_glossary_view(rec['source'])

    # --- TAG LOGIC ---
    def on_syntax_change(self, event: Any) -> None:
        # Trigger highlighting when syntax mode changes
        if self.current_edit_id:
            self.highlight_syntax()

    def show_tag_grid_popup(self) -> None:
        """Creates a compact 4-column grid popup for inserting tags."""
        # 1. Get Data
        syntax = self.tag_syntax_var.get()
        source_text = ""
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: source_text = rec['source']
            
        tags = self.logic.get_tag_suggestions(source_text, syntax)
        standard = tags['standard']
        context = tags['context']
        
        if not standard and not context:
            messagebox.showinfo("Tags", "No tags available for this segment.")
            return

        # 2. Create Popup
        popup = tk.Toplevel(self)
        popup.overrideredirect(True) # Removes window border
        popup.attributes('-topmost', True)
        
        # Position logic (Anchored to Button)
        x = self.btn_tags.winfo_rootx()
        y = self.btn_tags.winfo_rooty() + self.btn_tags.winfo_height()
        popup.geometry(f"+{x}+{y}")
        
        # Close when clicking away
        def close_popup(e):
            if str(e.widget) != str(popup): popup.destroy()
        popup.bind("<FocusOut>", lambda e: popup.destroy())
        popup.focus_set()

        # 3. Build Grid
        frame = ttk.Frame(popup, padding=5, bootstyle="dark")
        frame.pack(fill=BOTH, expand=True)
        
        def add_tag_btn(parent, tag_text, r, c):
            btn = ttk.Button(parent, text=tag_text, command=lambda t=tag_text: [self.insert_smart_tag(t), popup.destroy()], bootstyle="secondary-outline-sm")
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")

        current_row = 0
        
        # Standard Tags
        if standard:
            ttk.Label(frame, text="Standard", font=("Helvetica", 8, "bold"), bootstyle="inverse-dark").grid(row=current_row, column=0, columnspan=4, sticky="w", pady=(0, 2))
            current_row += 1
            for i, tag in enumerate(standard):
                add_tag_btn(frame, tag, current_row + (i // 4), i % 4)
            current_row += (len(standard) // 4) + 1

        # Context Tags
        if context:
            if standard: 
                ttk.Separator(frame, orient=HORIZONTAL).grid(row=current_row, column=0, columnspan=4, sticky="ew", pady=5)
                current_row += 1
            
            ttk.Label(frame, text="From Context", font=("Helvetica", 8, "bold"), bootstyle="inverse-dark").grid(row=current_row, column=0, columnspan=4, sticky="w", pady=(0, 2))
            current_row += 1
            for i, tag in enumerate(context):
                add_tag_btn(frame, tag, current_row + (i // 4), i % 4)

    def insert_smart_tag(self, opener: str) -> None:
        closer = ""
        syntax = self.tag_syntax_var.get()
        if syntax == "Gomo []":
            content = opener.strip("[]"); tag_name = content.split(" ")[0]; closer = f"[/{tag_name}]"
        else:
            content = opener.strip("<>"); tag_name = content.split(" ")[0]; closer = f"</{tag_name}>"
        try:
            if not self.txt_target.tag_ranges("sel"):
                self.txt_target.insert(tk.INSERT, f"{opener}{closer}")
                self.txt_target.mark_set(tk.INSERT, f"insert - {len(closer)}c")
            else:
                sel_first = self.txt_target.index("sel.first"); sel_last = self.txt_target.index("sel.last")
                text = self.txt_target.get(sel_first, sel_last)
                if text.startswith(opener) and text.endswith(closer):
                    inner = text[len(opener):-len(closer)]
                    self.txt_target.delete(sel_first, sel_last); self.txt_target.insert(sel_first, inner)
                    self.txt_target.tag_add("sel", sel_first, f"{sel_first} + {len(inner)}c")
                else:
                    self.txt_target.delete(sel_first, sel_last); self.txt_target.insert(sel_first, f"{opener}{text}{closer}")
            
            # Apply highlighting after insert
            self.highlight_syntax()
            
        except: pass
        self.txt_target.focus_set()

    def format_text(self, tag_type: str) -> None:
        syntax = self.tag_syntax_var.get()
        opener = f"[{tag_type}]" if syntax == "Gomo []" else f"<{tag_type}>"
        self.insert_smart_tag(opener)

    # --- UNSAVED CHANGES LOGIC ---
    def on_text_modified(self, event: Any) -> None:
        if event.keysym in ("Up", "Down", "Left", "Right", "Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"):
            return
        self.segment_dirty = True
        # Re-apply highlighting as user types
        self.highlight_syntax()

    def check_unsaved_changes(self) -> bool:
        if self.segment_dirty:
            resp = messagebox.askyesnocancel("Unsaved Changes", "You have edited this segment but not saved.\nSave before continuing?")
            if resp is None: return False
            if resp: self.save_segment()
            else: self.segment_dirty = False
        return True

    # --- DATA & IO METHODS ---
    def load_project_folder(self) -> None:
        folder = filedialog.askdirectory()
        if not folder: return
        self.current_folder = Path(folder)
        for i in self.file_tree.get_children(): self.file_tree.delete(i)
        self.file_map = {}
        xliffs = list(self.current_folder.glob("*.xliff"))
        for f in xliffs:
            lang = get_target_language(f)
            if lang not in self.file_map: self.file_map[lang] = []
            self.file_map[lang].append(f)
        for lang, files in self.file_map.items():
            node = self.file_tree.insert("", "end", text=lang, open=True)
            for f in files: self.file_tree.insert(node, "end", text=f.name, values=(str(f),))

    def on_file_select(self, event: Any) -> None:
        if not self.check_unsaved_changes(): return 
        sel = self.file_tree.selection()
        if not sel: return
        item = self.file_tree.item(sel[0])
        if not item['values']: return 
        self.load_file(Path(item['values'][0]))

    def load_file(self, path: Path) -> None:
        self.current_file = path
        try:
            self.xml_tree, self.data_store = self.logic.load_xliff(path)
            self.apply_filter()
            self.segment_dirty = False 
        except Exception as e: messagebox.showerror("Error", str(e))
    
    def request_file_switch(self, target_path: Path) -> bool:
        if not self.check_unsaved_changes(): return False
        self.load_file(target_path)
        self.select_file_in_tree(target_path)
        return True

    def select_file_in_tree(self, file_path: Path) -> None:
        target_str = str(file_path)
        for lang_node in self.file_tree.get_children():
            for file_node in self.file_tree.get_children(lang_node):
                values = self.file_tree.item(file_node, 'values')
                if values and values[0] == target_str:
                    self.file_tree.selection_set(file_node)
                    self.file_tree.see(file_node)
                    return

    def save_file(self, silent: bool = False) -> None:
        if not self.current_file or not self.xml_tree:
            if not silent: messagebox.showwarning("Warning", "No file loaded.")
            return
        try:
            self.logic.save_xliff(self.xml_tree, self.current_file)
            if not silent: messagebox.showinfo("Success", f"File saved: {Path(self.current_file).name}")
        except Exception as e: messagebox.showerror("Error", f"Failed to save: {e}")

    def on_row_select(self, event: Any) -> None:
        if not self.check_unsaved_changes(): return
        sel = self.tree.selection()
        if not sel: return
        uid = self.tree.item(sel[0])['values'][0]
        rec = next((x for x in self.data_store if str(x['id']) == str(uid)), None)
        if rec:
            self.current_edit_id = uid
            self.txt_source.config(state=NORMAL); self.txt_source.delete("1.0", END); self.txt_source.insert("1.0", rec['source']); self.txt_source.config(state=DISABLED)
            self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", rec['target'])
            self.edit_status_var.set(rec['status'])
            self.refresh_glossary_view(rec['source'])
            self.segment_dirty = False 
            
            # Apply highlighting to loaded text
            self.highlight_syntax()

    def refresh_glossary_view(self, source_text: str) -> None:
        for i in self.gloss_tree.get_children(): self.gloss_tree.delete(i)
        matches = self.logic.find_glossary_matches(source_text, self.current_file)
        for term, trans in matches: self.gloss_tree.insert("", "end", values=(term, trans))

    def insert_glossary_term(self, event: Any) -> None:
        sel = self.gloss_tree.selection()
        if not sel: return
        translation = self.gloss_tree.item(sel[0], 'values')[1]
        self.txt_target.focus_set()
        try: self.txt_target.delete("sel.first", "sel.last")
        except: pass
        self.txt_target.insert(tk.INSERT, translation)
        self.segment_dirty = True
        self.highlight_syntax()

    def save_segment(self) -> None:
        if not self.current_edit_id: return
        new_target = self.txt_target.get("1.0", "end-1c")
        new_status = self.edit_status_var.get()
        rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
        if rec:
            rec['target'] = new_target
            rec['status'] = new_status
            status_map = {'new': '🔴', 'needs-review': '🟠', 'translated': '🟢', 'final': '☑️'}
            icon = status_map.get(str(new_status).lower(), '❓')
            tag = str(new_status).lower().replace(" ", "_").replace("-", "_")
            for child in self.tree.get_children():
                if str(self.tree.item(child, 'values')[0]) == str(self.current_edit_id):
                    self.tree.item(child, values=(rec['id'], rec['source'].replace('\n', ' '), new_target.replace('\n', ' '), icon), tags=(tag,))
                    break
            if 'node' in rec:
                tu = rec['node']
                ns = self.logic.namespaces
                tgt_node = tu.find('xliff:target', namespaces=ns)
                if tgt_node is None: tgt_node = etree.SubElement(tu, f"{{{ns['xliff']}}}target")
                tgt_node.text = new_target
                tgt_node.set('state', new_status)
        self.save_file(silent=True)
        self.segment_dirty = False

    def save_and_next(self) -> None:
        self.save_segment()
        self.navigate_grid(1)

    def navigate_grid(self, direction: int) -> None:
        sel = self.tree.selection(); items = self.tree.get_children()
        if not items: return
        new_idx = 0
        if sel: new_idx = max(0, min(len(items)-1, items.index(sel[0]) + direction))
        self.tree.selection_set(items[new_idx]); self.tree.see(items[new_idx]); self.on_row_select(None)

    def setup_hotkeys(self) -> None:
        self.txt_target.bind("<Control-Return>", lambda e: self.save_and_next() or "break")
        self.txt_target.bind("<Control-b>", lambda e: self.format_text("b") or "break")
        self.txt_target.bind("<Control-i>", lambda e: self.format_text("i") or "break")
        self.txt_target.bind("<Control-u>", lambda e: self.format_text("u") or "break")
        self.bind_all("<Control-Q>", self.toggle_admin_mode)
        self.bind_all("<Control-s>", lambda e: self.save_file())
        
    def toggle_admin_mode(self, event: Any = None) -> None:
        self.admin_mode_active = not self.admin_mode_active
        print(f"Admin mode: {self.admin_mode_active}")

    # --- BULK ACTIONS ---
    def create_context_menus(self) -> None:
        self.menu_grid = tk.Menu(self, tearoff=0)
        self.menu_grid.add_command(label="↺ Revert to Source", command=self.bulk_revert_to_source)
        self.menu_grid.add_separator()
        self.menu_grid.add_command(label="📄 Copy Source Text", command=lambda: self.copy_selection_to_clipboard("source"))
        self.menu_grid.add_command(label="📄 Copy Target Text", command=lambda: self.copy_selection_to_clipboard("target"))
        self.menu_grid.add_separator()
        
        self.status_menu = tk.Menu(self.menu_grid, tearoff=0)
        self.menu_grid.add_cascade(label="Set Status", menu=self.status_menu)
        self.status_menu.add_command(label="🔴 New", command=lambda: self.bulk_set_status("new"))
        self.status_menu.add_command(label="🟠 Needs Review", command=lambda: self.bulk_set_status("needs-review"))
        self.status_menu.add_command(label="🟢 Translated", command=lambda: self.bulk_set_status("translated"))
        self.status_menu.add_command(label="☑️ Final", command=lambda: self.bulk_set_status("final"))
        
        self.menu_source = tk.Menu(self, tearoff=0)
        self.menu_source.add_command(label="Copy", command=lambda: self.text_copy(self.txt_source))
        self.menu_target = tk.Menu(self, tearoff=0)
        self.menu_target.add_command(label="Copy", command=lambda: self.text_copy(self.txt_target))
        self.menu_target.add_command(label="Paste", command=lambda: self.text_paste(self.txt_target))

    def show_grid_menu(self, event: Any) -> None:
        if self.tree.identify_row(event.y): self.menu_grid.post(event.x_root, event.y_root)
    def show_source_menu(self, event: Any) -> None: self.menu_source.post(event.x_root, event.y_root)
    def show_target_menu(self, event: Any) -> None: self.menu_target.post(event.x_root, event.y_root)
    
    def copy_source_to_target(self) -> None:
        if self.current_edit_id:
            rec = next((x for x in self.data_store if str(x['id']) == str(self.current_edit_id)), None)
            if rec: self.txt_target.delete("1.0", END); self.txt_target.insert("1.0", rec['source']); self.segment_dirty = True
            
    def get_selected_ids(self) -> List[str]:
        return [self.tree.item(i)['values'][0] for i in self.tree.selection()]

    def bulk_set_status(self, new_status: str) -> None:
        ids = self.get_selected_ids()
        if not ids: return
        status_map = {'new': '🔴', 'needs-review': '🟠', 'translated': '🟢', 'final': '☑️'}
        icon = status_map.get(new_status, '❓')
        tag = new_status.replace("-", "_")
        count = 0
        for uid in ids:
            rec = next((r for r in self.data_store if str(r['id']) == str(uid)), None)
            if rec:
                rec['status'] = new_status
                if 'node' in rec:
                    tgt_node = rec['node'].find('xliff:target', namespaces=self.logic.namespaces)
                    if tgt_node is None:
                        tgt_node = etree.SubElement(rec['node'], f"{{{self.logic.namespaces['xliff']}}}target")
                        tgt_node.text = rec['target']
                    tgt_node.set('state', new_status)
                for child in self.tree.get_children():
                    if str(self.tree.item(child, 'values')[0]) == str(uid):
                        vals = list(self.tree.item(child, 'values'))
                        vals[3] = icon 
                        self.tree.item(child, values=vals, tags=(tag,))
                        break
                count += 1
        if count > 0:
            self.save_file(silent=True)
            if self.current_edit_id in ids: self.edit_status_var.set(new_status)

    def bulk_revert_to_source(self) -> None:
        ids = self.get_selected_ids()
        if not ids: return
        if not messagebox.askyesno("Confirm Revert", f"Are you sure you want to revert {len(ids)} segments?"): return
        count = 0
        for uid in ids:
            rec = next((r for r in self.data_store if str(r['id']) == str(uid)), None)
            if rec:
                new_text = rec['source']
                rec['target'] = new_text
                if 'node' in rec:
                    tgt_node = rec['node'].find('xliff:target', namespaces=self.logic.namespaces)
                    if tgt_node is None: tgt_node = etree.SubElement(rec['node'], f"{{{self.logic.namespaces['xliff']}}}target")
                    tgt_node.text = new_text
                for child in self.tree.get_children():
                    if str(self.tree.item(child, 'values')[0]) == str(uid):
                        vals = list(self.tree.item(child, 'values'))
                        vals[2] = new_text.replace('\n', ' ')
                        self.tree.item(child, values=vals)
                        break
                count += 1
        if count > 0:
            self.save_file(silent=True)
            if self.current_edit_id in ids:
                self.txt_target.delete("1.0", END)
                self.txt_target.insert("1.0", self.txt_source.get("1.0", END).strip())

    def copy_selection_to_clipboard(self, mode: str = "source") -> None:
        ids = self.get_selected_ids()
        text_lines = []
        for uid in ids:
            rec = next((r for r in self.data_store if str(r['id']) == str(uid)), None)
            if rec:
                val = rec['source'] if mode == "source" else rec['target']
                if val: text_lines.append(val)
        if text_lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(text_lines))

    def clear_target(self) -> None: self.txt_target.delete("1.0", END); self.segment_dirty = True
    def text_copy(self, w: tk.Text) -> None: 
        try: self.clipboard_clear(); self.clipboard_append(w.get("sel.first", "sel.last"))
        except: pass
    def text_paste(self, w: tk.Text) -> None:
        try: w.insert(tk.INSERT, self.clipboard_get()); self.segment_dirty = True
        except: pass
    
    def apply_filter(self, event: Any = None) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        status_filter = self.filter_var.get().lower(); search = self.search_var.get().lower()
        status_map = {'new': '🔴', 'needs-review': '🟠', 'translated': '🟢', 'final': '☑️'}
        for rec in self.data_store:
            rec_status = str(rec['status']).lower().replace(" ", "").replace("-", "")
            filter_clean = status_filter.replace(" ", "").replace("-", "")
            if status_filter != "all" and rec_status != filter_clean: continue
            if search and (search not in str(rec['source']).lower() and search not in str(rec['target']).lower() and search not in str(rec['id']).lower()): continue
            tag = str(rec['status']).lower().replace(" ", "_").replace("-", "_")
            icon = status_map.get(str(rec['status']).lower(), '❓')
            self.tree.insert("", "end", values=(rec['id'], rec['source'].replace('\n', ' '), rec['target'].replace('\n', ' '), icon), tags=(tag,))
