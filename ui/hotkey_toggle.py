import customtkinter as ctk
from typing import Optional
from core.config_loader import ConfigLoader

class HotkeyToggle(ctk.CTkFrame):
    """
    Modular UI frame allowing users to view, edit, and save dual-layer 
    Numpad macro mappings (Num Lock ON vs Num Lock OFF) and sample paths.
    """
    def __init__(self, master, config_loader: Optional[ConfigLoader] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.config_loader = config_loader if config_loader else ConfigLoader("config/num_mapping.json")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_editor_workspace()

    def _build_header(self):
        """Constructs the top toolbar with layer toggle and save controls."""
        header_frame = ctk.CTkFrame(self, height=50, fg_color="#181818")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame, 
            text="Numpad Dual-Layer Macro Mapper", 
            font=("Arial", 14, "bold"), 
            text_color="cyan"
        ).pack(side="left", padx=15)

        # Layer Selector Segmented Button (Num Lock ON / OFF)
        self.layer_selector = ctk.CTkSegmentedButton(
            header_frame, 
            values=["Num Lock ON", "Num Lock OFF"],
            command=self._on_layer_switch
        )
        self.layer_selector.set("Num Lock ON")
        self.layer_selector.pack(side="left", padx=20)

        ctk.CTkButton(
            header_frame, 
            text="💾 Save Mappings", 
            fg_color="#1f538d", 
            command=self._save_current_edits
        ).pack(side="right", padx=15)

    def _build_editor_workspace(self):
        """Constructs the scrollable grid of editable hotkey fields."""
        self.workspace_frame = ctk.CTkScrollableFrame(self, fg_color="#141414")
        self.workspace_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.workspace_frame.grid_columnconfigure(0, weight=1)

        self.entries = {}
        self._populate_layer_fields("num_lock_on")

    def _on_layer_switch(self, value: str):
        """Switches the visible hotkey rows based on the selected layer tab."""
        layer_key = "num_lock_on" if value == "Num Lock ON" else "num_lock_off"
        self._populate_layer_fields(layer_key)

    def _populate_layer_fields(self, layer_key: str):
        """Clears and re-populates the input fields for the active layer."""
        for widget in self.workspace_frame.winfo_children():
            widget.destroy()
        self.entries.clear()

        layers_data = self.config_loader.data.get("numpad_layers", {})
        layer_mappings = layers_data.get(layer_key, {})

        ctk.CTkLabel(
            self.workspace_frame, 
            text=f"Editing Layer: {layer_key.upper()}", 
            font=("Arial", 12, "bold"),
            text_color="gray"
        ).pack(anchor="w", padx=10, pady=5)

        for key_code, info in layer_mappings.items():
            row_frame = ctk.CTkFrame(self.workspace_frame, fg_color="#222222", corner_radius=6)
            row_frame.pack(fill="x", padx=5, pady=5)
            row_frame.grid_columnconfigure(2, weight=1)

            # Key Identifier Label
            ctk.CTkLabel(row_frame, text=key_code.upper(), font=("Consolas", 12, "bold"), width=80).grid(row=0, column=0, padx=10, pady=8)

            # Editable Label Entry
            label_var = ctk.StringVar(value=info.get("label", ""))
            label_entry = ctk.CTkEntry(row_frame, textvariable=label_var, width=150, height=26)
            label_entry.grid(row=0, column=1, padx=5, pady=8)

            # Editable Sample Path Entry
            sample_var = ctk.StringVar(value=info.get("sample", ""))
            sample_entry = ctk.CTkEntry(row_frame, textvariable=sample_var, height=26)
            sample_entry.grid(row=0, column=2, sticky="ew", padx=5, pady=8)

            self.entries[key_code] = {
                "layer": layer_key,
                "label_var": label_var,
                "sample_var": sample_var
            }

    def _save_current_edits(self):
        """Pulls values from UI entry fields and commits them to the config loader."""
        active_layer = "num_lock_on" if self.layer_selector.get() == "Num Lock ON" else "num_lock_off"
        
        for key_code, data in self.entries.items():
            if data["layer"] == active_layer:
                new_label = data["label_var"].get()
                new_sample = data["sample_var"].get()
                self.config_loader.update_macro_binding(active_layer, key_code, new_label, new_sample)
        
        print("Controller Action: User hotkey layer successfully updated and saved to config/num_mapping.json")