import os
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

class VaultExplorerSidebar(ctk.CTkFrame):
    """
    VS Code-style Vault explorer sidebar supporting double-click project loading 
    and audio asset handling.
    """
    def __init__(self, master, on_project_open_callback, on_audio_load_callback, **kwargs):
        super().__init__(master, fg_color="#141414", **kwargs)
        
        self.on_project_open_callback = on_project_open_callback
        self.on_audio_load_callback = on_audio_load_callback

        # Header Label
        self.header = ctk.CTkLabel(self, text="VAULT EXPLORER", font=("Arial", 10, "bold"), text_color="gray")
        self.header.pack(fill="x", padx=8, pady=(6, 2))

        # Styled ttk Treeview for dark theme compatibility
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure(
            "Vault.Treeview",
            background="#141414",
            foreground="white",
            fieldbackground="#141414",
            borderwidth=0,
            font=("Arial", 9),
            rowheight=20
        )
        self.style.map("Vault.Treeview", background=[('selected', '#1f538d')])

        self.tree = ttk.Treeview(self, style="Vault.Treeview", selectmode="browse", show="tree")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        self.tree.bind("<Double-1>", self._on_item_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.refresh_vault_tree()

    def refresh_vault_tree(self):
        """Populates the tree structure starting directly from the Vault/ contents."""
        self.tree.delete(*self.tree.get_children())
        vault_root = os.path.join(os.getcwd(), "Vault")
        if not os.path.exists(vault_root):
            return

        # Populate children directly at the root level ("") to eliminate the spacer node
        self._populate_node("", vault_root)

    def _populate_node(self, parent, path):
        try:
            for item in sorted(os.listdir(path)):
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    node = self.tree.insert(parent, "end", text=f"📂 {item}", open=False)
                    self._populate_node(node, full_path)
                else:
                    ext = os.path.splitext(item)[1].lower()
                    if ext in ['.wav', '.mp3', '.flac', '.ogg', '.aurras']:
                        icon = "🎵" if ext != '.aurras' else "📄"
                        self.tree.insert(parent, "end", text=f"{icon} {item}", values=[full_path])
        except PermissionError:
            pass

    def _on_item_double_click(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return
        selected_item = selected_items[0]
        item_values = self.tree.item(selected_item, "values")
        if item_values:
            file_path = item_values[0]
            if file_path.endswith(".aurras"):
                project_dir = os.path.dirname(file_path)
                self.on_project_open_callback(project_dir)
            elif file_path.endswith(('.wav', '.mp3', '.flac', '.ogg')):
                self.on_audio_load_callback(file_path)

    def _on_right_click(self, event):
        selected_id = self.tree.identify_row(event.y)
        if selected_id:
            self.tree.selection_set(selected_id)
            item_values = self.tree.item(selected_id, "values")
            item_text = self.tree.item(selected_id, "text")
            
            menu = tk.Menu(self, tearoff=0, bg="#1a1a1a", fg="white", activebackground="#1f538d", activeforeground="white")
            
            # Determine path whether it's a file (has values) or a folder (resolved from tree path)
            target_path = item_values[0] if item_values else self._get_item_path_from_tree(selected_id)
            
            if target_path and os.path.exists(target_path):
                menu.add_command(label="Reveal in File Explorer", command=lambda: os.startfile(os.path.dirname(target_path) if os.path.isfile(target_path) else target_path))
                menu.add_separator()
                menu.add_command(label="Rename...", command=lambda: self._rename_item(target_path))
                menu.add_command(label="Delete", command=lambda: self._delete_item(target_path))
                menu.add_separator()
                
            menu.add_command(label="Refresh Explorer", command=self.refresh_vault_tree)
            menu.tk_popup(event.x_root, event.y_root)

    def _get_item_path_from_tree(self, item_id):
        """Helper to resolve directory paths for folder nodes that don't have stored values."""
        path_parts = []
        current = item_id
        while current:
            text = self.tree.item(current, "text").replace("📂 ", "").replace("🎵 ", "").replace("📄 ", "")
            path_parts.insert(0, text)
            current = self.tree.parent(current)
        return os.path.join(os.getcwd(), "Vault", *path_parts)

    def _rename_item(self, target_path):
        from tkinter import simpledialog, messagebox
        old_name = os.path.basename(target_path)
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=old_name, parent=self)
        
        if new_name and new_name != old_name:
            parent_dir = os.path.dirname(target_path)
            new_path = os.path.join(parent_dir, new_name)
            try:
                os.rename(target_path, new_path)
                self.refresh_vault_tree()
                print(f"Vault Action: Renamed {old_name} to {new_name}")
            except Exception as e:
                messagebox.showerror("Rename Error", f"Could not rename item:\n{e}", parent=self)

    def _delete_item(self, target_path):
        from tkinter import messagebox
        item_name = os.path.basename(target_path)
        is_dir = os.path.isdir(target_path)
        msg = f"Are you sure you want to delete folder '{item_name}' and all its contents?" if is_dir else f"Are you sure you want to delete file '{item_name}'?"
        
        if messagebox.askyesno("Confirm Delete", msg, icon="warning", parent=self):
            try:
                if is_dir:
                    import shutil
                    shutil.rmtree(target_path)
                else:
                    os.remove(target_path)
                self.refresh_vault_tree()
                print(f"Vault Action: Deleted {target_path}")
            except Exception as e:
                messagebox.showerror("Delete Error", f"Could not delete item:\n{e}", parent=self)