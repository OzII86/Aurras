# core/packs/pack_808_sub_beats.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, butter, finalize_stereo
)
from core.packs.pack_starter import synth_crisp_snare, synth_hihat, synth_perc_clap

PACK_NAME = "808_Sub_Beats"
DEFAULT_BPM = 132.0


def synth_tuned_808(
    root_freq: float = 32.70,
    duration: float = 0.85,
    drive: float = 1.6,
    punch_hz: float = 135.0,
    glide_ratio: float = 1.0
) -> np.ndarray:
    """
    Synthesizes a studio 808 sub bass / kick tuned to an exact fundamental frequency:
    - root_freq: Sustained sub-bass frequency in Hz (e.g., C1 = 32.70 Hz).
    - drive: Harmonic saturation amount (1.2 = pure sub, 3.2 = distorted trap 808).
    - punch_hz: Initial transient pitch drop height for chest punch.
    - glide_ratio: Pitch slide multiplier over the sustain tail (e.g., 1.5 = slide up a fifth).
    """
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False, dtype=np.float32)

    # Pitch envelope: fast beater transient drop + smooth optional glide across the tail
    transient_drop = punch_hz * np.exp(-t * 38.0)
    glide_curve = root_freq * (1.0 + (glide_ratio - 1.0) * (1.0 - np.exp(-t * 4.5)))
    inst_freq = glide_curve + transient_drop

    phase = np.cumsum(2.0 * np.pi * inst_freq / SAMPLE_RATE)
    sub_body = np.sin(phase)

    # Subtle 2nd & 3rd harmonic warmth so low C1/D1 notes remain audible on all speakers
    harm2 = np.sin(phase * 2.0) * 0.14 * np.exp(-t * 3.5)
    click = np.sin(2.0 * np.pi * 1250.0 * t) * np.exp(-t * 160.0) * 0.25

    amp_env = (1.0 - np.exp(-t * 450.0)) * np.exp(-t * 2.6)
    saturated = np.tanh((sub_body + harm2 + click) * amp_env * drive).astype(np.float32)

    # Gentle low-pass to keep the sub clean and massive
    cutoff = min(900.0, max(240.0, root_freq * 6.5 * (drive * 0.6)))
    b, a = butter(2, cutoff / (SAMPLE_RATE / 2.0), "low")
    filtered = lfilter(b, a, saturated)

    return finalize_stereo(filtered, tail_ms=20.0)


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    # 1. Core 9-Pad 808 Beat Starter (Q-C)
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("808_deep_c1.wav", "808 Deep C1", "q", synth_tuned_808(32.70, 0.90, drive=1.5, punch_hz=145.0), True),
        ("808_punch_f1.wav", "808 Punch F1", "w", synth_tuned_808(43.65, 0.80, drive=1.8, punch_hz=155.0), True),
        ("808_trap_snare.wav", "Trap Snare", "e", synth_crisp_snare(0.28), False),
        ("808_closed_hat.wav", "Closed Hat", "a", synth_hihat(open_hat=False), True),
        ("808_open_hat.wav", "Open Hat", "s", synth_hihat(open_hat=True), True),
        ("808_rim_clap.wav", "808 Rim / Clap", "d", synth_perc_clap(0.25), False),
        ("808_dist_g1.wav", "Distorted 808 G1", "z", synth_tuned_808(49.00, 0.85, drive=3.1, punch_hz=160.0), True),
        ("808_glide_bb1.wav", "Glide 808 Bb1", "x", synth_tuned_808(58.27, 0.90, drive=2.2, punch_hz=120.0, glide_ratio=1.5), True),
        ("808_sub_drop.wav", "808 Sub Drop", "c", synth_tuned_808(29.14, 1.25, drive=1.9, punch_hz=190.0, glide_ratio=0.75), True),
    ]

    # 2. Pads 10-36: Full 3-Octave Tuned 808 Sub Matrix (Clean Sub, Saturated 808, and Glide 808s)
    # Chromatic / Minor Bass Notes from C1 (MIDI 24) to G3 (MIDI 55)
    bass_midi_notes = [
        24, 26, 27, 29, 31, 32, 34, 36, 38,   # Pads 10-18 (R-N): Clean Round Sub 808s (C1 - D2)
        39, 41, 43, 44, 46, 48, 50, 51, 53,   # Pads 19-27 (U-.): Overdriven / Saturated 808s (Eb2 - F3)
        36, 39, 41, 43, 46, 48, 51, 53, 55,   # Pads 28-36 (1-9): Pitch-Glide / Drill Slide 808s (C2 - G3)
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = bass_midi_notes[step % len(bass_midi_notes)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            audio = synth_tuned_808(root_freq=freq, duration=0.85, drive=1.4, punch_hz=130.0)
            label = f"Sub 808 {n_lbl}"
        elif step < 18:
            audio = synth_tuned_808(root_freq=freq, duration=0.80, drive=3.0, punch_hz=150.0)
            label = f"Dist 808 {n_lbl}"
        else:
            glide = 1.498 if (step % 2 == 0) else 0.749  # Alternate 5th-up and 4th-down slides
            audio = synth_tuned_808(root_freq=freq, duration=0.85, drive=2.3, punch_hz=110.0, glide_ratio=glide)
            label = f"Slide 808 {n_lbl}"

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, True))

    return pads