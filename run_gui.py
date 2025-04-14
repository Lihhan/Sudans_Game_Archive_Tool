from utils import load_or_create_config
import tkinter as tk
from itemlistapp import ItemListApp

if __name__ == "__main__":
    items = load_or_create_config()
    root = tk.Tk()
    app = ItemListApp(root)
    root.mainloop()