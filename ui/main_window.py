import os
import json
import wave
import shutil
import time
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from core.audio_engine import AudioEngine
from ui.timeline_view import TimelineViewFrame, TimelineTrack
from ui.track_sidebar import TimelineTrack, TrackSidebar
from ui.hotkey_board import HotkeyBoard
from ui.hotkey_toggle import HotkeyToggle

class ProjectCreationDialog(ctk.CTkToplevel):
    """Modal dialog for capturing and sanitizing a custom project name."""
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.title("New Project")
        self.geometry("350x180")
        self.resizable(False, False)
        self.callback = callback
        
        self.transient(parent)
        self.grab_set()

        self.label = ctk.CTkLabel(self, text="Enter Project Name:", font=("Arial", 12, "bold"))
        self.label.pack(pady=(20, 5))

        self.entry = ctk.CTkEntry(self, width=280, placeholder_text="e.g., custom_project_name")
        self.entry.pack(pady=5)
        self.entry.focus()
        self.entry.bind("<Return>", lambda e: self.confirm())

        self.btn = ctk.CTkButton(self, text="Create Project", command=self.confirm)
        self.btn.pack(pady=(15, 20))

    def confirm(self):
        raw_name = self.entry.get().strip()
        if raw_name:
            sanitized_name = re.sub(r'[^a-zA-Z0-9_\-]', '', raw_name.replace(' ', '_'))
            self.destroy()
            self.callback(sanitized_name)

