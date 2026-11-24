import os
import time
import copy
import wave
import librosa
import threading
import numpy as np
import tkinter as tk
import customtkinter as ctk
from typing import List, Dict, Optional
from core.audio_engine import AudioEngine
from datetime import datetime
from ui.track_sidebar import TrackSidebar, TimelineTrack, sec_to_timecode, timecode_to_sec
from ui.sound_board import SoundBoardPanel
     
        
class TimelineViewFrame(ctk.CTkFrame):
    """
    Multi-Track DAW Sequencer interface featuring clean fixed-width side panel layouts,
    transport controls, mouse wheel zooming, model-driven clip dragging, region selection, 
    and undo support.
    """
    
    def __init__(self, master, audio_engine: Optional[AudioEngine] = None, open_project_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.audio_engine = audio_engine if audio_engine else AudioEngine()
        self.open_project_callback = open_project_callback

        self.tracks: List[TimelineTrack] = []
        self.is_recording = False
        self.recording_start_time: Optional[float] = None
        self.zoom_scale = 1.0  # Timeline Zoom Scaling Factor

        # Undo History Stack
        self.undo_stack: List[List[TimelineTrack]] = []

        # Drag-and-Drop State tracking variables
        self._dragging_clip_id: Optional[str] = None
        self._dragging_clip: Optional[Dict] = None
        self._drag_start_x: int = 0

        # Region Selection State variables
        self._selection_start_x: Optional[int] = None
        self._selection_end_x: Optional[int] = None
        self._selected_region_track_idx: Optional[int] = None

        # Track Selection State
        self.selected_track_idx: Optional[int] = 0

        # Configure primary layout grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_transport_bar()
        self._build_workspace_layout()

        self._start_meter_polling()

        # Project Metadata Attributes
        self.project_name: Optional[str] = None
        self.project_vault_dir: Optional[str] = None
        
        # Create default initial track
        self.controller_add_track("Audio 1")

    def get_recent_mic_peak(self):
        if hasattr(self.audio_engine, "get_recent_mic_peak"):
            return self.audio_engine.get_recent_mic_peak()
        return []

    def _build_transport_bar(self):
        self.transport_frame = ctk.CTkFrame(self, height=50, fg_color="#181818", corner_radius=6)
        self.transport_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        btn_config = {"width": 35, "height": 30, "fg_color": "#333333", "hover_color": "#444444"}
        
        ctk.CTkButton(self.transport_frame, text="▶", **btn_config, command=self.controller_play).pack(side="left", padx=3)
        ctk.CTkButton(self.transport_frame, text="⏹", **btn_config, command=self.controller_stop).pack(side="left", padx=3)
        
        rec_config = btn_config.copy()
        rec_config.update({"fg_color": "darkred", "hover_color": "red"})
        self.record_btn = ctk.CTkButton(self.transport_frame, text="⏺", **rec_config, command=self.controller_toggle_record)
        self.record_btn.pack(side="left", padx=3)

        def on_mute_rec_toggle():
            mute_val = self.mute_rec_switch.get() == 1
            if hasattr(self.audio_engine, "set_mute_output"):
                self.audio_engine.set_mute_output(mute_val)

        self.mute_rec_switch = ctk.CTkSwitch(
            self.transport_frame, text="Mute on Rec", font=("Arial", 10), 
            text_color="gray", progress_color="darkred",
            command=on_mute_rec_toggle
        )
        self.mute_rec_switch.select()
        self.mute_rec_switch.pack(side="left", padx=10)

        ctk.CTkButton(
            self.transport_frame, text="↶ Undo", fg_color="#444444", hover_color="#555555",
            command=self.controller_undo, width=65, height=30
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            self.transport_frame, text="📋 Copy Region", fg_color="#b85c00", hover_color="#d97736",
            command=self.controller_copy_selection_to_next_track, height=30
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.transport_frame, text="✂ Delete Region", fg_color="#8b0000", hover_color="#a80000",
            command=self.controller_delete_selected_region, height=30
        ).pack(side="left", padx=5)
        
        self.timecode_label = ctk.CTkLabel(
            self.transport_frame, text="0:00.00", font=("Consolas", 13, "bold"), text_color="cyan"
        )
        self.timecode_label.pack(side="left", padx=10)

        self.add_track_btn = ctk.CTkButton(
            self.transport_frame, text="+ Add Track", fg_color="#1f538d", 
            command=lambda: self.controller_add_track(f"Audio {len(self.tracks) + 1}")
        )
        self.add_track_btn.pack(side="right", padx=10)

    def _on_canvas_mouse_motion(self, event):
        self.timeline_canvas.delete("playhead")
        mouse_x = max(50, event.x)
        
        self.timeline_canvas.create_line(
            mouse_x, 0, mouse_x, self.timeline_canvas.winfo_height(), fill="white", width=1.5, tags="playhead"
        )
        self.timeline_canvas.create_polygon(
            mouse_x - 6, 0, mouse_x + 6, 0, mouse_x + 6, 10, mouse_x, 16, mouse_x - 6, 10,
            fill="white", outline="#cccccc", tags="playhead"
        )

    def _on_mouse_wheel(self, event):
        if event.delta > 0:
            self.zoom_scale = min(4.0, self.zoom_scale * 1.15)
        else:
            self.zoom_scale = max(0.25, self.zoom_scale / 1.15)
            
        self._redraw_all_clips()
    
    def _build_workspace_layout(self):
        self.workspace_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        self.workspace_frame.grid_columnconfigure(0, minsize=210, weight=0)
        self.workspace_frame.grid_columnconfigure(1, weight=1)
        self.workspace_frame.grid_columnconfigure(2, minsize=85, weight=0)
        
        # Row 0: Main panels (Vault, Tracks, Canvas, Master Meters)
        # Row 1: Bottom Sound Board / Channel Strip Rack
        self.workspace_frame.grid_rowconfigure(0, weight=1)
        self.workspace_frame.grid_rowconfigure(1, weight=0)

        # --- ADJUSTABLE VERTICAL PANE FOR LEFT COLUMN ---
        self.left_pane = tk.PanedWindow(
            self.workspace_frame, orient=tk.VERTICAL, 
            bg="#1a1a1a", sashwidth=4, bd=0
        )
        self.left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # 1. Vault Explorer (Top of Left Column)
        from ui.vault_explorer import VaultExplorerSidebar
        self.vault_explorer = VaultExplorerSidebar(
            self.left_pane,
            on_project_open_callback=lambda path: self.open_project_callback(path) if self.open_project_callback else None,
            on_audio_load_callback=lambda path: self.controller_load_audio_file(path)
        )
        self.left_pane.add(self.vault_explorer, height=100)

        # 2. Dedicated Track Sidebar Module (Bottom of Left Column)
        self.track_sidebar_wrapper = ctk.CTkFrame(self.left_pane, fg_color="transparent")
        self.track_sidebar = TrackSidebar(
            self.track_sidebar_wrapper,
            tracks=self.tracks,
            on_select_track=self._on_track_selected_from_sidebar,
            on_redraw=self._redraw_all_clips
        )
        self.track_sidebar.pack(fill="both", expand=True)
        self.left_pane.add(self.track_sidebar_wrapper, height=250)

        # --- CENTER TIMELINE PANE (With Scrollbars) ---
        self.center_pane_frame = ctk.CTkFrame(self.workspace_frame, fg_color="#1a1a1a")
        self.center_pane_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        
        self.center_pane_frame.grid_rowconfigure(0, weight=1)
        self.center_pane_frame.grid_columnconfigure(0, weight=1)

        self.timeline_canvas = ctk.CTkCanvas(self.center_pane_frame, bg="#1a1a1a", highlightthickness=0)
        
        # Build Scrollbars
        self.v_scroll = ctk.CTkScrollbar(self.center_pane_frame, orientation="vertical", command=self.timeline_canvas.yview)
        self.h_scroll = ctk.CTkScrollbar(self.center_pane_frame, orientation="horizontal", command=self.timeline_canvas.xview)
        
        self.timeline_canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        
        # Grid placement
        self.timeline_canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.timeline_canvas.bind("<Motion>", self._on_canvas_mouse_motion)
        self._draw_timeline_grid()

        # --- BIND MOUSE EVENTS FOR DRAGGING AND SELECTION ---
        self.timeline_canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.timeline_canvas.bind("<Button-1>", self._on_canvas_click)
        self.timeline_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.timeline_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        self.timeline_canvas.bind("<Control-Button-1>", self._on_selection_start)
        self.timeline_canvas.bind("<Control-B1-Motion>", self._on_selection_drag)
        self.timeline_canvas.bind("<Control-ButtonRelease-1>", self._on_selection_release)

        # --- BOTTOM SOUND BOARD / EFFECTS RACK ---
        self.sound_board = SoundBoardPanel(
            self.workspace_frame, 
            on_parameter_change=lambda params: self.audio_engine.update_live_stream_parameters(params)
        )
        self.sound_board.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _start_meter_polling(self):
        """Continuous low-overhead loop to feed live engine peaks into the UI meters."""
        if not self.winfo_exists():
            return
        
        if hasattr(self.audio_engine, "stage_peaks"):
            self.sound_board.update_all_meters(self.audio_engine.stage_peaks)
        
        # Decay peaks slightly to simulate realistic LED falloff if engine stops
        for key in self.audio_engine.stage_peaks:
            self.audio_engine.stage_peaks[key] *= 0.85 

        self.after(50, self._start_meter_polling)    

    def _on_track_selected_from_sidebar(self, track_idx: int):
        """Handles track selection events from the sidebar and updates the active track in the audio engine."""
        self.selected_track_idx = track_idx
        if 0 <= track_idx < len(self.tracks):
            self.sound_board.set_active_track(self.tracks[track_idx])
        else:
            self.sound_board.set_active_track(None)

    def _push_undo_state(self):
        state_snapshot = []
        for track in self.tracks:
            track_copy = TimelineTrack(track.track_id, track.name)
            track_copy.volume = track.volume
            track_copy.muted = track.muted
            track_copy.soloed = track.soloed
            track_copy.clips = copy.deepcopy(track.clips)
            state_snapshot.append(track_copy)
        self.undo_stack.append(state_snapshot)
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def _on_canvas_click(self, event):
        track_idx = max(0, (event.y - 45) // 80)
        
        if track_idx < len(self.tracks):
            track = self.tracks[track_idx]
            y_top = 45 + (track_idx * 80)
            y_bottom = y_top + 70
            
            if y_top <= event.y <= y_bottom:
                for clip in track.clips:
                    x_start = float(clip.get("start_x", 50.0))
                    x_end = float(clip.get("end_x", x_start + 50.0))
                    
                    if x_start <= event.x <= x_end:
                        self._dragging_clip = clip
                        self._dragging_clip_id = clip.get("uid")
                        self._drag_start_x = event.x
                        self.track_sidebar.select_track(track_idx)
                        return

        if track_idx < len(self.tracks):
            self.track_sidebar.select_track(track_idx)

    def _on_canvas_drag(self, event):
        if self._dragging_clip is None:
            return
            
        dx = event.x - self._drag_start_x
        self._drag_start_x = event.x
        
        current_start = float(self._dragging_clip.get("start_x", 50.0))
        duration = float(self._dragging_clip.get("duration", 3.0))
        pixels_per_sec = 10.0 * self.zoom_scale
        width = duration * pixels_per_sec
        
        new_start = max(50.0, current_start + float(dx))
        self._dragging_clip["start_x"] = new_start
        self._dragging_clip["end_x"] = new_start + width
                
        self._redraw_all_clips()

    def _on_canvas_release(self, event):
        if self._dragging_clip is not None:
            self._push_undo_state()
            self._redraw_all_clips()
            self.track_sidebar.refresh_tracks()
            if self.selected_track_idx is not None:
                self.track_sidebar.select_track(self.selected_track_idx)
            
        self._dragging_clip = None
        self._dragging_clip_id = None

    def controller_undo(self):
        if not self.undo_stack:
            return

        previous_state = self.undo_stack.pop()
        self.tracks = previous_state
        self.track_sidebar.tracks = self.tracks
        self.track_sidebar.refresh_tracks()

        if self.tracks:
            self.track_sidebar.select_track(min(self.selected_track_idx or 0, len(self.tracks) - 1))
        
        self.timeline_canvas.delete("selection_box")
        self._redraw_all_clips()

    def _draw_timeline_grid(self):
        self.timeline_canvas.update_idletasks()
        width = self.timeline_canvas.winfo_width() or 1200
        height = self.timeline_canvas.winfo_height() or 500
        
        self.timeline_canvas.delete("grid")
        
        pixels_per_sec = 10 * self.zoom_scale
        max_duration_sec = max(600, width // max(1, int(pixels_per_sec)))
        
        if self.zoom_scale >= 2.5:
            major_sec = 0.5
            subdivisions = 2
        elif self.zoom_scale >= 1.2:
            major_sec = 1.0
            subdivisions = 4
        elif self.zoom_scale >= 0.6:
            major_sec = 5.0
            subdivisions = 5
        elif self.zoom_scale >= 0.3:
            major_sec = 15.0
            subdivisions = 3
        else:
            major_sec = 30.0
            subdivisions = 3

        step_sec = major_sec / subdivisions
        base_major_width = max(0.5, 1.5 / max(0.5, self.zoom_scale))
        base_sub_width = max(0.5, 1.0 / max(0.5, self.zoom_scale))

        current_sec = 0.0
        i = 0
        last_label_x = -100.0

        while current_sec <= max_duration_sec:
            x = 50 + int(current_sec * pixels_per_sec)
            is_major = (i % subdivisions == 0)
            
            if is_major:
                line_color = "#555555"
                line_width = base_major_width
                tick_height = 12
            else:
                line_color = "#2a2a2a"
                line_width = base_sub_width
                tick_height = 6

            lane_line_color = "#2a2a2a" if is_major else "#1f1f1f"
            self.timeline_canvas.create_line(x, 0, x, height, fill=lane_line_color, width=line_width, tags="grid")
            self.timeline_canvas.create_line(x, 0, x, tick_height, fill=line_color, width=line_width, tags="grid")
            
            if is_major and (x - last_label_x >= 65):
                time_str = sec_to_timecode(current_sec)
                self.timeline_canvas.create_text(x + 3, 12, text=time_str, anchor="nw", fill="gray", font=("Arial", 8), tags="grid")
                last_label_x = x

            i += 1
            current_sec = i * step_sec

        for j in range(10):
            y = 40 + (j * 80)
            self.timeline_canvas.create_line(0, y, 50 + int(max_duration_sec * pixels_per_sec), y, fill="#222222", width=1.0, tags="grid")

    def controller_delete_selected_region(self):
        if self._selection_start_x is None or self._selection_end_x is None or self._selected_region_track_idx is None:
            return

        self._push_undo_state()
        
        x1 = min(self._selection_start_x, self._selection_end_x)
        x2 = max(self._selection_start_x, self._selection_end_x)
        track_idx = self._selected_region_track_idx

        if track_idx >= len(self.tracks):
            return

        track = self.tracks[track_idx]
        new_clips = []
        pixels_per_sec = 10.0 * self.zoom_scale
        
        # Ensure our temp trimmed directory exists
        import os, time
        os.makedirs(os.path.join(os.getcwd(), "assets", "temp", "trimmed"), exist_ok=True)

        for clip in track.clips:
            c_start = float(clip.get("start_x", 50.0))
            c_end = float(clip.get("end_x", c_start + 50.0))
            c_path = clip.get("path", "")
            c_dur = float(clip.get("duration", 3.0))

            if not c_path or not os.path.exists(c_path):
                new_clips.append(clip)
                continue

            # Case 1: Clip is entirely inside the deletion zone -> DESTROY
            if c_start >= x1 and c_end <= x2:
                continue
                
            # Case 2: Deletion zone is entirely inside the clip -> SPLIT AND TRIM BOTH
            elif c_start < x1 and c_end > x2:
                # 1. Left surviving piece (Trim from 0.0 to the cut point)
                left_dur = (x1 - c_start) / pixels_per_sec
                left_path = os.path.join(os.getcwd(), "assets", "temp", "trimmed", f"trim_L_{int(time.time()*1000)}.wav")
                try:
                    self.audio_engine.trim_audio(c_path, left_path, 0.0, left_dur)
                    left_clip = copy.deepcopy(clip)
                    left_clip["end_x"] = x1
                    left_clip["duration"] = left_dur
                    left_clip["path"] = left_path
                    new_clips.append(left_clip)
                except Exception as e:
                    print(f"Error trimming left: {e}")
                
                time.sleep(0.02) # Ensure a unique timestamp for the next file

                # 2. Right surviving piece (Trim from cut point to the end)
                right_start_rel = (x2 - c_start) / pixels_per_sec
                right_dur = c_dur - right_start_rel
                right_path = os.path.join(os.getcwd(), "assets", "temp", "trimmed", f"trim_R_{int(time.time()*1000)}.wav")
                try:
                    self.audio_engine.trim_audio(c_path, right_path, right_start_rel, c_dur)
                    right_clip = copy.deepcopy(clip)
                    right_clip["uid"] = f"clip_uid_{int(time.time()*1000)}_r"
                    right_clip["start_x"] = x2
                    right_clip["duration"] = right_dur
                    right_clip["path"] = right_path
                    new_clips.append(right_clip)
                except Exception as e:
                    print(f"Error trimming right: {e}")

            # Case 3: Deletion zone overlaps the right tail -> TRIM TAIL
            elif c_start < x1 and c_end > x1:
                left_dur = (x1 - c_start) / pixels_per_sec
                left_path = os.path.join(os.getcwd(), "assets", "temp", "trimmed", f"trim_tail_{int(time.time()*1000)}.wav")
                try:
                    self.audio_engine.trim_audio(c_path, left_path, 0.0, left_dur)
                    clip["end_x"] = x1
                    clip["duration"] = left_dur
                    clip["path"] = left_path
                    new_clips.append(clip)
                except Exception:
                    pass

            # Case 4: Deletion zone overlaps the left head -> TRIM HEAD
            elif c_start < x2 and c_end > x2:
                right_start_rel = (x2 - c_start) / pixels_per_sec
                right_dur = c_dur - right_start_rel
                right_path = os.path.join(os.getcwd(), "assets", "temp", "trimmed", f"trim_head_{int(time.time()*1000)}.wav")
                try:
                    self.audio_engine.trim_audio(c_path, right_path, right_start_rel, c_dur)
                    clip["start_x"] = x2
                    clip["duration"] = right_dur
                    clip["path"] = right_path
                    new_clips.append(clip)
                except Exception:
                    pass

            # Case 5: Clip is completely outside the deletion zone -> KEEP INTACT
            else:
                new_clips.append(clip)

        # Apply the survivor list back to the track
        track.clips = new_clips
        
        # Clear the blue selection UI box
        self.timeline_canvas.delete("selection_box")
        self._selection_start_x = None
        self._selection_end_x = None
        
        # Trigger the renderer
        self._redraw_all_clips()

    def _on_selection_start(self, event):
        self._selection_start_x = event.x
        self._selection_end_x = event.x
        self._selected_region_track_idx = max(0, (event.y - 45) // 80)
        self.timeline_canvas.delete("selection_box")

    def _on_selection_drag(self, event):
        if self._selection_start_x is None:
            return
        self._selection_end_x = max(0, event.x)
        
        track_idx = self._selected_region_track_idx or 0
        y_top = 45 + (track_idx * 80)
        y_bottom = y_top + 70
        
        x1 = min(self._selection_start_x, self._selection_end_x)
        x2 = max(self._selection_start_x, self._selection_end_x)
        
        self.timeline_canvas.delete("selection_box")
        self.timeline_canvas.create_rectangle(
            x1, y_top, x2, y_bottom,
            fill="#1f538d", stipple="gray50", outline="#00ffff", width=1,
            tags="selection_box"
        )

    def _on_selection_release(self, event):
        if self._selection_start_x is not None:
            self._selection_end_x = max(0, event.x)

    def controller_copy_selection_to_next_track(self):
        if self._selection_start_x is None or self._selection_end_x is None or self._selected_region_track_idx is None:
            return

        self._push_undo_state()
        x1 = min(self._selection_start_x, self._selection_end_x)
        x2 = max(self._selection_start_x, self._selection_end_x)
        
        if (x2 - x1) < 10:
            return

        source_track_idx = self._selected_region_track_idx
        if source_track_idx >= len(self.tracks):
            return

        source_track = self.tracks[source_track_idx]
        target_clip = None
        for clip in source_track.clips:
            if not (x2 < clip["start_x"] or x1 > clip["end_x"]):
                target_clip = clip
                break

        if not target_clip or not target_clip.get("path") or not os.path.exists(target_clip.get("path", "")):
            return

        base_name = source_track.name.split(" (Copy")[0]
        new_track_name = f"{base_name} (Copy)"
        
        self.controller_add_track(new_track_name)
        target_track = self.tracks[-1]

        clip_start_x = target_clip["start_x"]
        pixels_per_sec = 10 * self.zoom_scale
        relative_start_sec = max(0.0, (x1 - clip_start_x) / pixels_per_sec)
        clip_duration = (x2 - x1) / pixels_per_sec
        relative_end_sec = relative_start_sec + clip_duration

        os.makedirs(os.path.join(os.getcwd(), "assets", "temp", "trimmed"), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trimmed_path = os.path.join(os.getcwd(), "assets", "temp", "trimmed", f"region_{timestamp}.wav")
        
        try:
            self.audio_engine.trim_audio(target_clip["path"], trimmed_path, relative_start_sec, relative_end_sec)
        except Exception as e:
            trimmed_path = target_clip["path"]

        clip_uid = f"clip_uid_{int(time.time()*1000)}"
        new_clip = {
            "uid": clip_uid,
            "name": new_track_name,
            "path": trimmed_path,
            "duration": clip_duration,
            "start_x": x1,
            "end_x": x2
        }
        
        target_track.clips = [new_clip]
        self.timeline_canvas.delete("selection_box")
        self._selection_start_x = None
        self._selection_end_x = None
        self._redraw_all_clips()

    def controller_add_track(self, name: str):
        track_id = len(self.tracks)
        track = TimelineTrack(track_id, name)
        self.tracks.append(track)
        
        if hasattr(self, 'sound_board'):
            self.sound_board.add_channel(name)
        
        self._push_undo_state()

        self.track_sidebar.tracks = self.tracks
        self.track_sidebar.refresh_tracks()
        self.track_sidebar.select_track(track_id)

    def controller_load_audio_file(self, file_path: str):
        if file_path and os.path.exists(file_path):
            if not self.tracks:
                self.controller_add_track("Audio 1")
            target_idx = self.selected_track_idx or 0
            track = self.tracks[target_idx]

            duration = 3.0
            try:
                with wave.open(file_path, 'rb') as wf:
                    duration = wf.getnframes() / float(wf.getframerate())
            except Exception:
                pass

            clip_uid = f"clip_uid_{int(time.time()*1000)}"
            new_clip = {
                "uid": clip_uid,
                "name": os.path.basename(file_path),
                "path": file_path,
                "duration": duration,
                "start_x": 50,
                "end_x": 50 + int(duration * 10 * self.zoom_scale)
            }
            track.clips = [new_clip]
            self._redraw_all_clips()
            print(f"Controller Action: Loaded audio file to track '{track.name}' -> {file_path}")

    def controller_play(self):
        print("Controller Action: Starting Live DSP Playback...")
        
        has_clips = any(len(track.clips) > 0 for track in self.tracks)
        if not has_clips:
            print("Controller Warning: No audio clips found on timeline to play.")
            return

        # Ensure the soundboard is sending the absolute latest parameters
        if hasattr(self, 'sound_board'):
            self.audio_engine.update_live_stream_parameters(self.sound_board.get_current_parameters())

        self.is_playing_timeline = True

        def progress_cb(elapsed):
            current_x = 50 + int(elapsed * 10 * self.zoom_scale)
            time_str = sec_to_timecode(elapsed)
            if getattr(self, "is_playing_timeline", False):
                self.after(0, lambda t=time_str, x=current_x: self._render_playback_playhead(x, t))

        def stop_cb():
            self.after(0, self.controller_stop)

        self.audio_engine.start_live_playback(
            self.tracks, 
            zoom_scale=self.zoom_scale,
            on_progress=progress_cb,
            on_stop=stop_cb
        )

    def controller_stop(self):
        self.is_playing_timeline = False
        self.audio_engine.stop_playback()
        self.timeline_canvas.delete("playback_playhead")
        self.timecode_label.configure(text="0:00.00")

    def _render_playback_playhead(self, x_pos: int, timecode_str: str):
        self.timeline_canvas.delete("playback_playhead")
        canvas_height = self.timeline_canvas.winfo_height() or 500
        
        self.timeline_canvas.create_line(
            x_pos, 0, x_pos, canvas_height, fill="#00ffcc", width=2, tags="playback_playhead"
        )
        self.timeline_canvas.create_polygon(
            x_pos - 6, 0, x_pos + 6, 0, x_pos + 6, 10, x_pos, 16, x_pos - 6, 10,
            fill="#00ffcc", outline="white", tags="playback_playhead"
        )
        self.timecode_label.configure(text=timecode_str)

    def controller_toggle_record(self):
        if not self.is_recording:
            self._push_undo_state()
            self.is_recording = True
            self.recording_start_time = time.time()
            
            # 1. Check hardware switch FIRST without pulling the whole dictionary
            is_new_track = False
            if hasattr(self, 'sound_board') and hasattr(self.sound_board, 'hardware_io'):
                is_new_track = self.sound_board.hardware_io.rec_to_new_track
                
            if is_new_track:
                new_track_name = f"Audio {len(self.tracks) + 1}"
                self.controller_add_track(new_track_name)
                target_idx = len(self.tracks) - 1
            else:
                target_idx = self.selected_track_idx if self.selected_track_idx is not None and self.selected_track_idx < len(self.tracks) else 0
                
            target_track = self.tracks[target_idx]
            
            # 2. NOW grab the parameters AFTER the new track and channel strip exist
            if hasattr(self, 'sound_board'):
                current_params = self.sound_board.get_current_parameters()
                self.audio_engine.update_live_stream_parameters(current_params)
            
            mute_output = self.mute_rec_switch.get() == 1
            self.audio_engine.start_recording(mute_output=mute_output, target_track_idx=target_idx)
            self.record_btn.configure(fg_color="red")
            
            clip_uid = f"clip_uid_{int(time.time()*1000)}"
            self.active_recording_clip_uid = clip_uid
            
            clip_data = {
                "uid": clip_uid,
                "name": f"{target_track.name} (Recording...)",
                "path": "",
                "duration": 0.1,
                "start_x": 50,
                "end_x": 50,
                "is_recording": True
            }
            
            target_track.clips = [clip_data]
            
            self._redraw_all_clips()
            
            import threading
            threading.Thread(target=self._run_live_recording_render_loop, daemon=True).start()
        else:
            self.is_recording = False
            os.makedirs(os.path.join(os.getcwd(), "assets", "temp", "mic"), exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_path = os.path.join(os.getcwd(), "assets", "temp", "mic", f"{timestamp}_timeline_track.wav")
            
            saved_path = self.audio_engine.stop_recording(final_path)
            self.record_btn.configure(fg_color="darkred")
            
            elapsed_time = (time.time() - self.recording_start_time) if self.recording_start_time else 1.0
            
            for track in self.tracks:
                for clip in track.clips:
                    if clip.get("uid") == getattr(self, "active_recording_clip_uid", None):
                        actual_duration = elapsed_time
                        if saved_path and os.path.exists(saved_path):
                            try:
                                with wave.open(saved_path, 'rb') as wf:
                                    actual_duration = wf.getnframes() / float(wf.getframerate())
                            except Exception:
                                pass
                        
                        clip["path"] = saved_path if saved_path else final_path
                        pixels_per_sec = 10 * self.zoom_scale
                        clip["duration"] = actual_duration
                        clip["end_x"] = clip["start_x"] + int(actual_duration * pixels_per_sec)
                        clip["name"] = f"{track.name} #{len(track.clips)}"
                        clip.pop("is_recording", None)
                        break
            
            self.active_recording_clip_uid = None
            self._redraw_all_clips()
            self.track_sidebar.refresh_tracks()
            if self.selected_track_idx is not None:
                self.track_sidebar.select_track(self.selected_track_idx)

    def _run_live_recording_render_loop(self):
        while self.is_recording:
            elapsed = 0.0
            if self.recording_start_time is not None:
                elapsed = time.time() - self.recording_start_time
                timecode_str = sec_to_timecode(elapsed)
                self.after(0, lambda t=timecode_str: self.timecode_label.configure(text=t))
            
            self.after(0, self._update_active_recording_visuals, elapsed)
            time.sleep(0.05)

    def _update_active_recording_visuals(self, elapsed_sec: float):
        for track in self.tracks:
            for clip in track.clips:
                if clip.get("is_recording", False):
                    uid = clip["uid"]
                    track_idx = track.track_id
                    y_top = 45 + (track_idx * 80)
                    y_bottom = y_top + 70
                    
                    pixels_per_sec = 10 * self.zoom_scale
                    computed_width = int(elapsed_sec * pixels_per_sec)
                    x_start = int(clip.get("start_x", 50))
                    x_end = x_start + max(2, computed_width)
                    clip["end_x"] = x_end
                    
                    self.timeline_canvas.delete(f"live_{uid}")
                    self.timeline_canvas.create_rectangle(
                        x_start, y_top, x_end, y_bottom, 
                        fill="#d97736", outline="#f39c12", width=1, 
                        tags=("clip_block", uid, f"live_{uid}")
                    )
                    self.timeline_canvas.create_text(
                        x_start + 8, y_top + 6, text=clip['name'], 
                        anchor="nw", fill="white", font=("Arial", 9, "bold"), 
                        tags=("clip_block", uid, f"live_{uid}")
                    )

    def _redraw_all_clips(self):
        self._draw_timeline_grid()
        self.timeline_canvas.delete("clip_block")
        
        for track_idx, track in enumerate(self.tracks):
            y_top = 45 + (track_idx * 80)
            y_bottom = y_top + 70
            mid_y = y_top + 35
            
            for clip in track.clips:
                path = clip.get("path", "")
                uid = clip["uid"]
                if clip.get("is_recording", False):
                    continue

                duration = clip.get("duration", 3.0)
                pixels_per_sec = 10.0 * self.zoom_scale
                computed_width = duration * pixels_per_sec
                x_start = float(clip.get("start_x", 50.0))
                x_end = x_start + max(2.0, computed_width)
                clip["end_x"] = x_end
                
                int_x_start = int(x_start)
                int_x_end = int(x_end)
                
                self.timeline_canvas.create_rectangle(
                    int_x_start, y_top, int_x_end, y_bottom, 
                    fill="#2b4c7e", outline="#3498db", width=1, tags=("clip_block", uid)
                )
                
                waveform_peaks = []
                if path and os.path.exists(path):
                    try:
                        y, sr = librosa.load(path, sr=44100)
                        if len(y) > 0:
                            width_pixels = max(10, int((int_x_end - int_x_start) // 2))
                            chunk_size = max(1, int(len(y) // width_pixels))
                            for i in range(0, len(y), chunk_size):
                                chunk = y[i:i + chunk_size]
                                if len(chunk) > 0:
                                    waveform_peaks.append(float(np.max(np.abs(chunk))))
                    except Exception:
                        pass

                step = 2
                draw_x_start = int_x_start + 2
                draw_x_end = int_x_end - 2
                for idx, x in enumerate(range(draw_x_start, draw_x_end, step)):
                    h_offset = 2
                    if idx < len(waveform_peaks):
                        h_offset = max(2, int(min(1.0, waveform_peaks[idx] * 5.0) * 26))
                    
                    self.timeline_canvas.create_line(
                        x, mid_y - h_offset, x, mid_y + h_offset, 
                        fill="#00ffff", width=1.5, tags=("clip_block", uid)
                    )
                
                self.timeline_canvas.create_text(
                    int_x_start + 8, y_top + 6, text=f"{clip['name']} ({duration:.2f}s)", 
                    anchor="nw", fill="white", font=("Arial", 9, "bold"), tags=("clip_block", uid)
                )
                self.timeline_canvas.configure(scrollregion=self.timeline_canvas.bbox("all"))