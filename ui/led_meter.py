import customtkinter as ctk

class LEDMeter(ctk.CTkFrame):
    """Modular vertical LED peak meter for granular signal chain monitoring."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#111111", width=12, corner_radius=2, **kwargs)
        self.pack_propagate(False)

        # Pack from the BOTTOM up so they anchor to the base of the fader
        self.led_green3 = ctk.CTkFrame(self, fg_color="#003300", height=10, corner_radius=2)
        self.led_green3.pack(side="bottom", fill="x", padx=2, pady=(1, 2))
        
        self.led_green2 = ctk.CTkFrame(self, fg_color="#003300", height=10, corner_radius=2)
        self.led_green2.pack(side="bottom", fill="x", padx=2, pady=(1, 2))
        
        self.led_green1 = ctk.CTkFrame(self, fg_color="#003300", height=10, corner_radius=2)
        self.led_green1.pack(side="bottom", fill="x", padx=2, pady=1)

        self.led_yellow3 = ctk.CTkFrame(self, fg_color="#333300", height=10, corner_radius=2)
        self.led_yellow3.pack(side="bottom", fill="x", padx=2, pady=1)

        self.led_yellow2 = ctk.CTkFrame(self, fg_color="#333300", height=10, corner_radius=2)
        self.led_yellow2.pack(side="bottom", fill="x", padx=2, pady=1)

        self.led_yellow1 = ctk.CTkFrame(self, fg_color="#333300", height=10, corner_radius=2)
        self.led_yellow1.pack(side="bottom", fill="x", padx=2, pady=1)
        
        self.led_red = ctk.CTkFrame(self, fg_color="#330000", height=10, corner_radius=2)
        self.led_red.pack(side="bottom", fill="x", padx=2, pady=(2, 1))

    def set_level(self, level: float):
        """Updates the LED colors based on a 0.0 to 1.0 signal peak."""
        self.led_red.configure(fg_color="#ff0000" if level > 0.90 else "#330000")
        self.led_yellow3.configure(fg_color="#ffff00" if level > 0.75 else "#333300")
        self.led_yellow2.configure(fg_color="#ffff00" if level > 0.60 else "#333300")
        self.led_yellow1.configure(fg_color="#ffff00" if level > 0.45 else "#333300")
        self.led_green1.configure(fg_color="#00ff00" if level > 0.30 else "#003300")
        self.led_green2.configure(fg_color="#00ff00" if level > 0.15 else "#003300")
        self.led_green3.configure(fg_color="#00ff00" if level > 0.05 else "#003300")