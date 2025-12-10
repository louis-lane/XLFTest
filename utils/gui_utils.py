import tkinter as tk

def center_window(popup, width, height, parent):
    popup.update_idletasks()
    root = parent.winfo_toplevel()
    x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)
    if x < 0: x = 0
    if y < 0: y = 0
    popup.geometry(f"{width}x{height}+{x}+{y}")
