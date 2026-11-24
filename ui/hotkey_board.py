import os, json, re, shutil
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from typing import Callable, Optional
from core.config_loader import ConfigLoader
from core.beat_engine import BeatEngine
from core.auth_manager import AuthManager

class HotkeyBoard(ctk.CTkFrame):
    """
    MPC-style 3x3 Beat Pad Matrix powered by the standalone BeatEngine.
    Includes BPM Clock, Metronome, Timing Quantizer, Live Overdub Loop Recorder,
    Pitch/Bass/Treble Preset Baker, and one-click Sequencer Export.
    """

    def __init__(
        self,
        master,
        beat_engine: Optional[BeatEngine] = None,
        on_export_to_sequencer: Optional[Callable[[str, str], None]] = None,
        config_loader: Optional[ConfigLoader] = None,
        auth_manager: Optional[AuthManager] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.beat_engine = beat_engine if beat_engine else BeatEngine()
        self.on_export_to_sequencer = on_export_to_sequencer
        self.config_loader = config_loader if config_loader else ConfigLoader("config/num_mapping.json")
        self.auth_manager = auth_manager if auth_manager else AuthManager()
        self.selected_button_index: int = 0
        self.board_config = self.config_loader.get_hotkey_board_config()
        self.slots_data = self.board_config.get("slots", {})

        self.grid_mode: str = self.board_config.get("grid_mode", "3x3")

        # Configure layout: Row 0 = Transport, Row 1 = Pads + Inspector, Row 2 = Text Song Sequencer
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._build_transport_bar()
        self._build_soundboard_grid()
        self._build_editor_panel()
        self._build_song_composer_bar()

        # Sync initial transport settings with BeatEngine and pre-load samples
        self._sync_transport_to_engine()
        self._preload_all_slot_samples()
        self.controller_select_slot(0)

        slot0_sample = self._get_slot_dict(0).get("sample", "")
        if not slot0_sample or not os.path.exists(slot0_sample):
            self.pack_menu.set("Starter_Pack")
            self.controller_load_sound_pack("Starter_Pack")

        # Bind keyboard listener on root window and start transport UI polling
        self.after(200, self._bind_keyboard_triggers)
        self._poll_looper_transport()

    # =========================================================================
    # 1. TOP TEMPO, TIMING & LOOP RECORDING TRANSPORT BAR
    # =========================================================================

    def _build_transport_bar(self):
        self.transport_frame = ctk.CTkFrame(self, fg_color="#181818", corner_radius=8)
        self.transport_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))

        # --- Row A: Loop Controls, Beat Counter & Export ---
        top_row = ctk.CTkFrame(self.transport_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 4))

        self.loop_play_btn = ctk.CTkButton(
            top_row, text="▶ Start Loop", width=105, height=30,
            fg_color="#1f538d", hover_color="#2968b0", font=("Arial", 11, "bold"),
            command=self.controller_toggle_loop_play
        )
        self.loop_play_btn.pack(side="left", padx=4)

        self.loop_rec_btn = ctk.CTkButton(
            top_row, text="⏺ Overdub Rec", width=115, height=30,
            fg_color="#661111", hover_color="#991111", font=("Arial", 11, "bold"),
            command=self.controller_toggle_loop_record
        )
        self.loop_rec_btn.pack(side="left", padx=4)

        self.undo_loop_btn = ctk.CTkButton(
            top_row, text="↶ Undo Hit", width=85, height=30,
            fg_color="#333333", hover_color="#444444", font=("Arial", 11),
            command=self.controller_undo_overdub
        )
        self.undo_loop_btn.pack(side="left", padx=4)

        self.clear_loop_btn = ctk.CTkButton(
            top_row, text="🗑 Clear Loop", width=95, height=30,
            fg_color="#4a1c1c", hover_color="#6e2929", font=("Arial", 11),
            command=self.controller_clear_loop
        )
        self.clear_loop_btn.pack(side="left", padx=4)

        # Beat / Bar Readout Display
        self.beat_counter_lbl = ctk.CTkLabel(
            top_row, text="BAR 1 : BEAT 1", width=130,
            font=("Consolas", 14, "bold"), text_color="#00ffcc"
        )
        self.beat_counter_lbl.pack(side="left", padx=14)

        self.loop_progress = ctk.CTkProgressBar(top_row, width=180, height=12, progress_color="#00ffcc")
        self.loop_progress.set(0.0)
        self.loop_progress.pack(side="left", padx=6)

        # Export Buttons (Right Side)
        self.send_seq_btn = ctk.CTkButton(
            top_row, text="↪ Send Loop to Sequencer", width=175, height=30,
            fg_color="#006655", hover_color="#008870", font=("Arial", 11, "bold"),
            command=self.controller_send_loop_to_sequencer
        )
        self.send_seq_btn.pack(side="right", padx=4)

        self.export_wav_btn = ctk.CTkButton(
            top_row, text="💾 Save Loop WAV", width=130, height=30,
            fg_color="#2b4c7e", hover_color="#3b69ad", font=("Arial", 11, "bold"),
            command=self.controller_export_loop_wav
        )
        self.export_wav_btn.pack(side="right", padx=4)

        # --- Row B: Tempo (BPM), Bars, Timing Quantize & Metronome ---
        bottom_row = ctk.CTkFrame(self.transport_frame, fg_color="transparent")
        bottom_row.pack(fill="x", padx=10, pady=(2, 8))

        ctk.CTkLabel(bottom_row, text="Tempo (BPM):", font=("Arial", 11, "bold")).pack(side="left", padx=(4, 4))

        init_bpm = float(self.board_config.get("bpm", 120.0))
        self.bpm_var = ctk.StringVar(value=f"{int(init_bpm)}")
        self.bpm_entry = ctk.CTkEntry(bottom_row, textvariable=self.bpm_var, width=50, height=24, justify="center")
        self.bpm_entry.pack(side="left", padx=2)
        self.bpm_entry.bind("<Return>", self._on_bpm_entry_submit)
        self.bpm_entry.bind("<FocusOut>", self._on_bpm_entry_submit)

        self.bpm_slider = ctk.CTkSlider(
            bottom_row, from_=60, to=200, number_of_steps=140, width=140,
            command=self._on_bpm_slider_move
        )
        self.bpm_slider.set(init_bpm)
        self.bpm_slider.pack(side="left", padx=(4, 14))

        # Loop Length (Bars)
        ctk.CTkLabel(bottom_row, text="Loop Bars:", font=("Arial", 11, "bold")).pack(side="left", padx=(4, 4))
        init_bars = f"{self.board_config.get('bars', 2)} Bars"
        self.bars_menu = ctk.CTkOptionMenu(
            bottom_row, values=["1 Bar", "2 Bars", "4 Bars", "8 Bars"],
            width=90, height=24, command=lambda _: self._sync_transport_to_engine()
        )
        self.bars_menu.set(init_bars if init_bars in ["1 Bar", "2 Bars", "4 Bars", "8 Bars"] else "2 Bars")
        self.bars_menu.pack(side="left", padx=(2, 14))

        # Quantize Grid
        ctk.CTkLabel(bottom_row, text="Quantize:", font=("Arial", 11, "bold")).pack(side="left", padx=(4, 4))
        init_q = self.board_config.get("quantize", "1/16")
        self.quantize_menu = ctk.CTkOptionMenu(
            bottom_row, values=["Off", "1/4", "1/8", "1/16", "1/32"],
            width=80, height=24, command=lambda _: self._sync_transport_to_engine()
        )
        self.quantize_menu.set(init_q if init_q in ["Off", "1/4", "1/8", "1/16", "1/32"] else "1/16")
        self.quantize_menu.pack(side="left", padx=(2, 14))

        # Metronome Click Switch
        self.metro_switch = ctk.CTkSwitch(
            bottom_row, text="Metronome Click", font=("Arial", 11),
            progress_color="#00ffcc", command=self._sync_transport_to_engine
        )
        if self.board_config.get("metronome", True):
            self.metro_switch.select()
        self.metro_switch.pack(side="left", padx=8)

        ctk.CTkLabel(bottom_row, text="Sound Pack:", font=("Arial", 11, "bold"), text_color="cyan").pack(side="left", padx=(12, 4))
        self.pack_menu = ctk.CTkOptionMenu(
            bottom_row, values=self._discover_installed_packs(),
            width=145, height=24, fg_color="#1f538d", command=self.controller_load_sound_pack
        )
        self.pack_menu.set("Select Pack...")
        self.pack_menu.pack(side="left", padx=4)

        self.refresh_packs_btn = ctk.CTkButton(
            bottom_row, text="🔄", width=28, height=24,
            fg_color="#333333", hover_color="#444444", font=("Arial", 11),
            command=self.controller_refresh_packs
        )
        self.refresh_packs_btn.pack(side="left", padx=2)

        self.load_pack_btn = ctk.CTkButton(
            bottom_row, text="📂 Load Pack", width=95, height=24,
            fg_color="#2b4c7e", hover_color="#3b69ad", font=("Arial", 11, "bold"),
            command=self.controller_browse_and_load_pack_folder
        )
        self.load_pack_btn.pack(side="left", padx=(2, 2))

        self.save_pack_btn = ctk.CTkButton(
            bottom_row, text="📦 Save Pack", width=95, height=24,
            fg_color="#006655", hover_color="#008870", font=("Arial", 11, "bold"),
            command=self.controller_save_sound_pack
        )
        self.save_pack_btn.pack(side="left", padx=(2, 8))

        self.account_btn = ctk.CTkButton(
            bottom_row, text="👤 Sign In", width=95, height=24,
            fg_color="#3b3b58", hover_color="#4f4f75", font=("Arial", 11, "bold"),
            command=self.controller_open_account_dialog
        )
        self.account_btn.pack(side="left", padx=(2, 2))

        self.redeem_key_btn = ctk.CTkButton(
            bottom_row, text="🔑 Key", width=65, height=24,
            fg_color="#6b4c1e", hover_color="#8f6628", font=("Arial", 11, "bold"),
            command=self.controller_redeem_product_key
        )
        self.redeem_key_btn.pack(side="left", padx=(2, 8))

        ctk.CTkLabel(bottom_row, text="Grid:", font=("Arial", 11, "bold"), text_color="cyan").pack(side="left", padx=(6, 4))
        self.grid_mode_menu = ctk.CTkOptionMenu(
            bottom_row, values=["3x3", "3x6", "3x9", "Full (36)"],
            width=95, height=24, fg_color="#2b4c7e", command=self.controller_change_grid_mode
        )
        self.grid_mode_menu.set(self.grid_mode if self.grid_mode in ["3x3", "3x6", "3x9", "Full (36)"] else "3x3")
        self.grid_mode_menu.pack(side="left", padx=4)

        ctk.CTkLabel(
            bottom_row,
            text="Tip: Left-Click or press Hotkey to Play/Record Pad  •  Right-Click Pad to Configure",
            font=("Arial", 10), text_color="gray"
        ).pack(side="right", padx=6)

    # =========================================================================
    # 2. DYNAMIC PAD MATRIX, PAD INSPECTOR & TEXT SONG COMPOSER
    # =========================================================================

    def _get_grid_dimensions(self) -> tuple[int, int, int]:
        """Returns (rows, cols, total_pads) for the active grid_mode."""
        if self.grid_mode == "3x6":
            return 3, 6, 18
        elif self.grid_mode == "3x9":
            return 3, 9, 27
        elif self.grid_mode == "Full (36)":
            return 4, 9, 36
        return 3, 3, 9

    def _build_soundboard_grid(self):
        if hasattr(self, "grid_frame") and self.grid_frame.winfo_exists():
            self.grid_frame.destroy()

        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 4))

        rows, cols, total_pads = self._get_grid_dimensions()
        btn_font_size = 13 if cols <= 3 else (11 if cols <= 6 else 10)
        btn_height = 100 if rows <= 3 and cols <= 3 else 72

        self.buttons = []
        for i in range(total_pads):
            row = i // cols
            col = i % cols

            btn = ctk.CTkButton(
                self.grid_frame,
                text="",
                font=("Arial", btn_font_size, "bold"),
                height=btn_height,
                corner_radius=8,
                border_width=2,
                border_color="#333333",
                fg_color="#222222",
                hover_color="#2d4a77",
                command=lambda idx=i: self.controller_trigger_slot(idx)
            )
            btn.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            btn.bind("<Button-3>", lambda e, idx=i: self.controller_select_slot(idx))

            self.grid_frame.rowconfigure(row, weight=1)
            self.grid_frame.columnconfigure(col, weight=1)
            self.buttons.append(btn)
            self._refresh_pad_button_text(i)

    def controller_change_grid_mode(self, new_mode: str):
        """Rebuilds the pad matrix for 3x3, 3x6, 3x9, or Full (36) and updates the Inspector dropdown."""
        self.grid_mode = new_mode
        self.config_loader.data["hotkey_board"]["grid_mode"] = new_mode
        self.config_loader.save_config()

        current_pack = self.pack_menu.get() if hasattr(self, "pack_menu") else "Starter_Pack"
        updated_packs = self._discover_installed_packs()
        if hasattr(self, "pack_menu"):
            self.pack_menu.configure(values=updated_packs)

        self._build_soundboard_grid()
        _, _, total_pads = self._get_grid_dimensions()
        if hasattr(self, "slot_selector"):
            self.slot_selector.configure(values=[f"Pad {i + 1}" for i in range(total_pads)])

        target_pack = current_pack if current_pack in updated_packs and current_pack != "Select Pack..." else "Starter_Pack"
        if target_pack in updated_packs:
            self.pack_menu.set(target_pack)
            self.controller_load_sound_pack(target_pack)
        else:
            self.controller_select_slot(min(self.selected_button_index, total_pads - 1))

    def _build_editor_panel(self):
        self.editor_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="#181818")
        self.editor_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 10), pady=(4, 10))

        self.editor_title = ctk.CTkLabel(
            self.editor_frame, text="Pad 1 Inspector", font=("Arial", 16, "bold"), text_color="cyan"
        )
        self.editor_title.pack(pady=(10, 4))

        # Quick Pad Selector Dropdown
        self.slot_selector = ctk.CTkOptionMenu(
            self.editor_frame,
            values=[f"Pad {i + 1}" for i in range(9)],
            command=lambda val: self.controller_select_slot(int(val.split(" ")[1]) - 1),
            height=24
        )
        self.slot_selector.pack(fill="x", padx=15, pady=(0, 8))

        # 1. Audio Sample File Browser
        ctk.CTkLabel(self.editor_frame, text="Instrument / Sample File:", font=("Arial", 11, "bold")).pack(anchor="w", padx=15)
        sample_row = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        sample_row.pack(fill="x", padx=15, pady=(2, 6))

        self.sample_entry = ctk.CTkEntry(sample_row, placeholder_text="No audio sample loaded...", height=24)
        self.sample_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            sample_row, text="📂 Browse", width=75, height=24, fg_color="#2b4c7e",
            command=self.controller_browse_sample
        ).pack(side="right")

        # 2. Button Label
        ctk.CTkLabel(self.editor_frame, text="Pad Label:", font=("Arial", 11)).pack(anchor="w", padx=15)
        self.label_entry = ctk.CTkEntry(self.editor_frame, placeholder_text="e.g., 808 Kick, Snare, Synth Chord", height=24)
        self.label_entry.pack(fill="x", padx=15, pady=(2, 6))

        # 3. Hotkey Keybind
        ctk.CTkLabel(self.editor_frame, text="Keyboard Hotkey (Single Key):", font=("Arial", 11)).pack(anchor="w", padx=15)
        self.hotkey_entry = ctk.CTkEntry(self.editor_frame, placeholder_text="e.g., q, w, e, a, s, d, z, x, c", height=24)
        self.hotkey_entry.pack(fill="x", padx=15, pady=(2, 6))

        # 4. Pitch Shift Slider (-12 to +12 Semitones)
        self.pitch_lbl = ctk.CTkLabel(self.editor_frame, text="Pitch Shift: 0.0 st", font=("Arial", 11))
        self.pitch_lbl.pack(anchor="w", padx=15)
        self.pitch_slider = ctk.CTkSlider(
            self.editor_frame, from_=-12, to=12, number_of_steps=24,
            command=lambda val: self.pitch_lbl.configure(text=f"Pitch Shift: {float(val):+.1f} st")
        )
        self.pitch_slider.set(0)
        self.pitch_slider.pack(fill="x", padx=15, pady=(2, 6))

        # 5. Bass & Treble Tone Sliders (-12 to +12 dB)
        self.bass_lbl = ctk.CTkLabel(self.editor_frame, text="Bass EQ: +0 dB", font=("Arial", 11))
        self.bass_lbl.pack(anchor="w", padx=15)
        self.bass_slider = ctk.CTkSlider(
            self.editor_frame, from_=-12, to=12, number_of_steps=24,
            command=lambda val: self.bass_lbl.configure(text=f"Bass EQ: {int(val):+d} dB")
        )
        self.bass_slider.set(0)
        self.bass_slider.pack(fill="x", padx=15, pady=(2, 6))

        self.treble_lbl = ctk.CTkLabel(self.editor_frame, text="Treble EQ: +0 dB", font=("Arial", 11))
        self.treble_lbl.pack(anchor="w", padx=15)
        self.treble_slider = ctk.CTkSlider(
            self.editor_frame, from_=-12, to=12, number_of_steps=24,
            command=lambda val: self.treble_lbl.configure(text=f"Treble EQ: {int(val):+d} dB")
        )
        self.treble_slider.set(0)
        self.treble_slider.pack(fill="x", padx=15, pady=(2, 6))

        # 6. Pad Level / Volume Slider (0% to 150% using int bounds for Pylance)
        self.vol_lbl = ctk.CTkLabel(self.editor_frame, text="Pad Volume: 100%", font=("Arial", 11))
        self.vol_lbl.pack(anchor="w", padx=15)
        self.vol_slider = ctk.CTkSlider(
            self.editor_frame, from_=0, to=150, number_of_steps=30,
            command=lambda val: self.vol_lbl.configure(text=f"Pad Volume: {int(val)}%")
        )
        self.vol_slider.set(100)
        self.vol_slider.pack(fill="x", padx=15, pady=(2, 6))

        # 6B. Sound Stretch / Duration Timer Slider (0 = Auto/Original, 1..50 = 0.1s..5.0s)
        self.dur_lbl = ctk.CTkLabel(
            self.editor_frame, text="Stretch Timer: Original Length", font=("Arial", 11), text_color="#00ffcc"
        )
        self.dur_lbl.pack(anchor="w", padx=15)
        self.dur_slider = ctk.CTkSlider(
            self.editor_frame, from_=0, to=50, number_of_steps=50,
            command=self._on_duration_slider_move
        )
        self.dur_slider.set(0)
        self.dur_slider.pack(fill="x", padx=15, pady=(2, 6))

        # 7. Choke / Cut Self Switch
        self.choke_switch = ctk.CTkSwitch(
            self.editor_frame, text="Cut Self on Retrigger (808 / Hi-Hat)", font=("Arial", 11)
        )
        self.choke_switch.pack(anchor="w", padx=15, pady=(4, 8))

        # Action Buttons
        btn_row = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=15, pady=10)

        top_btn_row = ctk.CTkFrame(btn_row, fg_color="transparent")
        top_btn_row.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(
            top_btn_row, text="🔊 Test Pad", fg_color="#333333", hover_color="#444444", height=28,
            command=lambda: self.controller_trigger_slot(self.selected_button_index)
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            top_btn_row, text="↺ Reset Tweaks", fg_color="#4a2c2c", hover_color="#6e3b3b", height=28,
            command=self.controller_reset_slot_tweaks
        ).pack(side="right", fill="x", expand=True, padx=(4, 0))

        self.save_config_btn = ctk.CTkButton(
            btn_row, text="✔ Apply & Bake Preset Audio",
            command=self.controller_save_slot_config,
            fg_color="teal", hover_color="#006666", height=30, font=("Arial", 12, "bold")
        )
        self.save_config_btn.pack(fill="x")

    def _build_song_composer_bar(self):
        """Constructs the bottom Text-to-Beat Song Composer bar."""
        self.composer_frame = ctk.CTkFrame(self, fg_color="#181818", corner_radius=8)
        self.composer_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 10))

        header_row = ctk.CTkFrame(self.composer_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(6, 2))

        ctk.CTkLabel(
            header_row,
            text="🎼 Text-to-Song Sequencer  (Grouped letters = Play Together [Chord/Stack]  •  Space / '-' = Timing Step Gap)",
            font=("Arial", 11, "bold"), text_color="#00ffcc"
        ).pack(side="left")

        self.append_keys_switch = ctk.CTkSwitch(
            header_row, text="✍ Capture Pad Hits to Text", font=("Arial", 10), progress_color="orange"
        )
        self.append_keys_switch.pack(side="right", padx=6)

        input_row = ctk.CTkFrame(self.composer_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=12, pady=(2, 8))

        self.song_script_entry = ctk.CTkEntry(
            input_row,
            font=("Consolas", 13, "bold"),
            height=32,
            placeholder_text="Type keys here: e.g.  qez e we e qez qez we -   (qez plays Kick+Hat+Piano together, space steps forward)"
        )
        self.song_script_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        init_script = self.board_config.get("song_script", "qez e we e qez qez we e")
        if init_script:
            self.song_script_entry.insert(0, init_script)

        self.song_script_entry.bind("<KeyRelease>", lambda e: self._refresh_live_script_loop())

        ctk.CTkButton(
            input_row, text="▶ Play Written Song", width=150, height=32,
            fg_color="#1f538d", hover_color="#2968b0", font=("Arial", 11, "bold"),
            command=lambda: self.controller_play_song_script(clear_existing=True)
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            input_row, text="➕ Layer Text to Loop", width=150, height=32,
            fg_color="#006655", hover_color="#008870", font=("Arial", 11, "bold"),
            command=lambda: self.controller_play_song_script(clear_existing=False)
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            input_row, text="✖ Clear Text", width=90, height=32,
            fg_color="#4a1c1c", hover_color="#6e2929", font=("Arial", 11),
            command=lambda: self.song_script_entry.delete(0, "end")
        ).pack(side="left", padx=(4, 0))

    def _clear_song_script_and_refresh(self):
        """Clears the song script entry and wipes the live loop if currently playing."""
        self.song_script_entry.delete(0, "end")
        if self.beat_engine.is_running:
            self.beat_engine.clear_loop()

    def _refresh_live_script_loop(self):
        """
        If a playback loop is currently running, recompiles the updated song_script_entry
        directly into the active loop buffer so new captured pad hits play on the very next pass.
        """
        if not self.beat_engine.is_running:
            return

        script = self.song_script_entry.get()
        self.config_loader.data["hotkey_board"]["song_script"] = script
        self.config_loader.save_config()

        _, _, total_pads = self._get_grid_dimensions()
        key_map = {}
        for i in range(total_pads):
            info = self._get_slot_dict(i)
            k = info.get("hotkey", "").strip().lower()
            if k:
                key_map[k] = info

        if not script.strip():
            self.beat_engine.clear_loop()
            return

        self.beat_engine.compile_text_sequence_to_loop(
            script_text=script,
            key_to_slot_map=key_map,
            clear_existing=True,
            record_undo=False
        )

    def controller_play_song_script(self, clear_existing: bool = True):
        """Compiles the text box string into the BeatEngine loop buffer and starts playback."""
        script = self.song_script_entry.get()
        self.config_loader.data["hotkey_board"]["song_script"] = script
        self.config_loader.save_config()

        self._sync_transport_to_engine()

        _, _, total_pads = self._get_grid_dimensions()
        key_map = {}
        for i in range(total_pads):
            info = self._get_slot_dict(i)
            k = info.get("hotkey", "").strip().lower()
            if k:
                key_map[k] = info

        notes_count = self.beat_engine.compile_text_sequence_to_loop(
            script_text=script,
            key_to_slot_map=key_map,
            clear_existing=clear_existing
        )

        if notes_count > 0:
            self.beat_engine.start_loop(record_overdub=False)
            self.loop_play_btn.configure(text="⏹ Stop Loop", fg_color="#d97736", hover_color="#e68a00")
        else:
            messagebox.showwarning(
                "No Matching Keys",
                "None of the characters in your song text matched an active pad with a loaded audio sample.",
                parent=self
            )

    # =========================================================================
    # 3. CONTROLLERS & STANDALONE BEAT ENGINE WIRING
    # =========================================================================

    def _on_duration_slider_move(self, val):
        sec = int(val) / 10.0
        if sec <= 0.05:
            self.dur_lbl.configure(text="Stretch Timer: Original Length")
        else:
            self.dur_lbl.configure(text=f"Stretch Timer: {sec:.1f}s (Elongate/Stretch)")

    def _get_slot_dict(self, index: int) -> dict:
        full_keys = [
            "q", "w", "e", "a", "s", "d", "z", "x", "c",
            "r", "t", "y", "f", "g", "h", "v", "b", "n",
            "u", "i", "o", "j", "k", "l", "m", ",", ".",
            "1", "2", "3", "4", "5", "6", "7", "8", "9"
        ]
        default_key = full_keys[index] if index < len(full_keys) else ""
        return self.slots_data.get(f"slot_{index}", {
            "label": f"Pad {index + 1}",
            "hotkey": default_key,
            "sample": "",
            "base_sample": "",
            "pitch": 0.0,
            "bass": 0.0,
            "treble": 0.0,
            "duration": 0.0,
            "volume": 1.0,
            "choke": False
        })

    def _refresh_pad_button_text(self, index: int):
        info = self._get_slot_dict(index)
        label = info.get("label", f"Pad {index + 1}")
        hotkey = info.get("hotkey", "").upper()
        sample = info.get("sample", "")
        pitch = float(info.get("pitch", 0.0))
        bass = float(info.get("bass", 0.0))
        treble = float(info.get("treble", 0.0))

        sample_name = os.path.basename(sample) if sample else "Unassigned"
        if len(sample_name) > 20:
            sample_name = sample_name[:17] + "..."

        mods = []
        if abs(pitch) >= 0.5:
            mods.append(f"P{pitch:+.0f}")
        if abs(bass) >= 0.5:
            mods.append(f"B{bass:+.0f}")
        if abs(treble) >= 0.5:
            mods.append(f"T{treble:+.0f}")
        dur = float(info.get("duration", 0.0))
        if dur > 0.05:
            mods.append(f"{dur:.1f}s")
        mod_str = f" [{' '.join(mods)}]" if mods else ""

        key_badge = f"[{hotkey}]" if hotkey else "[No Key]"
        display_text = f"{label}  {key_badge}\n{sample_name}{mod_str}"
        has_file = bool(sample and os.path.exists(sample))
        base_color = "#1e3d59" if has_file else "#222222"

        self.buttons[index].configure(text=display_text, fg_color=base_color)

    def _preload_all_slot_samples(self):
        for i in range(36):
            info = self._get_slot_dict(i)
            sample_path = info.get("sample", "")
            if sample_path and os.path.exists(sample_path):
                self.beat_engine.load_sample(sample_path, 0.0)

    def _get_active_packs_root(self) -> tuple[str, str, int]:
        """Returns (abs_packs_root, grid_folder_name, total_pads) for the current grid_mode."""
        mode_map = {
            "3x3": ("3x3", 9),
            "3x6": ("3x6", 18),
            "3x9": ("3x9", 27),
            "Full (36)": ("Full_36", 36),
        }
        grid_folder, total_pads = mode_map.get(self.grid_mode, ("3x3", 9))
        packs_root = os.path.join(os.getcwd(), "Vault", "Presets", grid_folder, "Packs")
        os.makedirs(packs_root, exist_ok=True)
        return packs_root, grid_folder, total_pads

    def _auto_build_manifest_for_manual_folder(self, pack_name: str, pack_dir: str) -> bool:
        """
        If a user manually drops a folder of audio files into Vault/Presets/<grid_dir>/Packs/<pack_name>/,
        automatically builds a pack_manifest.json mapping up to `total_pads` audio files.
        """
        valid_exts = (".wav", ".mp3", ".flac", ".ogg")
        audio_files = sorted([
            f for f in os.listdir(pack_dir)
            if os.path.isfile(os.path.join(pack_dir, f)) and f.lower().endswith(valid_exts)
        ])
        if not audio_files:
            return False

        _, grid_folder, total_pads = self._get_active_packs_root()
        full_keys = [
            "q", "w", "e", "a", "s", "d", "z", "x", "c",
            "r", "t", "y", "f", "g", "h", "v", "b", "n",
            "u", "i", "o", "j", "k", "l", "m", ",", ".",
            "1", "2", "3", "4", "5", "6", "7", "8", "9"
        ]
        slots = {}
        for i in range(total_pads):
            if i < len(audio_files):
                fname = audio_files[i]
                rel_path = os.path.join("Vault", "Presets", grid_folder, "Packs", pack_name, fname).replace("\\", "/")
                clean_label = os.path.splitext(fname)[0].replace("_", " ").replace("-", " ").title()[:16]
            else:
                rel_path = ""
                clean_label = f"Pad {i + 1}"

            slots[f"slot_{i}"] = {
                "label": clean_label,
                "hotkey": full_keys[i],
                "sample": rel_path,
                "base_sample": rel_path,
                "pitch": 0.0,
                "bass": 0.0,
                "treble": 0.0,
                "volume": 1.0,
                "choke": False
            }

        manifest = {
            "pack_name": pack_name,
            "grid_mode": self.grid_mode,
            "pad_count": total_pads,
            "bpm": 120.0,
            "slots": slots
        }
        manifest_path = os.path.join(pack_dir, "pack_manifest.json")
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4)
            print(f"[PackScanner] Auto-indexed manual {self.grid_mode} folder '{pack_name}' ({len(audio_files)} files)")
            return True
        except Exception as e:
            print(f"[PackScanner] Failed to index manual folder '{pack_name}': {e}")
            return False

    def _discover_installed_packs(self) -> list[str]:
        """Scans Vault/Presets/<grid_dir>/Packs/ for built-in and manual packs."""
        packs_root, _, _ = self._get_active_packs_root()

        # Sync packs owned by the currently logged-in user (or Starter_Pack if signed out)
        try:
            from core.pack_generator import build_all_expansion_packs
            build_all_expansion_packs(
                self.grid_mode,
                unlocked_packs=self.auth_manager.get_unlocked_packs(),
                master_key_active=self.auth_manager.is_admin
            )
        except Exception as e:
            print(f"Pack plugin sync warning: {e}")

        found: list[str] = []
        for entry in sorted(os.listdir(packs_root)):
            pack_dir = os.path.join(packs_root, entry)
            if not os.path.isdir(pack_dir):
                continue

            manifest_path = os.path.join(pack_dir, "pack_manifest.json")
            if os.path.isfile(manifest_path) or self._auto_build_manifest_for_manual_folder(entry, pack_dir):
                found.append(entry)

        if "Starter_Pack" in found:
            found.remove("Starter_Pack")
            found.insert(0, "Starter_Pack")

        return ["Select Pack..."] + found

    def controller_refresh_packs(self):
        """Re-scans Vault/Presets/Packs/ for newly added manual folders and updates the dropdown."""
        current = self.pack_menu.get()
        updated = self._discover_installed_packs()
        self.pack_menu.configure(values=updated)
        if current in updated:
            self.pack_menu.set(current)
        else:
            self.pack_menu.set("Select Pack...")

    def controller_open_account_dialog(self):
        """Opens a modal dialog to Sign In, Register a new account, or Sign Out."""
        if self.auth_manager.current_user:
            role = "ADMIN" if self.auth_manager.is_admin else "Member"
            owned = ", ".join(sorted(self.auth_manager.get_unlocked_packs()))
            if messagebox.askyesno(
                "Account Session",
                f"Signed in as: {self.auth_manager.current_user} ({role})\n"
                f"Unlocked Packs: {'ALL (Master Key)' if self.auth_manager.is_admin else owned}\n\n"
                f"Do you want to sign out?",
                parent=self
            ):
                self.auth_manager.logout()
                self.account_btn.configure(text="👤 Sign In", fg_color="#3b3b58")
                self.controller_refresh_packs()
            return

        win = ctk.CTkToplevel(self)
        win.title("Aurras Account Sign In")
        win.geometry("340x240")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()

        ctk.CTkLabel(win, text="Aurras Studio Account", font=("Arial", 15, "bold"), text_color="cyan").pack(pady=(14, 4))
        ctk.CTkLabel(win, text="Sign in to sync your unlocked Sound Packs", font=("Arial", 11), text_color="gray").pack(pady=(0, 10))

        user_entry = ctk.CTkEntry(win, placeholder_text="Username", width=260, height=30)
        user_entry.pack(pady=4)
        pass_entry = ctk.CTkEntry(win, placeholder_text="Password", show="*", width=260, height=30)
        pass_entry.pack(pady=4)

        def _handle_auth(is_register: bool):
            u = user_entry.get()
            p = pass_entry.get()
            ok, msg = self.auth_manager.register_user(u, p) if is_register else self.auth_manager.login(u, p)
            if ok:
                badge = f"👑 {self.auth_manager.current_user}" if self.auth_manager.is_admin else f"👤 {self.auth_manager.current_user}"
                self.account_btn.configure(text=badge, fg_color="#1f538d")
                self.controller_refresh_packs()
                messagebox.showinfo("Signed In", msg, parent=win)
                win.destroy()
            else:
                messagebox.showerror("Authentication Failed", msg, parent=win)

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=14)
        ctk.CTkButton(btn_row, text="Sign In", width=120, fg_color="#1f538d", command=lambda: _handle_auth(False)).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Create Account", width=120, fg_color="#006655", command=lambda: _handle_auth(True)).pack(side="left", padx=6)

    def controller_redeem_product_key(self):
        """Prompts for a Sound Pack Product Key or Admin Master Key and saves it to the active account."""
        if not self.auth_manager.current_user:
            messagebox.showinfo("Sign In Required", "Please sign in or create an account first so your key is saved automatically.", parent=self)
            self.controller_open_account_dialog()
            if not self.auth_manager.current_user:
                return

        raw_key = simpledialog.askstring(
            "Redeem Sound Pack Key",
            f"Account: {self.auth_manager.current_user}\nEnter your Sound Pack Product Key (or Admin Master Key):",
            parent=self
        )
        if not raw_key or not raw_key.strip():
            return

        from core.pack_generator import discover_pack_plugins
        all_plugin_names = list(discover_pack_plugins().keys())
        ok, msg = self.auth_manager.redeem_product_key(raw_key, all_plugin_names)

        if ok:
            if self.auth_manager.is_admin:
                self.account_btn.configure(text=f"👑 {self.auth_manager.current_user}", fg_color="#8f6628")
            self.controller_refresh_packs()
            messagebox.showinfo("Pack Unlocked", msg, parent=self)
        else:
            messagebox.showerror("Invalid Key", msg, parent=self)

    def controller_browse_and_load_pack_folder(self):
        """
        Opens a folder dialog to load a Sound Pack directory.
        If an external folder of audio files is chosen, imports it into Vault/Presets/<grid_dir>/Packs/
        and auto-generates its pack_manifest.json before loading.
        """
        packs_root, grid_folder, _ = self._get_active_packs_root()
        selected_dir = filedialog.askdirectory(
            title=f"Select Sound Pack Folder to Load ({self.grid_mode})",
            initialdir=packs_root
        )
        if not selected_dir:
            return

        raw_folder_name = os.path.basename(os.path.normpath(selected_dir))
        pack_name = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_folder_name.replace(" ", "_")) or "Imported_Pack"
        target_pack_dir = os.path.join(packs_root, pack_name)

        # If user selected a folder outside Vault/Presets/<grid_dir>/Packs/, import its files into the Vault
        if os.path.abspath(selected_dir) != os.path.abspath(target_pack_dir):
            os.makedirs(target_pack_dir, exist_ok=True)
            valid_exts = (".wav", ".mp3", ".flac", ".ogg", ".json")
            for item in os.listdir(selected_dir):
                src_file = os.path.join(selected_dir, item)
                if os.path.isfile(src_file) and item.lower().endswith(valid_exts):
                    dst_file = os.path.join(target_pack_dir, item)
                    if os.path.abspath(src_file) != os.path.abspath(dst_file):
                        try:
                            shutil.copy2(src_file, dst_file)
                        except Exception as e:
                            print(f"[PackImport] Warning copying {item}: {e}")

        # Ensure a valid pack_manifest.json exists (or auto-build one from the folder's audio files)
        manifest_path = os.path.join(target_pack_dir, "pack_manifest.json")
        if not os.path.isfile(manifest_path):
            built = self._auto_build_manifest_for_manual_folder(pack_name, target_pack_dir)
            if not built:
                messagebox.showwarning(
                    "No Audio Found",
                    f"No supported audio files (.wav, .mp3, .flac, .ogg) were found in:\n{selected_dir}",
                    parent=self
                )
                return

        # Refresh dropdown, select the loaded pack, and load all pads
        updated_packs = self._discover_installed_packs()
        self.pack_menu.configure(values=updated_packs)
        self.pack_menu.set(pack_name)
        self.controller_load_sound_pack(pack_name)

    def controller_load_sound_pack(self, pack_name: str):
        """Loads all pad instruments (9, 18, 27, or 36) and BPM from the active grid's expansion pack."""
        if not pack_name or pack_name == "Select Pack...":
            return
        packs_root, _, total_pads = self._get_active_packs_root()
        manifest_path = os.path.join(packs_root, pack_name, "pack_manifest.json")
        if not os.path.exists(manifest_path):
            return

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            pack_bpm = float(manifest.get("bpm", 120.0))
            self.bpm_slider.set(pack_bpm)
            self.bpm_var.set(f"{int(pack_bpm)}")
            self._sync_transport_to_engine()

            pack_slots = manifest.get("slots", {})
            for i in range(total_pads):
                s = pack_slots.get(f"slot_{i}", {})
                self.config_loader.update_hotkey_slot(
                    slot_idx=i,
                    label=s.get("label", f"Pad {i + 1}"),
                    hotkey=s.get("hotkey", ""),
                    sample_path=s.get("sample", ""),
                    base_sample=s.get("base_sample", s.get("sample", "")),
                    pitch=float(s.get("pitch", 0.0)),
                    bass=float(s.get("bass", 0.0)),
                    treble=float(s.get("treble", 0.0)),
                    volume=float(s.get("volume", 1.0)),
                    choke=bool(s.get("choke", False))
                )

            self.slots_data = self.config_loader.get_hotkey_board_config().get("slots", {})
            self._preload_all_slot_samples()
            for i in range(len(self.buttons)):
                self._refresh_pad_button_text(i)
            self.controller_select_slot(0)
        except Exception as e:
            messagebox.showerror("Pack Load Error", f"Failed to load pack '{pack_name}':\n{e}", parent=self)

    def controller_save_sound_pack(self):
        """Packages all active pads in the current grid mode into Vault/Presets/<grid_dir>/Packs/<Pack_Name>."""
        raw_name = simpledialog.askstring(
            "Save Sound Pack",
            f"Enter a name for this {self.grid_mode} Sound Pack:",
            parent=self
        )
        if not raw_name or not raw_name.strip():
            return

        pack_name = re.sub(r"[^a-zA-Z0-9_\-]", "", raw_name.strip().replace(" ", "_"))
        if not pack_name:
            messagebox.showwarning("Invalid Name", "Please enter a valid alphanumeric pack name.", parent=self)
            return

        packs_root, grid_folder, total_pads = self._get_active_packs_root()
        pack_dir = os.path.join(packs_root, pack_name)
        os.makedirs(pack_dir, exist_ok=True)

        pack_slots = {}
        for i in range(total_pads):
            info = self._get_slot_dict(i)
            src_sample = info.get("sample", "")
            rel_dest_sample = ""

            if src_sample and os.path.exists(src_sample):
                ext = os.path.splitext(src_sample)[1] or ".wav"
                safe_label = re.sub(r"[^a-zA-Z0-9_\-]", "", info.get("label", f"pad_{i + 1}").replace(" ", "_")).lower()
                dest_filename = f"pad_{i + 1:02d}_{safe_label}{ext}"
                abs_dest = os.path.join(pack_dir, dest_filename)

                if os.path.abspath(src_sample) != os.path.abspath(abs_dest):
                    try:
                        shutil.copy2(src_sample, abs_dest)
                    except Exception as e:
                        print(f"[PackSave] Warning copying {src_sample}: {e}")

                rel_dest_sample = os.path.join("Vault", "Presets", grid_folder, "Packs", pack_name, dest_filename).replace("\\", "/")

            pack_slots[f"slot_{i}"] = {
                "label": info.get("label", f"Pad {i + 1}"),
                "hotkey": info.get("hotkey", ""),
                "sample": rel_dest_sample,
                "base_sample": rel_dest_sample,
                "pitch": 0.0,
                "bass": 0.0,
                "treble": 0.0,
                "volume": float(info.get("volume", 1.0)),
                "choke": bool(info.get("choke", False))
            }

        manifest = {
            "pack_name": pack_name,
            "grid_mode": self.grid_mode,
            "pad_count": total_pads,
            "bpm": float(self.bpm_slider.get()),
            "slots": pack_slots
        }

        manifest_path = os.path.join(pack_dir, "pack_manifest.json")
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=4)

            updated_packs = self._discover_installed_packs()
            self.pack_menu.configure(values=updated_packs)
            self.pack_menu.set(pack_name)
            messagebox.showinfo(
                "Sound Pack Saved",
                f"Saved {self.grid_mode} pack '{pack_name}' ({total_pads} pads) to:\nVault/Presets/{grid_folder}/Packs/{pack_name}",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Pack Save Error", f"Failed to save Sound Pack:\n{e}", parent=self)

    def controller_select_slot(self, index: int):
        """Highlights the chosen pad slot and populates the inspector panel."""
        self.selected_button_index = index
        self.slot_selector.set(f"Pad {index + 1}")
        self.editor_title.configure(text=f"Pad {index + 1} Inspector")

        for i, btn in enumerate(self.buttons):
            btn.configure(border_color="#00ffcc" if i == index else "#333333", border_width=2)

        info = self._get_slot_dict(index)

        self.sample_entry.delete(0, "end")
        self.sample_entry.insert(0, info.get("sample", ""))

        self.label_entry.delete(0, "end")
        self.label_entry.insert(0, info.get("label", f"Pad {index + 1}"))

        self.hotkey_entry.delete(0, "end")
        self.hotkey_entry.insert(0, info.get("hotkey", ""))

        pitch_val = float(info.get("pitch", 0.0))
        self.pitch_slider.set(pitch_val)
        self.pitch_lbl.configure(text=f"Pitch Shift: {pitch_val:+.1f} st")

        bass_val = int(round(float(info.get("bass", 0.0))))
        self.bass_slider.set(bass_val)
        self.bass_lbl.configure(text=f"Bass EQ: {bass_val:+d} dB")

        treble_val = int(round(float(info.get("treble", 0.0))))
        self.treble_slider.set(treble_val)
        self.treble_lbl.configure(text=f"Treble EQ: {treble_val:+d} dB")

        vol_val = float(info.get("volume", 1.0))
        vol_pct = int(round(vol_val * 100))
        self.vol_slider.set(vol_pct)
        self.vol_lbl.configure(text=f"Pad Volume: {vol_pct}%")

        dur_val = float(info.get("duration", 0.0))
        self.dur_slider.set(int(round(dur_val * 10.0)))
        if dur_val > 0.05:
            self.dur_lbl.configure(text=f"Stretch Timer: {dur_val:.1f}s (Elongate/Stretch)")
        else:
            # Show the base sample's natural duration if loaded in cache
            base_path = info.get("base_sample") or info.get("sample", "")
            nat_buf = self.beat_engine.load_sample(base_path, 0.0) if base_path else None
            if nat_buf is not None and len(nat_buf) > 0:
                nat_sec = len(nat_buf) / float(self.beat_engine.sample_rate)
                self.dur_lbl.configure(text=f"Stretch Timer: Original ({nat_sec:.2f}s)")
            else:
                self.dur_lbl.configure(text="Stretch Timer: Original Length")

        if info.get("choke", False):
            self.choke_switch.select()
        else:
            self.choke_switch.deselect()

    def controller_browse_sample(self):
        initial_dir = os.path.join(os.getcwd(), "Vault", "Presets", "Beats")
        os.makedirs(initial_dir, exist_ok=True)

        file_path = filedialog.askopenfilename(
            title=f"Select Instrument/Sample for Pad {self.selected_button_index + 1}",
            initialdir=initial_dir,
            filetypes=[("Audio Files", "*.wav *.mp3 *.flac *.ogg"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                rel_path = os.path.relpath(file_path, os.getcwd()).replace("\\", "/")
                if not rel_path.startswith(".."):
                    file_path = rel_path
            except ValueError:
                pass

            self.sample_entry.delete(0, "end")
            self.sample_entry.insert(0, file_path)

            # Reset tone/pitch sliders when loading a fresh base sample
            self.pitch_slider.set(0)
            self.pitch_lbl.configure(text="Pitch Shift: +0.0 st")
            self.bass_slider.set(0)
            self.bass_lbl.configure(text="Bass EQ: +0 dB")
            self.treble_slider.set(0)
            self.treble_lbl.configure(text="Treble EQ: +0 dB")
            self.dur_slider.set(0)
            self.dur_lbl.configure(text="Stretch Timer: Original Length")

            current_label = self.label_entry.get().strip()
            if not current_label or current_label.startswith("Pad ") or current_label.startswith("Slot "):
                clean_name = os.path.splitext(os.path.basename(file_path))[0].replace("_", " ").title()
                self.label_entry.delete(0, "end")
                self.label_entry.insert(0, clean_name[:16])

            self.controller_save_slot_config()

    def controller_reset_slot_tweaks(self):
        """Resets Pitch, Bass, Treble, Stretch Timer, and Volume to default and restores the base sample."""
        idx = self.selected_button_index
        info = self._get_slot_dict(idx)
        base_sample = info.get("base_sample") or info.get("sample", "")

        if base_sample:
            self.sample_entry.delete(0, "end")
            self.sample_entry.insert(0, base_sample)

        self.pitch_slider.set(0)
        self.pitch_lbl.configure(text="Pitch Shift: +0.0 st")

        self.bass_slider.set(0)
        self.bass_lbl.configure(text="Bass EQ: +0 dB")

        self.treble_slider.set(0)
        self.treble_lbl.configure(text="Treble EQ: +0 dB")

        self.dur_slider.set(0)
        self.dur_lbl.configure(text="Stretch Timer: Original Length")

        self.vol_slider.set(100)
        self.vol_lbl.configure(text="Pad Volume: 100%")

        self.controller_save_slot_config()

    def controller_save_slot_config(self):
        idx = self.selected_button_index
        info = self._get_slot_dict(idx)

        new_label = self.label_entry.get().strip() or f"Pad {idx + 1}"
        new_hotkey = self.hotkey_entry.get().strip().lower()
        entered_sample = self.sample_entry.get().strip()

        base_sample = info.get("base_sample") or entered_sample
        if entered_sample != info.get("sample"):
            base_sample = entered_sample

        new_pitch = float(self.pitch_slider.get())
        new_bass = float(self.bass_slider.get())
        new_treble = float(self.treble_slider.get())
        new_dur = int(self.dur_slider.get()) / 10.0
        new_vol = float(self.vol_slider.get()) / 100.0
        new_choke = bool(self.choke_switch.get() == 1)

        final_sample = entered_sample
        if base_sample and os.path.exists(base_sample):
            baked = self.beat_engine.render_and_save_tweaked_sample(
                source_path=base_sample,
                pitch_steps=new_pitch,
                bass_db=new_bass,
                treble_db=new_treble,
                target_duration=new_dur
            )
            if baked:
                final_sample = baked
                self.sample_entry.delete(0, "end")
                self.sample_entry.insert(0, final_sample)

        self.config_loader.update_hotkey_slot(
            slot_idx=idx,
            label=new_label,
            hotkey=new_hotkey,
            sample_path=final_sample,
            base_sample=base_sample,
            pitch=new_pitch,
            bass=new_bass,
            treble=new_treble,
            duration=new_dur,
            volume=new_vol,
            choke=new_choke
        )
        self.slots_data = self.config_loader.get_hotkey_board_config().get("slots", {})

        if final_sample and os.path.exists(final_sample):
            self.beat_engine.load_sample(final_sample, 0.0)

        self._refresh_pad_button_text(idx)

    def controller_trigger_slot(self, index: int):
        """Triggers the sample on Pad `index` via BeatEngine and flashes the pad button."""
        self.controller_select_slot(index)
        info = self._get_slot_dict(index)
        sample_path = info.get("sample", "")

        if not sample_path or not os.path.exists(sample_path):
            self.controller_browse_sample()
            return

        # If 'Capture Pad Hits to Text' is active, append this pad's key and refresh live playback
        if hasattr(self, "append_keys_switch") and self.append_keys_switch.get() == 1:
            bound_key = info.get("hotkey", "").strip().lower()
            if bound_key:
                self.song_script_entry.insert("end", bound_key)
                self._refresh_live_script_loop()

        # Pass pitch_steps=0.0 because any pitch/bass/treble tweaks are already baked into `sample_path`
        fired = self.beat_engine.trigger_pad(
            slot_idx=index,
            file_path=sample_path,
            pitch_steps=0.0,
            volume=float(info.get("volume", 1.0)),
            choke=bool(info.get("choke", False))
        )

        if fired:
            is_rec = self.beat_engine.is_recording and self.beat_engine.is_running
            flash_color = "#cc2222" if is_rec else "#00b894"
            self.buttons[index].configure(fg_color=flash_color)
            self.after(120, lambda idx=index: self._refresh_pad_button_text(idx))

    # =========================================================================
    # 4. LOOPER TRANSPORT CONTROLLERS & KEYBOARD HOOKS
    # =========================================================================

    def _on_bpm_slider_move(self, val):
        self.bpm_var.set(f"{int(float(val))}")
        self._sync_transport_to_engine()

    def _on_bpm_entry_submit(self, event=None):
        try:
            bpm = max(60.0, min(200.0, float(self.bpm_var.get())))
        except ValueError:
            bpm = 120.0
        self.bpm_var.set(f"{int(bpm)}")
        self.bpm_slider.set(bpm)
        self._sync_transport_to_engine()

    def _sync_transport_to_engine(self):
        try:
            bpm = float(self.bpm_slider.get())
        except Exception:
            bpm = 120.0

        bars_str = self.bars_menu.get().split(" ")[0]
        bars = int(bars_str) if bars_str.isdigit() else 2
        quantize = self.quantize_menu.get()
        metro = bool(self.metro_switch.get() == 1)

        self.beat_engine.configure_transport(bpm=bpm, bars=bars, quantize=quantize, metronome=metro)
        self.config_loader.update_looper_transport(bpm=bpm, bars=bars, quantize=quantize, metronome=metro)

    def controller_toggle_loop_play(self):
        status = self.beat_engine.get_status()
        if not status["is_running"]:
            self._sync_transport_to_engine()
            self.beat_engine.start_loop(record_overdub=False)
            self.loop_play_btn.configure(text="⏹ Stop Loop", fg_color="#d97736", hover_color="#e68a00")
        else:
            self.beat_engine.stop_loop()
            self.loop_play_btn.configure(text="▶ Start Loop", fg_color="#1f538d", hover_color="#2968b0")
            self.loop_rec_btn.configure(text="⏺ Overdub Rec", fg_color="#661111")
            self.loop_progress.set(0.0)
            self.beat_counter_lbl.configure(text="BAR 1 : BEAT 1")

    def controller_toggle_loop_record(self):
        status = self.beat_engine.get_status()
        new_rec_state = not status["is_recording"]
        self._sync_transport_to_engine()
        self.beat_engine.set_recording(new_rec_state)

        if new_rec_state:
            self.loop_play_btn.configure(text="⏹ Stop Loop", fg_color="#d97736", hover_color="#e68a00")
            self.loop_rec_btn.configure(text="⏺ Recording ON", fg_color="#ff2222", hover_color="#cc0000")
        else:
            self.loop_rec_btn.configure(text="⏺ Overdub Rec", fg_color="#661111", hover_color="#991111")

    def controller_undo_overdub(self):
        self.beat_engine.undo_overdub()

    def controller_clear_loop(self):
        self.beat_engine.clear_loop()

    def controller_export_loop_wav(self):
        initial_dir = os.path.join(os.getcwd(), "Vault", "Presets", "Beats")
        os.makedirs(initial_dir, exist_ok=True)
        default_name = f"beat_loop_{int(self.bpm_slider.get())}bpm_{datetime.now().strftime('%H%M%S')}.wav"

        out_path = filedialog.asksaveasfilename(
            title="Save Layered Beat Loop",
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=".wav",
            filetypes=[("WAV Audio (*.wav)", "*.wav")]
        )
        if out_path:
            saved = self.beat_engine.export_loop(out_path)
            if saved:
                messagebox.showinfo("Loop Exported", f"Beat loop saved to:\n{saved}", parent=self)
            else:
                messagebox.showwarning("Empty Loop", "Record some pad hits into the loop first before exporting.", parent=self)

    def controller_send_loop_to_sequencer(self):
        loop_dir = os.path.join(os.getcwd(), "Vault", "Audio", "Loops")
        os.makedirs(loop_dir, exist_ok=True)
        bpm = int(self.bpm_slider.get())
        bars = self.bars_menu.get().split(" ")[0]
        filename = f"Beat_{bpm}BPM_{bars}Bars_{datetime.now().strftime('%H%M%S')}.wav"
        out_path = os.path.join(loop_dir, filename)

        saved = self.beat_engine.export_loop(out_path)
        if not saved:
            messagebox.showwarning(
                "Loop Empty",
                "The loop buffer is currently empty.\n\nClick '⏺ Overdub Rec' and play your pads to record a beat first!",
                parent=self
            )
            return

        if self.on_export_to_sequencer:
            track_title = f"Beat Loop ({bpm} BPM)"
            self.on_export_to_sequencer(saved, track_title)
            messagebox.showinfo("Sent to Sequencer", f"Added '{track_title}' to the Sequencer timeline!", parent=self)

    def _bind_keyboard_triggers(self):
        root = self.winfo_toplevel()
        root.bind("<KeyPress>", self._on_global_key_press, add="+")

    def _on_global_key_press(self, event):
        # Ignore key presses when typing inside an Entry widget
        focused = self.focus_get()
        if focused is not None and (
            isinstance(focused, ctk.CTkEntry) or focused.winfo_class() in ("Entry", "TEntry")
        ):
            return

        pressed_char = event.keysym.lower()
        key_aliases = {"comma": ",", "period": "."}
        pressed_char = key_aliases.get(pressed_char, pressed_char)

        if hasattr(self, "append_keys_switch") and self.append_keys_switch.get() == 1:
            if pressed_char == "space":
                self.song_script_entry.insert("end", " ")
                self._refresh_live_script_loop()
                return
            elif pressed_char == "backspace":
                current_txt = self.song_script_entry.get()
                if current_txt:
                    self.song_script_entry.delete(len(current_txt) - 1, "end")
                    self._refresh_live_script_loop()
                return

        _, _, total_pads = self._get_grid_dimensions()
        for i in range(total_pads):
            info = self._get_slot_dict(i)
            bound_key = info.get("hotkey", "").strip().lower()
            if bound_key and pressed_char == bound_key:
                self.controller_trigger_slot(i)
                break

    def _poll_looper_transport(self):
        if not self.winfo_exists():
            return

        status = self.beat_engine.get_status()
        if status["is_running"]:
            self.beat_counter_lbl.configure(
                text=f"BAR {status['bar']} : BEAT {status['beat']}",
                text_color="#ff4444" if status["is_recording"] else "#00ffcc"
            )
            self.loop_progress.set(status["progress"])

        self.after(35, self._poll_looper_transport)