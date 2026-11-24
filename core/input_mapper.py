import ctypes
from typing import Dict, Any

class NumpadLayerManager:
    """
    Manages dual-layer Numpad macro execution based on the system Num Lock state.
    """
    def __init__(self, config_data: Dict[str, Any]):
        self.layers = config_data.get("numpad_layers", {})

    def is_num_lock_active(self) -> bool:
        """
        Checks the low-level virtual key state for Num Lock (VK_NUMLOCK = 0x90).
        Returns True if Num Lock is ON, False if OFF.
        """
        try:
            # GetKeyState returns a short; lowest bit indicates toggle state
            state = ctypes.windll.user32.GetKeyState(0x90)
            return bool(state & 0x0001)
        except Exception:
            return True  # Default fallback

    def get_active_mapping(self, virtual_key_name: str) -> dict:
        """
        Retrieves the correct macro mapping depending on the current Num Lock toggle state.
        """
        num_lock_is_on = self.is_num_lock_active()
        active_layer_key = "num_lock_on" if num_lock_is_on else "num_lock_off"
        
        layer_mappings = self.layers.get(active_layer_key, {})
        return layer_mappings.get(virtual_key_name, {})