class MainWindow(ctk.CTk):
    """
    Main application window for Aurras, featuring a professional top menu bar,
    Vault export management, and tabbed studio workspaces.
    """
    def __init__(self):
        super().__init__()
        
        self.title("Aurras Audio & Voice Studio Suite")
        self.geometry("1300x800")
        
        self.audio_engine = AudioEngine()

        os.makedirs(os.path.join(os.getcwd(), "Vault", "Projects"), exist_ok=True)
        os.makedirs(os.path.join(os.getcwd(), "Vault", "Audio"), exist_ok=True)
        os.makedirs(os.path.join(os.getcwd(), "assets", "temp", "mic"), exist_ok=True)
        os.makedirs(os.path.join(os.getcwd(), "assets", "temp", "mix"), exist_ok=True)
        os.makedirs(os.path.join(os.getcwd(), "assets", "temp", "trimmed"), exist_ok=True)

        self._build_top_menu()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self, fg_color="#1a1a1a")
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.sequencer_tab = self.tabview.add("Sequencer")
        self.soundboard_tab = self.tabview.add("Soundboard Grid")
        self.mapper_tab = self.tabview.add("Numpad Dual-Layer Mapper")

        self.sequencer_tab.grid_columnconfigure(0, weight=1)
        self.sequencer_tab.grid_rowconfigure(0, weight=1)

        self.soundboard_tab.grid_columnconfigure(0, weight=1)
        self.soundboard_tab.grid_rowconfigure(0, weight=1)

        self.mapper_tab.grid_columnconfigure(0, weight=1)
        self.mapper_tab.grid_rowconfigure(0, weight=1)

        # Single clean initialization of main sequencer view
        self.sequencer_view = TimelineViewFrame(
            self.sequencer_tab, 
            audio_engine=self.audio_engine, 
            open_project_callback=self.menu_open_project_from_path
        )
        self.sequencer_view.pack(fill="both", expand=True)

        self.hotkey_board = HotkeyBoard(
            self.soundboard_tab,
            on_export_to_sequencer=self._send_beat_loop_to_sequencer
        )
        self.hotkey_board.pack(fill="both", expand=True)

        self.hotkey_toggle = HotkeyToggle(self.mapper_tab)
        self.hotkey_toggle.pack(fill="both", expand=True)

    def _build_top_menu(self):
        menubar = tk.Menu(self, bg="#222222", fg="white", activebackground="#1f538d", activeforeground="white", bd=0)
        
        file_menu = tk.Menu(menubar, tearoff=0, bg="#1a1a1a", fg="white", activebackground="#1f538d", activeforeground="white")
        file_menu.add_command(label="New Project", command=self.menu_new_project)
        file_menu.add_command(label="Open Project...", command=self.menu_open_project)
        file_menu.add_command(label="Open Audio File...", command=self.menu_open_audio_file)
        file_menu.add_separator()
        file_menu.add_command(label="Save Project", command=self.menu_save_project)
        file_menu.add_command(label="Save Project As...", command=self.menu_save_project_as)
        file_menu.add_command(label="Save Audio File As...", command=self.menu_save_audio_file)
        file_menu.add_separator()
        file_menu.add_command(label="Settings", command=self.menu_open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.menu_exit)
        
        menubar.add_cascade(label="File", menu=file_menu)
        
        edit_menu = tk.Menu(menubar, tearoff=0, bg="#1a1a1a", fg="white", activebackground="#1f538d", activeforeground="white")
        edit_menu.add_command(label="Undo", command=lambda: self.sequencer_view.controller_undo())
        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0, bg="#1a1a1a", fg="white", activebackground="#1f538d", activeforeground="white")
        view_menu.add_command(label="Toggle Dark/Light Mode", command=lambda: ctk.set_appearance_mode("Dark" if ctk.get_appearance_mode() == "Light" else "Light"))
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg="#1a1a1a", fg="white", activebackground="#1f538d", activeforeground="white")
        help_menu.add_command(label="About Aurras", command=lambda: messagebox.showinfo("About Aurras", "Aurras Audio & Voice Studio Suite\nLocal Multi-Track DAW & Soundboard Engine"))
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    def menu_new_project(self):
        if not hasattr(self, "open_project_names"):
            self.open_project_names = []

        def on_project_named(project_name: str):
            tab_title = project_name
            default_tabs = ["Sequencer", "Soundboard Grid", "Numpad Dual-Layer Mapper"]
            
            if tab_title in self.open_project_names or tab_title in default_tabs:
                tab_title = f"{project_name}_{int(time.time() % 1000)}"
            
            self.open_project_names.append(tab_title)
            
            new_tab = self.tabview.add(tab_title)
            new_tab.grid_columnconfigure(0, weight=1)
            new_tab.grid_rowconfigure(0, weight=1)
            
            project_sequencer = TimelineViewFrame(
                new_tab, 
                audio_engine=AudioEngine(), 
                open_project_callback=self.menu_open_project_from_path
            )
            project_sequencer.pack(fill="both", expand=True)
            
            project_sequencer.project_name = project_name
            project_sequencer.project_vault_dir = os.path.join(os.getcwd(), "Vault", "Projects", project_name)
            
            self.tabview.set(tab_title)
            print(f"Menu Action: Created new studio project tab -> {project_name}")

        ProjectCreationDialog(self, on_project_named)

    def menu_open_project(self):
        dir_path = filedialog.askdirectory(title="Open Project Folder", initialdir=os.path.join(os.getcwd(), "Vault", "Projects"))
        if dir_path:
            self.menu_open_project_from_path(dir_path)

    def menu_open_project_from_path(self, dir_path: str):
        if dir_path:
            manifest_path = os.path.join(dir_path, "project.aurras")
            if not os.path.exists(manifest_path):
                messagebox.showerror("Open Error", "No valid 'project.aurras' manifest found in this directory.")
                return

            # self.audio_engine.clean_temp_directory()

            try:
                with open(manifest_path, "r") as f:
                    project_data = json.load(f)
                
                proj_name = project_data.get("project_name", os.path.basename(dir_path))
                
                if not hasattr(self, "open_project_names"):
                    self.open_project_names = []
                    
                tab_title = proj_name
                default_tabs = ["Sequencer", "Soundboard Grid", "Numpad Dual-Layer Mapper"]
                if tab_title in self.open_project_names or tab_title in default_tabs:
                    tab_title = f"{proj_name}_{int(time.time() % 1000)}"
                
                self.open_project_names.append(tab_title)
                
                new_tab = self.tabview.add(tab_title)
                new_tab.grid_columnconfigure(0, weight=1)
                new_tab.grid_rowconfigure(0, weight=1)
                
                project_sequencer = TimelineViewFrame(
                    new_tab, 
                    audio_engine=AudioEngine(), 
                    open_project_callback=self.menu_open_project_from_path
                )
                project_sequencer.pack(fill="both", expand=True)
                
                project_sequencer.project_name = proj_name
                project_sequencer.project_vault_dir = dir_path
                
                project_sequencer.tracks.clear()
                project_sequencer.sound_board.clear_channels()

                for t_data in project_data.get("tracks", []):
                    track = TimelineTrack(t_data["track_id"], t_data["name"])
                    track.volume = t_data.get("volume", 1.0)
                    track.muted = t_data.get("muted", False)
                    track.soloed = t_data.get("soloed", False)
                    track.looped = t_data.get("looped", False)
                    
                    for clip in t_data.get("clips", []):
                        clip_path = clip.get("path")
                        if clip_path and not os.path.exists(clip_path):
                            alt_path = os.path.join(dir_path, "audio", os.path.basename(clip_path))
                            if os.path.exists(alt_path):
                                clip["path"] = alt_path
                        track.clips.append(clip)
                        
                    project_sequencer.tracks.append(track)
                    project_sequencer.sound_board.add_channel(track.name)

                # Refresh sidebar via update method
                project_sequencer.track_sidebar.tracks = project_sequencer.tracks
                project_sequencer.track_sidebar.refresh_tracks()
                if project_sequencer.tracks:
                    project_sequencer.track_sidebar.select_track(0)
                
                project_sequencer._redraw_all_clips()
                self.tabview.set(tab_title)
                print(f"Menu Action: Successfully loaded project from tree -> {proj_name}")

            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to parse project manifest:\n{e}")

    def menu_open_audio_file(self):
        file_path = filedialog.askopenfilename(
            title="Open Audio File", 
            filetypes=[("Audio Files", "*.wav *.mp3 *.ogg *.flac *.m4a"), ("All Files", "*.*")]
        )
        if file_path:
            # self.audio_engine.clean_temp_directory()
            print(f"Menu Action: Loaded audio file -> {file_path}")
            
            if not self.sequencer_view.tracks:
                self.sequencer_view.controller_add_track("Audio 1")
            target_idx = self.sequencer_view.selected_track_idx or 0
            track = self.sequencer_view.tracks[target_idx]

            duration = 3.0
            try:
                with wave.open(file_path, 'rb') as wf:
                    duration = wf.getnframes() / float(wf.getframerate())
            except Exception:
                pass

            clip_uid = f"clip_uid_{int(os.path.basename(file_path).__hash__())}"
            new_clip = {
                "uid": clip_uid,
                "name": os.path.basename(file_path),
                "path": file_path,
                "duration": duration,
                "start_x": 50,
                "end_x": 50 + int(duration * 10 * self.sequencer_view.zoom_scale)
            }
            track.clips = [new_clip]
            self.sequencer_view._redraw_all_clips()

    def _get_active_sequencer(self):
        current_tab_name = self.tabview.get()
        try:
            active_tab_frame = self.tabview.tab(current_tab_name)
            for widget in active_tab_frame.winfo_children():
                if isinstance(widget, TimelineViewFrame):
                    return widget
        except Exception:
            pass
        return None

    def menu_save_project(self):
        active_sequencer = self._get_active_sequencer()
        if not active_sequencer:
            messagebox.showerror("Save Error", "No active project session found in this tab.")
            return

        proj_name = getattr(active_sequencer, "project_name", None)
        if not proj_name:
            self.menu_save_project_as()
            return

        self._execute_project_save(proj_name, active_sequencer)

    def menu_save_project_as(self):
        active_sequencer = self._get_active_sequencer()
        if not active_sequencer:
            messagebox.showerror("Save Error", "No active project session found in this tab.")
            return

        def on_new_name_entered(new_name: str):
            active_sequencer.project_name = new_name
            active_sequencer.project_vault_dir = os.path.join(os.getcwd(), "Vault", "Projects", new_name)
            self._execute_project_save(new_name, active_sequencer)

        ProjectCreationDialog(self, on_new_name_entered)

    def _execute_project_save(self, proj_name: str, active_sequencer: TimelineViewFrame):
        proj_dir = os.path.join(os.getcwd(), "Vault", "Projects", proj_name)
        audio_vault_dir = os.path.join(proj_dir, "audio")
        
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(audio_vault_dir, exist_ok=True)

        project_data = {
            "project_name": proj_name,
            "version": "1.0",
            "tracks": []
        }
        
        for track in active_sequencer.tracks:
            track_clips_copied = []
            safe_track_name = re.sub(r'[^a-zA-Z0-9_\-]', '', track.name.replace(' ', '_'))
            if not safe_track_name:
                safe_track_name = f"Track_{track.track_id}"

            for idx, clip in enumerate(track.clips):
                src_path = clip.get("path")
                
                if src_path and os.path.exists(src_path):
                    file_ext = os.path.splitext(src_path)[1]
                    if len(track.clips) > 1:
                        new_file_name = f"{safe_track_name}_{idx + 1}{file_ext}"
                    else:
                        new_file_name = f"{safe_track_name}{file_ext}"
                        
                    dest_path = os.path.join(audio_vault_dir, new_file_name)
                    
                    if os.path.abspath(src_path) != os.path.abspath(dest_path):
                        try:
                            shutil.copy2(src_path, dest_path)
                        except Exception as e:
                            print(f"Warning: Could not copy asset {new_file_name}: {e}")
                    
                    clip["path"] = dest_path
                    clip["name"] = track.name if len(track.clips) == 1 else f"{track.name} #{idx + 1}"
                
                track_clips_copied.append(clip.copy())

            track_dict = {
                "track_id": track.track_id,
                "name": track.name,
                "volume": track.volume,
                "muted": track.muted,
                "soloed": track.soloed,
                "looped": track.looped,
                "clips": track_clips_copied
            }
            project_data["tracks"].append(track_dict)
        
        manifest_path = os.path.join(proj_dir, "project.aurras")
        try:
            with open(manifest_path, "w") as f:
                json.dump(project_data, f, indent=4)
            
            active_sequencer.audio_engine.clean_temp_directory()
            active_sequencer._redraw_all_clips()
            
            print(f"Menu Action: Project saved and paths redirected to -> {proj_dir}")
            messagebox.showinfo("Vault Save", f"Project successfully saved to:\n{proj_dir}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save project package:\n{e}")

    def menu_save_audio_file(self):
        active_sequencer = self._get_active_sequencer()
        proj_name = getattr(active_sequencer, "project_name", None) if active_sequencer else None
        
        if proj_name:
            initial_dir = os.path.join(os.getcwd(), "Vault", "Projects", proj_name, "audio")
        else:
            initial_dir = os.path.join(os.getcwd(), "Vault", "Audio")
            
        os.makedirs(initial_dir, exist_ok=True)

        file_path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            initialdir=initial_dir,
            filetypes=[
                ("WAV Audio (*.wav)", "*.wav"), 
                ("FLAC Audio (*.flac)", "*.flac"),
                ("MP3 Audio (*.mp3)", "*.mp3"),
                ("All Files (*.*)", "*.*")
            ]
        )
        if file_path:
            tracks_to_export = active_sequencer.tracks if active_sequencer else self.sequencer_view.tracks
            zoom_to_use = active_sequencer.zoom_scale if active_sequencer else self.sequencer_view.zoom_scale
            
            # ---> PASTE IT HERE <---
            active_sequencer = self._get_active_sequencer()
            console_parameters = active_sequencer.sound_board.get_current_parameters() if active_sequencer and hasattr(active_sequencer, "sound_board") else {}
            
            exported_path = self.audio_engine.mix_and_export_timeline(
                tracks_to_export, 
                output_path=file_path, 
                zoom_scale=zoom_to_use,
                console_params=console_parameters
            )
            
            if exported_path and os.path.exists(exported_path):
                messagebox.showinfo("Audio Export", f"Master mix exported successfully to:\n{exported_path}")
            else:
                messagebox.showerror("Export Failed", "Could not export master mix. Check console for missing or unsupported files.")

    def _send_beat_loop_to_sequencer(self, loop_wav_path: str, track_title: str):
        """Creates a new track on the Sequencer, loads the exported beat loop, and switches tabs."""
        target_seq = self._get_active_sequencer() or self.sequencer_view
        target_seq.controller_add_track(track_title)
        target_seq.selected_track_idx = len(target_seq.tracks) - 1
        target_seq.controller_load_audio_file(loop_wav_path)
        if hasattr(target_seq, "vault_explorer"):
            target_seq.vault_explorer.refresh_vault_tree()
        self.tabview.set("Sequencer")

    def menu_open_settings(self):
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Aurras Studio Settings")
        settings_win.geometry("400x300")
        settings_win.attributes("-topmost", True)
        ctk.CTkLabel(settings_win, text="Studio Preferences & Hotkeys", font=("Arial", 14, "bold")).pack(pady=20)
        ctk.CTkLabel(settings_win, text="Hotkey mapping and theme configs configured via JSON.", text_color="gray").pack(pady=10)

    def menu_exit(self):
        if messagebox.askyesno("Exit Aurras", "Are you sure you want to exit? Any unsaved work will be lost."):
            self.audio_engine.clean_temp_directory()
            self.destroy()

if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    app = MainWindow()
    app.mainloop()