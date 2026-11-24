# --- core/pack_generator.py (Plugin Loader) ---
import os
import json
import importlib
import pkgutil
from typing import Dict, Any, List
import soundfile as sf
from core.packs.dsp_primitives import SAMPLE_RATE

FREE_PACKS = {"Starter_Pack"}
ADMIN_MASTER_KEY = "AURRAS-ADMIN-MASTER-2026"

GRID_MODE_DIRS = {
    "3x3": ("3x3", 9),
    "3x6": ("3x6", 18),
    "3x9": ("3x9", 27),
    "Full (36)": ("Full_36", 36),
}


def get_packs_dir_for_grid(grid_mode: str = "3x3") -> tuple[str, str, int]:
    """Returns (abs_packs_dir, grid_folder_name, pad_count) for the requested grid_mode."""
    folder_name, pad_count = GRID_MODE_DIRS.get(grid_mode, ("3x3", 9))
    abs_dir = os.path.join(os.getcwd(), "Vault", "Presets", folder_name, "Packs")
    return abs_dir, folder_name, pad_count


def discover_pack_plugins() -> Dict[str, Any]:
    """
    Dynamically discovers all standalone `pack_*.py` generator modules inside `core/packs/`.
    Each module exposes PACK_NAME (str), DEFAULT_BPM (float), and get_36_pads() -> list.
    """
    import core.packs as packs_pkg
    plugins: Dict[str, Any] = {}

    for _, mod_name, is_pkg in pkgutil.iter_modules(packs_pkg.__path__):
        if is_pkg or not mod_name.startswith("pack_"):
            continue
        try:
            module = importlib.import_module(f"core.packs.{mod_name}")
            pack_name = getattr(module, "PACK_NAME", None)
            if pack_name and hasattr(module, "get_36_pads"):
                plugins[pack_name] = module
        except Exception as e:
            print(f"[PackOrchestrator] Error loading plugin '{mod_name}': {e}")

    # Ensure Starter_Pack is always ordered first in the plugin registry
    ordered = {"Starter_Pack": plugins.pop("Starter_Pack")} if "Starter_Pack" in plugins else {}
    ordered.update(dict(sorted(plugins.items())))
    return ordered
    return plugins


def build_single_pack(pack_name: str, module: Any, grid_mode: str = "3x3") -> bool:
    """Renders a single pack plugin into Vault/Presets/<grid_dir>/Packs/<pack_name>/."""
    packs_root_dir, grid_folder, pad_count = get_packs_dir_for_grid(grid_mode)
    pack_dir = os.path.join(packs_root_dir, pack_name)
    os.makedirs(pack_dir, exist_ok=True)

    full_pads = module.get_36_pads()
    active_pads = full_pads[:pad_count]
    default_bpm = float(getattr(module, "DEFAULT_BPM", 120.0))

    slots = {}
    for idx, (fname, label, key, audio_data, choke) in enumerate(active_pads):
        rel_path = os.path.join("Vault", "Presets", grid_folder, "Packs", pack_name, fname).replace("\\", "/")
        abs_path = os.path.join(pack_dir, fname)
        if not os.path.exists(abs_path):
            sf.write(abs_path, audio_data, SAMPLE_RATE, subtype="PCM_16")
        slots[f"slot_{idx}"] = {
            "label": label,
            "hotkey": key,
            "sample": rel_path,
            "base_sample": rel_path,
            "pitch": 0.0,
            "bass": 0.0,
            "treble": 0.0,
            "volume": 1.0,
            "choke": choke,
        }

    manifest = {
        "pack_name": pack_name,
        "grid_mode": grid_mode,
        "pad_count": pad_count,
        "bpm": default_bpm,
        "slots": slots,
    }
    with open(os.path.join(pack_dir, "pack_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

    print(f"[PackOrchestrator] Built {grid_mode} Plugin Pack ({pad_count} pads): '{pack_name}'")
    return True


def build_all_expansion_packs(
    grid_mode: str = "3x3",
    unlocked_packs: set[str] | None = None,
    master_key_active: bool = False
) -> List[str]:
    """
    Builds only free packs (Starter_Pack) unless `master_key_active` is True
    or the pack name is present in `unlocked_packs`.
    """
    packs_root_dir, _, _ = get_packs_dir_for_grid(grid_mode)
    plugins = discover_pack_plugins()
    allowed = set(FREE_PACKS)
    if unlocked_packs:
        allowed.update(unlocked_packs)

    built_names: List[str] = []
    for pack_name, mod in plugins.items():
        if not master_key_active and pack_name not in allowed:
            continue

        manifest_path = os.path.join(packs_root_dir, pack_name, "pack_manifest.json")
        if not os.path.isfile(manifest_path):
            build_single_pack(pack_name, mod, grid_mode)
        built_names.append(pack_name)

    return built_names


if __name__ == "__main__":
    for mode in ("3x3", "3x6", "3x9", "Full (36)"):
        build_all_expansion_packs(mode)