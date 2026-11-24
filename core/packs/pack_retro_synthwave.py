# core/packs/pack_retro_synthwave.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo
)

PACK_NAME = "Retro_Synthwave"
DEFAULT_BPM = 118.0


def synth_80s_gated_tom(duration: float = 0.42, start_f: float = 160.0, end_f: float = 65.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = end_f + (start_f - end_f) * np.exp(-t * 14.0)
    body = np.sin(np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)) * np.exp(-t * 5.0)
    rng = np.random.default_rng(84)
    verb = rng.standard_normal(len(t)).astype(np.float32) * 0.25
    gate = np.where(t < 0.28, 1.0, np.exp(-(t - 0.28) * 55.0)).astype(np.float32)
    return finalize_stereo((body + verb) * gate)


def synth_juno_brass_stab(duration: float = 0.65, root_freq: float = 130.81) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    ratios = [1.0, 1.2, 1.5, 2.0]
    left = np.zeros_like(t)
    right = np.zeros_like(t)
    for r in ratios:
        left += sawtooth(2.0 * np.pi * (root_freq * r * 0.996) * t)
        right += sawtooth(2.0 * np.pi * (root_freq * r * 1.004) * t)
    b, a = butter(2, 1900.0 / (SAMPLE_RATE / 2.0), "low")
    env = ((1.0 - np.exp(-t * 35.0)) * np.exp(-t * 3.5)).astype(np.float32)
    return finalize_stereo(np.column_stack((lfilter(b, a, left) * env, lfilter(b, a, right) * env)))


def synth_outrun_bass(duration: float = 0.35, freq: float = 65.41) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    pwm = np.sign(np.sin(2.0 * np.pi * freq * t) - 0.3).astype(np.float32)
    saw = sawtooth(2.0 * np.pi * (freq * 2.0) * t) * 0.5
    b, a = butter(3, 1100.0 / (SAMPLE_RATE / 2.0), "low")
    env = np.exp(-t * 7.5).astype(np.float32)
    return finalize_stereo(lfilter(b, a, pwm + saw) * env)


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("linn_kick.wav", "80s Punch Kick", "q", synth_80s_gated_tom(0.35, 140.0, 45.0), True),
        ("gated_tom_hi.wav", "Gated Tom Hi", "w", synth_80s_gated_tom(0.42, 190.0, 85.0), False),
        ("gated_tom_lo.wav", "Gated Tom Lo", "e", synth_80s_gated_tom(0.45, 130.0, 58.0), False),
        ("outrun_bass_c2.wav", "Outrun Bass C2", "a", synth_outrun_bass(0.35, 65.41), True),
        ("outrun_bass_eb2.wav", "Outrun Bass Eb2", "s", synth_outrun_bass(0.35, 77.78), True),
        ("outrun_bass_g2.wav", "Outrun Bass G2", "d", synth_outrun_bass(0.35, 98.00), True),
        ("juno_stab_cm.wav", "Juno Stab Cm", "z", synth_juno_brass_stab(0.65, 130.81), True),
        ("juno_stab_fm.wav", "Juno Stab Fm", "x", synth_juno_brass_stab(0.65, 174.61), True),
        ("juno_stab_gm.wav", "Juno Stab Gm", "c", synth_juno_brass_stab(0.65, 196.00), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 12:
            audio = synth_outrun_bass(0.35, freq=midi_to_freq(36 + step))
            label, choke = f"Analog Bass {midi_to_label(36 + step)}", True
        else:
            audio = synth_juno_brass_stab(0.55, root_freq=freq)
            label, choke = f"Juno Lead {n_lbl}", False

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads