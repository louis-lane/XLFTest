import tkinter as tk
from typing import Union

def center_window(popup: Union[tk.Toplevel, tk.Tk], width: int, height: int, parent: tk.Widget) -> None:
    """
    Centers a popup window relative to its parent window.
    
    Args:
        popup (tk.Toplevel): The window to center.
        width (int): Desired width.
        height (int): Desired height.
        parent (tk.Widget): The parent widget to center against.
    """
    popup.update_idletasks()
    
    # Robustly find the top-level parent
    root = parent.winfo_toplevel()
    
    x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)
    
    # Prevent negative coordinates (off-screen)
    if x < 0: x = 0
    if y < 0: y = 0
    
    popup.geometry(f"{width}x{height}+{x}+{y}")
