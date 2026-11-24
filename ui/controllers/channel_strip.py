import customtkinter as ctk
from ui.led_meter import LEDMeter

class ChannelStrip(ctk.CTkFrame):
    """A complete, standardized DAW channel strip with built-in EQ, FX, and routing."""
    def __init__(self, master, ch_id: int, on_change_callback, **kwargs):
        super().__init__(master, fg_color="#222222", corner_radius=4, border_width=1, border_color="#333333", **kwargs)
        self.on_change_callback = on_change_callback
        
        # 1. PAN & GAIN (Horizontal sliders acting as knobs)
        ctk.CTkLabel(self, text="Pan", font=("Arial", 8)).pack(pady=(5, 0))
        self.pan = ctk.CTkSlider(self, from_=-100, to=100, width=70, height=10, command=self._trigger_callback)
        self.pan.set(0)
        self.pan.pack(pady=(0, 2))
        
        ctk.CTkLabel(self, text="Gain", font=("Arial", 8)).pack()
        self.gain = ctk.CTkSlider(self, from_=-24, to=24, width=70, height=10, command=self._trigger_callback)
        self.gain.set(0)
        self.gain.pack(pady=(0, 2))

        # 2. EQ STACK (Upgraded to 4-Band with +/- 24dB limits)
        ctk.CTkLabel(self, text="High", font=("Arial", 8)).pack()
        self.eq_high = ctk.CTkSlider(self, from_=-24, to=24, width=70, height=10, command=self._trigger_callback)
        self.eq_high.set(0)
        self.eq_high.pack(pady=(0, 2))
        
        ctk.CTkLabel(self, text="Mid", font=("Arial", 8)).pack()
        self.eq_mid = ctk.CTkSlider(self, from_=-24, to=24, width=70, height=10, command=self._trigger_callback)
        self.eq_mid.set(0)
        self.eq_mid.pack(pady=(0, 2))
        
        ctk.CTkLabel(self, text="Low", font=("Arial", 8)).pack()
        self.eq_low = ctk.CTkSlider(self, from_=-24, to=24, width=70, height=10, command=self._trigger_callback)
        self.eq_low.set(0)
        self.eq_low.pack(pady=(0, 2))

        ctk.CTkLabel(self, text="Bass", font=("Arial", 8)).pack()
        self.eq_bass = ctk.CTkSlider(self, from_=-24, to=24, width=70, height=10, command=self._trigger_callback)
        self.eq_bass.set(0)
        self.eq_bass.pack(pady=(0, 2))

        # 3. FX SENDS
        ctk.CTkLabel(self, text="Echo FX", font=("Arial", 8)).pack()
        self.fx_echo = ctk.CTkSlider(self, from_=0, to=100, width=70, height=10, command=self._trigger_callback)
        self.fx_echo.set(0)
        self.fx_echo.pack(pady=(0, 5))

        # 4. ROUTING TOGGLES (HPF & Mute)
        toggle_row = ctk.CTkFrame(self, fg_color="transparent")
        toggle_row.pack(pady=2)
        self.btn_hpf = ctk.CTkButton(toggle_row, text="HPF", width=30, height=20, font=("Arial", 8), fg_color="#333333")
        self.btn_hpf.pack(side="left", padx=2)
        self.is_muted = False
        self.btn_mute = ctk.CTkButton(
            toggle_row, text="M", width=20, height=20, font=("Arial", 9, "bold"), 
            fg_color="#552222", hover_color="#aa2222", command=self._toggle_mute
        )
        self.btn_mute.pack(side="left", padx=2)

        # 5. FADER & METER
        fader_row = ctk.CTkFrame(self, fg_color="transparent")
        fader_row.pack(expand=True, fill="y", pady=5)
        
        self.fader = ctk.CTkSlider(fader_row, from_=-60, to=12, orientation="vertical", width=14, height=120, command=self._trigger_callback)
        self.fader.set(0)
        self.fader.pack(side="left", padx=2)
        
        self.meter = LEDMeter(fader_row, height=120)
        self.meter.pack(side="left", padx=2)

        # 6. SCRIBBLE STRIP (Label)
        self.name_entry = ctk.CTkEntry(self, width=75, height=20, font=("Arial", 9, "bold"), fg_color="#111111", border_width=0, justify="center")
        self.name_entry.insert(0, f"Audio {ch_id}")
        self.name_entry.pack(side="bottom", pady=5)

    def _trigger_callback(self, _):
        """Passes the trigger up to the master board to pull fresh data"""
        if self.on_change_callback:
            self.on_change_callback(None)

    def _toggle_mute(self):
        """Flips the mute state, turns the button bright red, and updates the engine."""
        self.is_muted = not self.is_muted
        self.btn_mute.configure(fg_color="#ff2222" if self.is_muted else "#552222")
        self._trigger_callback(None)

    def get_values(self) -> dict:
        """Packages the entire state of this channel strip."""
        return {
            "name": self.name_entry.get(),
            "mute": self.is_muted,
            "pan": self.pan.get(),
            "gain": self.gain.get(),
            "eq_high": self.eq_high.get(),
            "eq_mid": self.eq_mid.get(),
            "eq_low": self.eq_low.get(),
            "eq_bass": self.eq_bass.get(),
            "fx_echo": self.fx_echo.get(),
            "fader": self.fader.get()
        }

    def update_meter(self, peak: float):
        self.meter.set_level(peak)