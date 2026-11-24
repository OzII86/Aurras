# core/packs/pack_pure_cello.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo, karplus_strong_pluck
)
from core.packs.pack_gothic_cathedral import synth_cello_bow, synth_pizzicato_strings, synth_war_taiko

PACK_NAME = "Pure_Cello_Ensemble"
DEFAULT_BPM = 92.0


def synth_cello_spiccato(duration: float = 0.32, freq: float = 130.81) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    bow = sawtooth(2.0 * np.pi * freq * t) + 0.35 * sawtooth(2.0 * np.pi * (freq * 1.003) * t)
    rng = np.random.default_rng(int(freq * 10))
    rosin = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t * 45.0) * 0.15
    b, a = butter(2, 920.0 / (SAMPLE_RATE / 2.0), "low")
    env = ((1.0 - np.exp(-t * 65.0)) * np.exp(-t * 8.5)).astype(np.float32)
    return finalize_stereo(lfilter(b, a, bow + rosin) * env)


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("cello_c2_bow.wav", "Cello Bow C2", "q", synth_cello_bow(1.1, 65.41), True),
        ("cello_g2_bow.wav", "Cello Bow G2", "w", synth_cello_bow(1.1, 98.00), True),
        ("cello_c3_bow.wav", "Cello Bow C3", "e", synth_cello_bow(1.1, 130.81), True),
        ("cello_eb3_bow.wav", "Cello Bow Eb3", "a", synth_cello_bow(1.1, 155.56), True),
        ("cello_g3_bow.wav", "Cello Bow G3", "s", synth_cello_bow(1.1, 196.00), True),
        ("cello_spic_c3.wav", "Spiccato C3", "d", synth_cello_spiccato(0.32, 130.81), False),
        ("cello_spic_g3.wav", "Spiccato G3", "z", synth_cello_spiccato(0.32, 196.00), False),
        ("cello_pizz_c3.wav", "Pizzicato C3", "x", synth_pizzicato_strings(0.5, 130.81), False),
        ("war_taiko_hit.wav", "Ensemble Timpani", "c", synth_war_taiko(0.75), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            audio = synth_cello_bow(duration=0.95, freq=freq * 0.5)
            label, choke = f"Cello Bow {n_lbl}", True
        elif step < 18:
            audio = synth_cello_spiccato(duration=0.32, freq=freq * 0.5)
            label, choke = f"Spiccato {n_lbl}", False
        else:
            audio = finalize_stereo(karplus_strong_pluck(freq * 0.5, 0.55, decay=0.991, brightness=0.35))
            label, choke = f"Cello Pizz {n_lbl}", False

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads