# core/packs/pack_pure_piano.py
import numpy as np
from core.packs.dsp_primitives import (
    FULL_36_KEYS, C_MINOR_SCALE_MIDI, midi_to_freq, midi_to_label
)
from core.packs.pack_starter import synth_piano_note, synth_piano_chord
from core.packs.pack_lofi_midnight import synth_rhodes_chord
from core.packs.pack_gothic_cathedral import synth_harpsichord

PACK_NAME = "Pure_Grand_Piano"
DEFAULT_BPM = 100.0


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("piano_c3.wav", "Grand Piano C3", "q", synth_piano_note(0.9, 130.81), False),
        ("piano_eb3.wav", "Grand Piano Eb3", "w", synth_piano_note(0.9, 155.56), False),
        ("piano_f3.wav", "Grand Piano F3", "e", synth_piano_note(0.9, 174.61), False),
        ("piano_g3.wav", "Grand Piano G3", "a", synth_piano_note(0.9, 196.00), False),
        ("piano_bb3.wav", "Grand Piano Bb3", "s", synth_piano_note(0.9, 233.08), False),
        ("piano_c4.wav", "Grand Piano C4", "d", synth_piano_note(0.9, 261.63), False),
        ("piano_eb4.wav", "Grand Piano Eb4", "z", synth_piano_note(0.9, 311.13), False),
        ("piano_cm9.wav", "Grand Chord Cm9", "x", synth_piano_chord(1.15), True),
        ("rhodes_fmaj7.wav", "Electric Grand", "c", synth_rhodes_chord(1.15), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 18:
            audio = synth_piano_note(duration=0.85, freq=freq)
            label, choke = f"Piano {n_lbl}", False
        else:
            audio = synth_harpsichord(duration=0.70, freq=freq)
            label, choke = f"Bright Key {n_lbl}", False

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads