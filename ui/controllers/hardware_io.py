import customtkinter as ctk
from ui.led_meter import LEDMeter

class HardwareIOBlock(ctk.CTkFrame):
    """Permanent Master I/O block for Mic and Speaker routing and metering."""
    def __init__(self, master, on_change_callback, **kwargs):
        super().__init__(master, fg_color="#1a1a1a", corner_radius=6, **kwargs)
        self.on_change_callback = on_change_callback
        self.rec_to_new_track = False  # ---> NEW: Memory state for the push button
        
        # Header
        ctk.CTkLabel(self, text="Hardware I/O", font=("Arial", 10, "bold")).pack(pady=(5, 10))
        
        io_row = ctk.CTkFrame(self, fg_color="transparent")
        io_row.pack(fill="both", expand=True, padx=4, pady=4)

        # --- MIC STRIP ---
        mic_col = ctk.CTkFrame(io_row, fg_color="transparent")
        mic_col.pack(side="left", expand=True, fill="both")
        ctk.CTkLabel(mic_col, text="Mic", font=("Arial", 8)).pack()
        
        mic_inner = ctk.CTkFrame(mic_col, fg_color="transparent")
        mic_inner.pack(expand=True)
        
        self.mic_slider = ctk.CTkSlider(
            mic_inner, from_=0, to=100, number_of_steps=100, 
            orientation="vertical", height=90, width=14,
            command=on_change_callback
        )
        self.mic_slider.set(80)
        self.mic_slider.pack(side="left", padx=(0, 4))
        
        self.mic_meter = LEDMeter(mic_inner, height=90)
        self.mic_meter.pack(side="left")

        # --- MIC ANTI-POP FADE ---
        ctk.CTkLabel(self, text="Mic Fade (s)", font=("Arial", 8)).pack(pady=(10, 0))
        self.mic_fade = ctk.CTkSlider(self, from_=0, to=2, width=70, height=10, command=on_change_callback)
        self.mic_fade.set(0.15)  # Default to 150ms anti-pop
        self.mic_fade.pack(pady=(0, 5))

        # --- SPEAKER STRIP ---
        spk_col = ctk.CTkFrame(io_row, fg_color="transparent")
        spk_col.pack(side="left", expand=True, fill="both")
        ctk.CTkLabel(spk_col, text="Speaker", font=("Arial", 8)).pack()
        
        spk_inner = ctk.CTkFrame(spk_col, fg_color="transparent")
        spk_inner.pack(expand=True)
        
        self.speaker_slider = ctk.CTkSlider(
            spk_inner, from_=0, to=100, number_of_steps=100, 
            orientation="vertical", height=90, width=14,
            command=on_change_callback
        )
        self.speaker_slider.set(75)
        self.speaker_slider.pack(side="left", padx=(0, 4))
        
        self.speaker_meter = LEDMeter(spk_inner, height=90)
        self.speaker_meter.pack(side="left")

        # --- SMART PUSH BUTTON (Stateful) ---
        self.rec_mode_btn = ctk.CTkButton(
            self, text="Rec Mode: Overwrite", font=("Arial", 10, "bold"), 
            fg_color="#333333", hover_color="#444444", 
            command=self._toggle_rec_mode
        )
        self.rec_mode_btn.pack(pady=(10, 5))

    def _toggle_rec_mode(self):
        """Flips the memory state and updates the UI button colors."""
        self.rec_to_new_track = not self.rec_to_new_track
        
        if self.rec_to_new_track:
            self.rec_mode_btn.configure(text="Rec Mode: New Track", fg_color="#1f538d", hover_color="#143a63")
        else:
            self.rec_mode_btn.configure(text="Rec Mode: Overwrite", fg_color="#333333", hover_color="#444444")
            
        self.on_change_callback(0)  # Push dummy update to console

    def get_values(self) -> dict:
        """Returns the master I/O levels and global switches."""
        return {
            "mic_vol": self.mic_slider.get(),
            "speaker_vol": self.speaker_slider.get(),
            "mic_fade": self.mic_fade.get(),
            "rec_new_track": self.rec_to_new_track
        }
        
    def update_meters(self, peaks: dict):
        """Feeds live audio engine peaks into the LED meters."""
        self.mic_meter.set_level(peaks.get("mic", 0.0))
        self.speaker_meter.set_level(peaks.get("speaker", 0.0))