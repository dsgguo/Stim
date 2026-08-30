
import tkinter as tk
from tkinter import font as tkfont
import ctypes

try:
    # 强制在Tkinter初始化之前声明高DPI感知
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

def select_mode():
    """
    Displays a GUI startup menu and returns the selected mode.
    Values: 'free', 'offline', 'online_discrete', 'online_continuous'
    Returns None if the user cancels (ESC or window close).
    """
    
    selected_mode = [None] # None signals cancellation (ESC / window close); set on Enter
    
    options = [
        ("Design Mode", 'free'),
        ("Offline Experiment", 'offline'),
        ("Online Discrete Experiment", 'online_discrete'),
        ("Online Continuous Experiment", 'online_continuous')
    ]
    
    root = tk.Tk()
    root.title("Stimulus Startup")
    root.geometry("400x350")
    root.configure(bg="#2E2E2E")
    
    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    # Fonts
    title_font = tkfont.Font(family="Helvetica", size=18, weight="bold")
    item_font = tkfont.Font(family="Helvetica", size=14)
    sel_font = tkfont.Font(family="Helvetica", size=14, weight="bold")

    current_selection_index = 0
    option_labels = []

    def update_ui():
        for i, (text, mode) in enumerate(options):
            lbl = option_labels[i]
            if i == current_selection_index:
                lbl.config(fg="#FFFFFF", bg="#4A90E2", font=sel_font) # Highlight
            else:
                lbl.config(fg="#DDDDDD", bg="#2E2E2E", font=item_font) # Normal

    def on_key_up(event):
        nonlocal current_selection_index
        current_selection_index = (current_selection_index - 1) % len(options)
        update_ui()

    def on_key_down(event):
        nonlocal current_selection_index
        current_selection_index = (current_selection_index + 1) % len(options)
        update_ui()

    def on_select(event=None):
        nonlocal selected_mode
        selected_mode[0] = options[current_selection_index][1]
        print(f"User selected: {options[current_selection_index][0]}")
        root.destroy()
        
    # Title
    header = tk.Label(root, text="Select Mode", bg="#2E2E2E", fg="#FFFFFF", font=title_font)
    header.pack(pady=20)
    
    # Options Container
    frame = tk.Frame(root, bg="#2E2E2E")
    frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    for text, mode in options:
        lbl = tk.Label(frame, text=text, bg="#2E2E2E", fg="#DDDDDD", font=item_font, pady=8, width=30, anchor="w")
        lbl.pack(fill=tk.X)
        option_labels.append(lbl)

    # Initial Highlight
    update_ui()
    
    # Bindings
    root.bind('<Up>', on_key_up)
    root.bind('<Down>', on_key_down)
    root.bind('<Return>', on_select)
    root.bind('<Escape>', lambda e: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    
    # Focus
    root.focus_force()
    
    root.mainloop()
    
    return selected_mode[0]

if __name__ == "__main__":
    # Test standalone
    mode = select_mode()
    print(f"Final Selection returned: {mode}")
