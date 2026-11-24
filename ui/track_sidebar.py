import customtkinter as ctk
from typing import List, Sequence, Callable, Optional, Dict

def sec_to_timecode(seconds: float) -> str:
    """Universal Helper: Converts seconds into strict M:SS.ss format with millisecond precision."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}:{secs:05.2f}"

def timecode_to_sec(time_str: str) -> float:
    """Universal Helper: Converts M:SS.ss format string into float seconds with validation."""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(time_str)
    except ValueError:
        return 0.0

class TimelineTrack:
    """
    Data structure representing an individual audio track lane on the timeline sequencer.
    """
    def __init__(self, track_id: int, name: str):
        self.track_id = track_id
        self.name = name
        self.volume = 1.0
        self.muted = False
        self.soloed = False
        self.looped = False
        self.clips: List[Dict] = []

class TrackSidebar(ctk.CTkScrollableFrame):
    """
    Dedicated sidebar component managing track cards, routing controls, 
    and track parameters independently from the timeline canvas.
    """
    def __init__(self, master, tracks: Sequence[TimelineTrack], on_select_track: Callable[[int], None], on_redraw: Callable[[], None], **kwargs):
        super().__init__(master, label_text="Tracks", fg_color="#141414", **kwargs)
        self.tracks = tracks
        self.on_select_track = on_select_track
        self.on_redraw = on_redraw
        self.track_cards: List[ctk.CTkFrame] = []
        self.selected_track_idx: Optional[int] = None

    def refresh_tracks(self):
        for card in self.track_cards:
            card.destroy()
        self.track_cards.clear()

        for track in self.tracks:
            self._build_track_card_ui(track)

        if self.tracks and self.selected_track_idx is not None:
            self._set_selection_visual(min(self.selected_track_idx, len(self.tracks) - 1))

    def _build_track_card_ui(self, track: TimelineTrack):
        card = ctk.CTkFrame(self, fg_color="#222222", corner_radius=6)
        card.pack(fill="x", pady=5, padx=5)
        self.track_cards.append(card)

        card.bind("<Button-1>", lambda e, tid=track.track_id: self.select_track(tid))

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=6, pady=(8, 4))
        top_row.bind("<Button-1>", lambda e, tid=track.track_id: self.select_track(tid))
        
        top_row.grid_columnconfigure(0, weight=1)
        top_row.grid_columnconfigure(1, weight=0)
        top_row.grid_columnconfigure(2, weight=0)
        top_row.grid_columnconfigure(3, weight=0)

        name_var = ctk.StringVar(value=track.name)
        name_entry = ctk.CTkEntry(
            top_row, textvariable=name_var, width=95, height=24, 
            font=("Arial", 11, "bold"), fg_color="#181818", border_color="#333333"
        )
        name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        
        def on_name_change(*args):
            track.name = name_var.get()
            self.on_redraw()
        name_var.trace_add("write", on_name_change)

        def toggle_loop():
            track.looped = not track.looped
            loop_btn.configure(fg_color="#1f538d" if track.looped else "#333333")

        loop_btn = ctk.CTkButton(
            top_row, text="⟳", width=24, height=22, 
            fg_color="#1f538d" if track.looped else "#333333", 
            font=("Arial", 11, "bold"), command=toggle_loop
        )
        loop_btn.grid(row=0, column=1, padx=1)

        def toggle_solo():
            track.soloed = not track.soloed
            solo_btn.configure(fg_color="#b85c00" if track.soloed else "#333333")

        solo_btn = ctk.CTkButton(
            top_row, text="S", width=24, height=22, 
            fg_color="#b85c00" if track.soloed else "#333333", 
            font=("Arial", 10, "bold"), command=toggle_solo
        )
        solo_btn.grid(row=0, column=2, padx=1)

        def toggle_mute():
            track.muted = not track.muted
            mute_btn.configure(fg_color="#8b0000" if track.muted else "#333333")

        mute_btn = ctk.CTkButton(
            top_row, text="M", width=24, height=22, 
            fg_color="#8b0000" if track.muted else "#333333", 
            font=("Arial", 10, "bold"), command=toggle_mute
        )
        mute_btn.grid(row=0, column=3, padx=1)

        pos_row = ctk.CTkFrame(card, fg_color="transparent")
        pos_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(pos_row, text="Pos:", font=("Arial", 10), text_color="gray").pack(side="left", padx=(0, 4))

        current_pos_sec = 0.0
        if track.clips:
            start_x = track.clips[0].get("start_x", 50)
            current_pos_sec = max(0.0, (start_x - 50) / 10.0)

        pos_var = ctk.StringVar(value=sec_to_timecode(current_pos_sec))
        pos_entry = ctk.CTkEntry(
            pos_row, textvariable=pos_var, width=70, height=22, 
            font=("Consolas", 10), fg_color="#181818"
        )
        pos_entry.pack(side="left", padx=2)

        def on_position_submit(event=None):
            new_sec = timecode_to_sec(pos_var.get())
            new_start_x = 50 + int(new_sec * 10.0)
            if track.clips:
                clip = track.clips[0]
                duration = clip.get("duration", 3.0)
                clip["start_x"] = new_start_x
                clip["end_x"] = new_start_x + int(duration * 10.0)
            self.on_redraw()

        pos_entry.bind("<Return>", on_position_submit)
        pos_entry.bind("<FocusOut>", on_position_submit)

        ctk.CTkButton(
            card, text="Effects (Pitch / EQ)", height=24, fg_color="#1f538d", font=("Arial", 11),
            command=lambda: print(f"Opening effects for {track.name}")
        ).pack(fill="x", padx=8, pady=(4, 8))

    def select_track(self, track_idx: int):
        self.selected_track_idx = track_idx
        self._set_selection_visual(track_idx)
        self.on_select_track(track_idx)

    def _set_selection_visual(self, track_idx: int):
        for idx, card in enumerate(self.track_cards):
            if idx == track_idx:
                card.configure(fg_color="#2b4c7e")
            else:
                card.configure(fg_color="#222222")