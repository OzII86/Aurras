# core/packs/pack_metal_foundry.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, butter, finalize_stereo, karplus_strong_pluck
)

PACK_NAME = "Metal_Foundry"
DEFAULT_BPM = 135.0


def synth_metal_guitar(freq: float = 65.41, duration: float = 0.55, palm_mute: bool = False) -> np.ndarray:
    """High-gain tube-saturated Drop-C power chord (Root + Fifth + Octave) with cabinet impulse filter."""
    decay = 0.982 if palm_mute else 0.996
    bright = 0.28 if palm_mute else 0.55
    root = karplus_strong_pluck(freq, duration, decay=decay, brightness=bright)
    fifth = karplus_strong_pluck(freq * 1.498, duration, decay=decay, brightness=bright) * 0.85
    octave = karplus_strong_pluck(freq * 2.0, duration, decay=decay, brightness=bright) * 0.65

    # Double-tracked stereo guitars pushed through high-gain tanh tube clipping
    raw_l = np.tanh((root + fifth + octave) * 6.5).astype(np.float32)
    raw_r = np.tanh(( np.roll(root, 18) + fifth * 0.9 + octave * 1.1) * 6.5).astype(np.float32)

    # 4x12 Celestion Guitar Cabinet bandpass emulation (85Hz - 3800Hz)
    b, a = butter(3, [85.0 / (SAMPLE_RATE / 2.0), 3800.0 / (SAMPLE_RATE / 2.0)], "band")
    cab_l = lfilter(b, a, raw_l)
    cab_r = lfilter(b, a, raw_r)
    return finalize_stereo(np.column_stack((cab_l, cab_r)))


def synth_click_kick(duration: float = 0.35, double_hit: bool = False) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = 48.0 + 160.0 * np.exp(-t * 42.0)
    sub = np.sin(np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)) * np.exp(-t * 9.0)
    beater = np.sin(2.0 * np.pi * 3200.0 * t) * np.exp(-t * 95.0) * 0.55
    hit = np.tanh((sub + beater) * 2.0).astype(np.float32)
    if double_hit:
        offset = int(SAMPLE_RATE * 0.11)
        hit[offset:] += hit[:len(hit) - offset] * 0.95
    return finalize_stereo(hit)


def synth_china_cymbal(duration: float = 0.75) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    ratios = [245.0, 388.0, 512.0, 780.0, 1190.0, 1840.0, 2910.0]
    trash = np.zeros_like(t)
    for r in ratios:
        trash += np.sign(np.sin(2.0 * np.pi * r * t)).astype(np.float32)
    rng = np.random.default_rng(66)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(2, [1200.0 / (SAMPLE_RATE / 2.0), 6500.0 / (SAMPLE_RATE / 2.0)], "band")
    env = np.exp(-t * 4.5).astype(np.float32)
    return finalize_stereo(lfilter(b, a, trash * 0.4 + noise * 0.6) * env)


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("metal_kick.wav", "Trigger Kick", "q", synth_click_kick(0.32, False), False),
        ("double_kick.wav", "Double Kick 2x", "w", synth_click_kick(0.36, True), True),
        ("china_trash.wav", "Trash China Cym", "e", synth_china_cymbal(0.75), False),
        ("chug_drop_c.wav", "Palm Chug C2", "a", synth_metal_guitar(65.41, 0.28, palm_mute=True), True),
        ("chug_eb2.wav", "Palm Chug Eb2", "s", synth_metal_guitar(77.78, 0.28, palm_mute=True), True),
        ("chug_f2.wav", "Palm Chug F2", "d", synth_metal_guitar(87.31, 0.28, palm_mute=True), True),
        ("chord_drop_c.wav", "Power Chord C2", "z", synth_metal_guitar(65.41, 0.85, palm_mute=False), True),
        ("chord_eb2.wav", "Power Chord Eb2", "x", synth_metal_guitar(77.78, 0.85, palm_mute=False), True),
        ("chord_g2.wav", "Power Chord G2", "c", synth_metal_guitar(98.00, 0.85, palm_mute=False), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            audio = synth_metal_guitar(freq=midi_to_freq(36 + step), duration=0.28, palm_mute=True)
            label, choke = f"Chug {midi_to_label(36 + step)}", True
        elif step < 18:
            audio = synth_metal_guitar(freq=midi_to_freq(36 + (step - 9)), duration=0.80, palm_mute=False)
            label, choke = f"Power {midi_to_label(36 + (step - 9))}", True
        else:
            audio = synth_metal_guitar(freq=freq * 2.0, duration=0.60, palm_mute=False)
            label, choke = f"Shred Lead {n_lbl}", True

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads