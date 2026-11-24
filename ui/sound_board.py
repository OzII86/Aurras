import os
import json
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any
from tkinter import simpledialog, messagebox
from ui.led_meter import LEDMeter
from ui.track_sidebar import TimelineTrack
from ui.controllers.hardware_io import HardwareIOBlock
from ui.controllers.channel_strip import ChannelStrip

class SoundBoardPanel(ctk.CTkFrame):
    """
    Professional broadcast-grade mixing console featuring vertical faders, 
    echo/delay processing, real-time peak LED meters, and hardware I/O volume controls.
    """
    def __init__(self, master, on_parameter_change: Optional[Callable[[Dict[str, Any]], None]] = None, **kwargs):
        super().__init__(master, fg_color="#141414", corner_radius=8, **kwargs)
        
        self.on_parameter_change = on_parameter_change
        self.active_track: Optional[TimelineTrack] = None

        self._init_presets_directory()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- TOP HEADER & PRESET BROWSER ---
        self._build_header_bar()

        # --- CONSOLE MODULE CONTAINER (HORIZONTAL ROW OF VERTICAL STRIPS) ---
        self.console_container = ctk.CTkScrollableFrame(self, fg_color="#1a1a1a", orientation="horizontal", height=460)
        self.console_container.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        self._build_vertical_modules()

    def _init_presets_directory(self):
        base_presets = os.path.join(os.getcwd(), "Vault", "Presets")
        for sub in ["Genres", "Voices", "Customs", "Beats"]:
            os.makedirs(os.path.join(base_presets, sub), exist_ok=True)

    def _build_header_bar(self):
        header_frame = ctk.CTkFrame(self, fg_color="#1f1f1f", height=40)
        header_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        
        self.title_lbl = ctk.CTkLabel(header_frame, text="Mixing Console", font=("Arial", 12, "bold"), text_color="cyan")
        self.title_lbl.pack(side="left", padx=10, pady=8)

        save_preset_btn = ctk.CTkButton(header_frame, text="Save Preset...", width=100, height=26, fg_color="#1f538d", command=self._save_current_preset)
        save_preset_btn.pack(side="right", padx=8)

        self.preset_optionmenu = ctk.CTkOptionMenu(header_frame, values=["Load Preset..."], width=160, height=26, command=self._load_preset_callback)
        self.preset_optionmenu.pack(side="right", padx=8)
        self._refresh_preset_dropdown()

    def set_active_track(self, track: Optional[TimelineTrack]):
        self.active_track = track
        if track:
            self.title_lbl.configure(text=f"Mixing Console: Track {track.track_id + 1} - {track.name}")
        else:
            self.title_lbl.configure(text="Mixing Console: [No Track Selected]")

    def _create_vertical_strip(self, title: str, width: int = 130) -> ctk.CTkFrame:
        strip = ctk.CTkFrame(self.console_container, fg_color="#222222", width=width, corner_radius=6)
        strip.pack(side="left", fill="y", padx=5, pady=5)
        strip.pack_propagate(False)
        
        ctk.CTkLabel(strip, text=title, font=("Arial", 10, "bold"), text_color="#aaaaaa").pack(pady=(6, 4))
        return strip

    def add_channel(self, track_name: Optional[str] = None):
        """Spawns a new complete vertical channel strip, inheriting the track's name."""
        ch_id = len(self.channels) + 1
        strip = ChannelStrip(self.channels_container, ch_id, self._on_slider_changed)
        strip.pack(side="left", fill="y", padx=3, pady=5)
        
        if track_name:
            strip.name_entry.delete(0, "end")
            strip.name_entry.insert(0, track_name)
            
        self.channels.append(strip)
        self._on_slider_changed(None)

    def clear_channels(self):
        """Destroys all active channel strips (used when loading a new project)."""
        for ch in self.channels:
            ch.destroy()
        self.channels.clear()

    def _build_vertical_modules(self):
        # 1. Permanent Hardware I/O Block 
        self.hardware_io = HardwareIOBlock(self.console_container, self._on_slider_changed, width=160)
        self.hardware_io.pack(side="left", fill="y", padx=(10, 5), pady=10)

        # 2. The Channel Strip Matrix
        self.channels_container = ctk.CTkFrame(self.console_container, fg_color="transparent")
        self.channels_container.pack(side="left", fill="both", expand=True)
        
        self.channels = []
        
        # 3. Voice Modulator / Pitch Strip
        mod_strip = self._create_vertical_strip("Voice FX")
        ctk.CTkLabel(mod_strip, text="Pitch", font=("Arial", 9)).pack()
        self.pitch_slider = ctk.CTkSlider(
            mod_strip, from_=-12, to=12, number_of_steps=24, 
            orientation="vertical", height=90,
            command=self._on_slider_changed
        )
        self.pitch_slider.set(0)
        self.pitch_slider.pack(pady=2)
        
        self.voice_mod_switch = ctk.CTkSwitch(mod_strip, text="Mod", font=("Arial", 9))
        self.voice_mod_switch.pack(pady=4)


    def get_current_parameters(self) -> dict:
        """Collects the hardware master levels and the full state of every channel strip."""
        params = {}
        if hasattr(self, 'hardware_io'):
            params.update(self.hardware_io.get_values())
            
        if hasattr(self, 'channels'):
            # This creates a clean array of every channel's settings
            params["channels"] = [ch.get_values() for ch in self.channels]
            
        return params

    def update_all_meters(self, peaks: dict):
        """Distributes signal peaks to the Hardware I/O and the Channel Strips."""
        if hasattr(self, 'hardware_io'):
            self.hardware_io.update_meters(peaks)
            
        if hasattr(self, 'channels'):
            # Send the peak to each corresponding channel strip dynamically
            for i, ch in enumerate(self.channels):
                ch_peak = peaks.get(f"channel_{i}", 0.0)
                ch.update_meter(ch_peak)

    def _on_slider_changed(self, value):
        """Triggers the external callback whenever any fader or slider moves."""
        if self.on_parameter_change:
            self.on_parameter_change(self.get_current_parameters())

    
    def _refresh_preset_dropdown(self):
        presets = []
        base_presets = os.path.join(os.getcwd(), "Vault", "Presets")
        for root, dirs, files in os.walk(base_presets):
            for file in files:
                if file.endswith(".json"):
                    rel = os.path.relpath(os.path.join(root, file), base_presets)
                    presets.append(rel)
        if presets:
            self.preset_optionmenu.configure(values=presets)

    def _load_preset_callback(self, choice: str):
        print(f"Loading preset: {choice}")

    def _save_current_preset(self):
        
        preset_name = simpledialog.askstring("Save Preset", "Enter custom preset name:", parent=self)
        if preset_name:
            path = os.path.join(os.getcwd(), "Vault", "Presets", "Customs", f"{preset_name}.json")
            
            data = {
                "preset_name": preset_name, 
                "parameters": self.get_current_parameters()
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
            self._refresh_preset_dropdown()
            messagebox.showinfo("Preset Saved", f"Successfully saved preset to Customs/{preset_name}.json", parent=self)