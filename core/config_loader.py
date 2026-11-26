import os
import json
from typing import Dict, Any

class ConfigLoader:
    """
    Utility class to load, update, and save user-defined Numpad macro 
    and soundboard mappings to 'config/num_mapping.json'.
    """
    def __init__(self, config_path: str = "config/num_mapping.json"):
        self.config_path = os.path.abspath(config_path)
        self.data: Dict[str, Any] = {}
        self.load_config()

    def _ensure_defaults(self):
        """Ensures both numpad_layers and hotkey_board structures exist in JSON."""
        changed = False
        if "numpad_layers" not in self.data:
            self.data["numpad_layers"] = {"num_lock_on": {}, "num_lock_off": {}}
            changed = True

        if "licensing" not in self.data:
            self.data["licensing"] = {
                "master_key_unlocked": False,
                "unlocked_packs": ["Starter_Pack"]
            }
            changed = True

        full_keys = [
            "q", "w", "e", "a", "s", "d", "z", "x", "c",
            "r", "t", "y", "f", "g", "h", "v", "b", "n",
            "u", "i", "o", "j", "k", "l", "m", ",", ".",
            "1", "2", "3", "4", "5", "6", "7", "8", "9"
        ]
        if "hotkey_board" not in self.data:
            slots = {}
            for i in range(36):
                slots[f"slot_{i}"] = {
                    "label": f"Pad {i + 1}",
                    "hotkey": full_keys[i],
                    "sample": "",
                    "base_sample": "",
                    "pitch": 0.0,
                    "bass": 0.0,
                    "treble": 0.0,
                    "duration": 0.0,
                    "volume": 1.0,
                    "choke": False
                }
            self.data["hotkey_board"] = {
                "bpm": 120.0,
                "bars": 2,
                "quantize": "1/8",
                "metronome": True,
                "grid_mode": "3x3",
                "song_script": "qez e we e qez qez we e",
                "slots": slots
            }
            changed = True
        else:
            # Ensure existing configs upgrade cleanly to 36 slots
            slots = self.data["hotkey_board"].setdefault("slots", {})
            for i in range(36):
                if f"slot_{i}" not in slots:
                    slots[f"slot_{i}"] = {
                        "label": f"Pad {i + 1}",
                        "hotkey": full_keys[i],
                        "sample": "",
                        "base_sample": "",
                        "pitch": 0.0,
                        "bass": 0.0,
                        "treble": 0.0,
                        "duration": 0.0,
                        "volume": 1.0,
                        "choke": False
                    }
                    changed = True
            if "grid_mode" not in self.data["hotkey_board"]:
                self.data["hotkey_board"]["grid_mode"] = "3x3"
                changed = True
            if "song_script" not in self.data["hotkey_board"]:
                self.data["hotkey_board"]["song_script"] = "qez e we e qez qez we e"
                changed = True

        if changed:
            self.save_config()

    def load_config(self):
        """Loads configuration from JSON file or initializes defaults if missing."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                print(f"Configuration loaded successfully from -> {self.config_path}")
            except Exception as e:
                print(f"Error parsing configuration JSON: {e}")
                self.data = {}
        else:
            print(f"Configuration file not found at {self.config_path}. Initializing default structure.")
            self.data = {}

        self._ensure_defaults()

    def save_config(self):
        """Saves current configuration state back to num_mapping.json."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            print(f"Configuration successfully saved to -> {self.config_path}")
        except Exception as e:
            print(f"Error saving configuration JSON: {e}")

    def update_macro_binding(self, layer: str, key: str, label: str, sample_path: str):
        """
        Updates a specific hotkey's label and audio sample path dynamically 
        from the user hotkey editor interface.
        """
        if "numpad_layers" in self.data and layer in self.data["numpad_layers"]:
            self.data["numpad_layers"][layer][key] = {
                "label": label,
                "sample": sample_path
            }
            self.save_config()

    def get_hotkey_board_config(self) -> Dict[str, Any]:
        """Returns the hotkey_board configuration dictionary."""
        self._ensure_defaults()
        return self.data["hotkey_board"]

    def update_hotkey_slot(
        self,
        slot_idx: int,
        label: str,
        hotkey: str,
        sample_path: str,
        base_sample: str = "",
        pitch: float = 0.0,
        bass: float = 0.0,
        treble: float = 0.0,
        duration: float = 0.0,
        volume: float = 1.0,
        choke: bool = False
    ):
        """Updates and persists a single soundboard pad slot."""
        self._ensure_defaults()
        slot_key = f"slot_{slot_idx}"
        self.data["hotkey_board"]["slots"][slot_key] = {
            "label": label,
            "hotkey": hotkey,
            "sample": sample_path,
            "base_sample": base_sample or sample_path,
            "pitch": float(pitch),
            "bass": float(bass),
            "treble": float(treble),
            "duration": float(duration),
            "volume": float(volume),
            "choke": bool(choke)
        }
        self.save_config()

    def update_looper_transport(self, bpm: float, bars: int, quantize: str, metronome: bool):
        """Updates and persists the beat looper transport settings."""
        self._ensure_defaults()
        self.data["hotkey_board"]["bpm"] = float(bpm)
        self.data["hotkey_board"]["bars"] = int(bars)
        self.data["hotkey_board"]["quantize"] = str(quantize)
        self.data["hotkey_board"]["metronome"] = bool(metronome)
        self.save_config()