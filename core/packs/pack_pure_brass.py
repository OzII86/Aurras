# core/packs/pack_pure_brass.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo
)
from core.packs.pack_cyber_industrial import synth_dystopian_horn
from core.packs.pack_starter import synth_crisp_snare

PACK_NAME = "Pure_Brass_Section"
DEFAULT_BPM = 108.0


def synth_trumpet_note(duration: float = 0.65, freq: float = 261.63, muted: bool = False) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    scoop = 1.0 - 0.018 * np.exp(-t * 45.0)
    vib = 1.0 + 0.004 * np.sin(2.0 * np.pi * 5.5 * t) * np.clip((t - 0.12) * 4.0, 0.0, 1.0)
    phase = np.cumsum(2.0 * np.pi * (freq * scoop * vib) / SAMPLE_RATE)

    raw = sawtooth(phase) * 0.65 + np.sin(phase) * 0.4 + np.sin(phase * 2.0) * 0.3 + np.sin(phase * 3.0) * 0.2
    saturated = np.tanh(raw * 1.9).astype(np.float32)

    rng = np.random.default_rng(int(freq))
    chiff = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t * 50.0) * 0.08

    if muted:
        b, a = butter(2, [850.0 / (SAMPLE_RATE / 2.0), 2800.0 / (SAMPLE_RATE / 2.0)], "band")
    else:
        b, a = butter(2, 2400.0 / (SAMPLE_RATE / 2.0), "low")

    env = ((1.0 - np.exp(-t * 38.0)) * np.exp(-t * 2.4)).astype(np.float32)
    filtered = lfilter(b, a, saturated + chiff) * env
    return finalize_stereo(np.column_stack((filtered, np.roll(filtered, 12) * 0.95)))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("trp_c4.wav", "Trumpet C4", "q", synth_trumpet_note(0.65, 261.63), True),
        ("trp_eb4.wav", "Trumpet Eb4", "w", synth_trumpet_note(0.65, 311.13), True),
        ("trp_g4.wav", "Trumpet G4", "e", synth_trumpet_note(0.65, 392.00), True),
        ("trp_bb4.wav", "Trumpet Bb4", "a", synth_trumpet_note(0.65, 466.16), True),
        ("trp_c5.wav", "Trumpet C5", "s", synth_trumpet_note(0.65, 523.25), True),
        ("muted_trp_d4.wav", "Muted Jazz D4", "d", synth_trumpet_note(0.55, 293.66, muted=True), True),
        ("trombone_c2.wav", "Trombone C2", "z", synth_dystopian_horn(0.95, 65.41), True),
        ("trombone_g2.wav", "Trombone G2", "x", synth_dystopian_horn(0.95, 98.00), True),
        ("brass_snare.wav", "Marching Snare", "c", synth_crisp_snare(0.30), False),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            audio = synth_trumpet_note(duration=0.65, freq=freq, muted=False)
            label, choke = f"Trumpet {n_lbl}", True
        elif step < 18:
            audio = synth_trumpet_note(duration=0.55, freq=freq, muted=True)
            label, choke = f"Muted Trp {n_lbl}", True
        else:
            audio = synth_dystopian_horn(duration=0.85, freq=freq * 0.5)
            label, choke = f"Trombone {n_lbl}", True

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads