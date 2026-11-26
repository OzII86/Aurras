## Aurras File Structure
This system is a stand-alone program designed modular solo engines. The root is stored within `Desktop/Projects/`.

Path:
Aurras/
│
├── core/                           # Standalone Backend Processing Engines (HIVE-Ready)
│   ├── __init__.py
│   ├── audio_engine.py             # Real-time mic duplex streaming, live channel DSP, and stereo master mix export
│   ├── beat_engine.py              # Standalone polyphonic pad sampler, BPM clock, metronome, quantized loop overdubber & text-to-beat compiler
│   ├── dsp.py                      # Stateful 4-Band Butterworth EQ (FourBandEQ) and anti-pop VolumeFader
│   ├── config_loader.py            # JSON configuration manager for 36-pad soundboard, grid modes, song scripts, and dual-layer numpad
│   ├── input_mapper.py             # Win32 low-level Num Lock state detector and dual-layer macro router
│   ├── separator.py                # Local Demucs AI stem separation engine (vocals, drums, bass, other)
│   ├── pack_generator.py           # Dynamic plugin orchestrator discovering and building sound packs per grid dimension
│   └── packs/                      # Modular Drop-In Sound Pack Synthesis Plugins
│       ├── __init__.py
│       ├── dsp_primitives.py       # Shared physical modeling waveguides (Karplus-Strong), filters, and scale math
│       ├── pack_starter.py         # Starter_Pack (808s, Crisp Snare, Hats, Industrial Bass, Piano C4, Dark Keys, Cyber Pluck)
│       ├── pack_pure_drums.py      # Pure_Acoustic_Drums (Studio Kick, Birch Snare, Rack/Floor Toms, Crash, Ride, Bell, Shaker)
│       ├── pack_pure_cello.py      # Pure_Cello_Ensemble (Bowed Cello sustains, Spiccato short bows, Pizzicato plucks, Timpani)
│       ├── pack_pure_brass.py      # Pure_Brass_Section (Lip-reed Trumpet, Muted Jazz Trumpet, Low Trombone, Marching Snare)
│       ├── pack_pure_piano.py      # Pure_Grand_Piano (3-Octave Concert Grand, Cm9 Chords, FM Electric Grand, Harpsichord)
│       ├── pack_cyber_industrial.py# Cyber_Industrial (Doom Kick, Gated Snare, Anvil Clank, Acid 303, Bitcrush Sub, Dystopian Horn)
│       ├── pack_gothic_cathedral.py# Gothic_Cathedral (War Taiko, Tubular Bell, Dungeon Chains, Pipe Organ Dm, Glass Harp)
│       ├── pack_lofi_midnight.py   # LoFi_Midnight (Dusty Kick, Lazy Rim, Rhodes FMaj7, Upright Bass, Vibraphone, Tape Flute)
│       ├── pack_dark_phonk_trap.py # Dark_Phonk_Trap (Pitched 808 Cowbells, Clipped 808s, 1/32 Hi-Hat Rolls, Memphis Vox Chops)
│       ├── pack_metal_foundry.py   # Metal_Foundry (Palm-Muted Drop-C Guitar Chugs, Power Chords, Double Kick, Trash China)
│       ├── pack_retro_synthwave.py # Retro_Synthwave (80s Gated Toms, Outrun PWM Bass, Juno Chorus Brass Stabs)
│       └── pack_chiptune_arcade.py # Chiptune_Arcade (8-Bit NES Pulse Leads, Triangle Bass, Arcade Coin/Powerup Arps)
│
├── ui/                             # Graphical User Interface Modules
│   ├── __init__.py
│   ├── main_window.py              # Main studio window, top menu bar, multi-tab workspace, and .aurras project packaging
│   ├── timeline_view.py            # Multi-track sequencer canvas, zoom scaling, 4-case region trimming, and undo history
│   ├── track_sidebar.py            # Per-track control cards (Name, Loop, Solo, Mute, M:SS.ss timecode positioning)
│   ├── sound_board.py              # Broadcast mixing console housing Hardware I/O, Channel Strips, and Preset Manager
│   ├── led_meter.py                # 7-segment vertical Green/Yellow/Red LED peak meter widget
│   ├── hotkey_board.py             # Scalable Beat Workstation (3x3, 3x6, 3x9, Full 36), Text-to-Song Sequencer & Pack Manager
│   ├── hotkey_toggle.py            # Dual-layer Numpad macro mapper interface (Num Lock ON / OFF)
│   ├── vault_explorer.py           # VS Code-style project and audio asset file explorer with context menus
│   └── controllers/                # Modular Mixing Console Strip Components
│       ├── hardware_io.py          # Permanent Mic/Speaker master faders, anti-pop fade slider, and Overwrite/New Track toggle
│       └── channel_strip.py        # Per-track vertical strip (Pan, Preamp Gain, 4-Band EQ, Echo FX, HPF, Mute, Fader, LED Meter)
│
├── Vault/                          # Central Studio Asset & Preset Storage
│   ├── Projects/                   # Self-contained studio project packages (project.aurras + bundled audio/)
│   ├── Audio/                      # Standalone raw audio imports and exported Loops/
│   └── Presets/                    # Console & Beat Workstation Presets
│       ├── Genres/                 # Mixing console genre presets
│       ├── Voices/                 # Vocal chain presets
│       ├── Customs/                # User-saved console presets
│       ├── Beats/                  # Auto-baked tweaked pad samples (e.g., kick_808_p+3_b+6dB_t-2dB.wav)
│       ├── 3x3/Packs/              # 9-Pad Sound Packs (Starter_Pack, Pure Instruments, Genre Packs + pack_manifest.json)
│       ├── 3x6/Packs/              # 18-Pad Sound Packs
│       ├── 3x9/Packs/              # 27-Pad Sound Packs
│       └── Full_36/Packs/          # 36-Pad Full-Keyboard Sound Packs
│
├── assets/                         # Runtime Workspace & Temporary Buffers
│   ├── icons/
│   └── temp/                       # Runtime mic recordings (mic/), split stems, region trims (trimmed/), and master mixes (mix/)
│
├── config/                         # User Mappings & Persistent State
│   ├── num_mapping.json            # 36-pad soundboard state, looper transport settings, song scripts, and numpad layers
│   └── aurras_vault.db             # Local SQLite database storing salted user accounts, tier expirations & redeemed pack keys (git-ignored)
│
├── Milestones.md                   # Project Milestones and Completion Status
├── ProjectPlan.md                  # High-Level Development Roadmap
├── README.md                       # Architecture and System Documentation
├── main.py                         # Application entry point
├── requirements.txt                # Python package dependencies
└── SoundForgeStudio.spec           # PyInstaller build specification

## Core Feature Architecture
* **Broadcast Mixing Console (`SoundBoardPanel`)**: A professional-grade vertical fader channel strip providing real-time hardware I/O control (Mic and Speaker master volumes), Preamp Gain, High-Pass Filters, 4-Band Equalization, Compression, Echo/Delay, Pitch/Formant shifting, and live Green/Yellow/Red LED peak meters with feedback prevention routing.

* **Vault Preset & Project Hierarchy**: A structured preset library (`Vault/Presets/Genres/`, `Voices/`, `Customs/`) allowing producers to save, load, and dynamically organize custom console processing chains via JSON manifests.

* **Multi-Track DAW Sequencer**: A timeline workspace supporting multi-format audio loading (WAV, MP3, FLAC, OGG), mouse-wheel zoom scaling, clip dragging, absolute region selection, duplication, deletion, and robust undo history management.

* **Vault Explorer**: An embedded VS Code-style file explorer supporting double-click project loading, audio previewing, file renaming, deletion, and direct integration with the file system.

* **Dynamic Soundboard & Dual-Layer Numpad Mapper**: Customizable macro soundboard grids and Num Lock-aware dual-layer numpad keybind managers for live sound triggers and sample playback.

* **Standalone Beat Engine & Scalable Pad Matrix (BeatEngine & HotkeyBoard)**: A zero-dependency polyphonic sampler and loop workstation supporting dynamic grid scaling (3x3 [9 pads], 3x6 [18 pads], 3x9 [27 pads], and Full (36) [36 pads]). Features a master BPM clock (60–200 BPM), synthesized metronome click, rhythmic quantization (Off, 1/4, 1/8, 1/16, 1/32), multi-pass live overdub recording, 15-step overdub undo, and one-click export straight to the Multi-Track Sequencer.

* **Text-to-Song Sequencer**: Built-in text tracker allowing users to compose and layer beats by typing strings of characters—grouped characters fire simultaneously as chords/stacks (e.g., qdx), while spaces ( ) and dashes (-) advance the quantized timing grid. Includes live pad-to-text keystroke capture.

* **Modular Sound Pack Plugin Architecture (`core/pack_generator.py & core/packs/`)**: Dynamically discovers and synthesizes 12 genre and pure-instrument packs across all grid sizes (Vault/Presets/<grid_type>/Packs/), auto-indexes manually dropped audio folders, and bakes custom Pitch/Bass/Treble pad tweaks into auto-named .wav files in Vault/Presets/Beats/.

* **Offline Account, Tiered Entitlements & Admin Keygen (`core/auth_manager.py`)**: Self-hosted SQLite authentication engine (`config/aurras_vault.db`) using PBKDF2-HMAC-SHA256 salted password hashing and deterministic HMAC-SHA256 product keys. Supports progressive commercial tiers (**Free Starter**, **30-Day Auto-Demo**, **Individual Pack Keys**, **Stackable 30-Day Monthly Subscriptions**, **Lifetime Pro**, and **Admin Master**) with full `3x3`–`Full (36)` grid access across all tiers and an interactive **Admin Product Key Generator** inside the Account Console.


* **Broadcast Mixing Console (SoundBoardPanel, HardwareIOBlock, ChannelStrip)**: Hardware-inspired vertical channel strip console providing real-time Mic/Speaker master volume control, anti-pop relay warmup fades (VolumeFader), Preamp Gain, stateful 4-Band Butterworth EQ (FourBandEQ), circular-buffer Echo FX, stereo Pan, and 50ms-polled 7-segment LED peak meters.

* **Multi-Track DAW Sequencer & Vault Explorer (TimelineViewFrame, VaultExplorerSidebar)**: Interactive timeline supporting multi-format audio, mouse-wheel zoom scaling, clip dragging, Ctrl+Click region selection, 4-case non-destructive region splitting/trimming, 20-step undo history, and .aurras project packaging.