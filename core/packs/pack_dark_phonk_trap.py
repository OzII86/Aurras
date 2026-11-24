# core/packs/pack_dark_phonk_trap.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo
)

PACK_NAME = "Dark_Phonk_Trap"
DEFAULT_BPM = 140.0


def synth_phonk_cowbell(duration: float = 0.38, root_freq: float = 540.0) -> np.ndarray:
    """ Classic TR-808 Drift Phonk pitched cowbell (540Hz + 800Hz ratio with band-pass bite)."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    f1 = root_freq
    f2 = root_freq * (800.0 / 540.0)
    sq1 = np.sign(np.sin(2.0 * np.pi * f1 * t)).astype(np.float32)
    sq2 = np.sign(np.sin(2.0 * np.pi * f2 * t)).astype(np.float32)
    b, a = butter(2, [450.0 / (SAMPLE_RATE / 2.0), 2600.0 / (SAMPLE_RATE / 2.0)], "band")
    env = ((1.0 - np.exp(-t * 250.0)) * np.exp(-t * 9.5)).astype(np.float32)
    bell = np.tanh(lfilter(b, a, (sq1 + sq2) * 0.6) * env * 2.2)
    return finalize_stereo(bell)


def synth_clipped_808(duration: float = 0.70, sub_freq: float = 43.65) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = sub_freq + 140.0 * np.exp(-t * 34.0)
    phase = np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)
    raw = np.sin(phase) * np.exp(-t * 4.0)
    b, a = butter(2, 320.0 / (SAMPLE_RATE / 2.0), "low")
    return finalize_stereo(lfilter(b, a, np.tanh(raw * 3.2)))


def synth_trap_snare(duration: float = 0.24) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    pop = np.sin(2.0 * np.pi * (240.0 + 180.0 * np.exp(-t * 45.0)) * t) * np.exp(-t * 28.0)
    rng = np.random.default_rng(14)
    snap = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t * 22.0)
    b, a = butter(2, 1600.0 / (SAMPLE_RATE / 2.0), "high")
    return finalize_stereo(pop * 0.6 + lfilter(b, a, snap) * 0.6)


def synth_hihat_roll(duration: float = 0.25, hits: int = 4) -> np.ndarray:
    """ Rapid 1/32 trap hi-hat stutter roll in a single pad trigger."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(81)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(3, 6800.0 / (SAMPLE_RATE / 2.0), "high")
    crisp = lfilter(b, a, noise)
    step_len = duration / hits
    env = np.exp(-((t % step_len) * 85.0)).astype(np.float32)
    return finalize_stereo(crisp * env)


def synth_memphis_vox_chop(duration: float = 0.45, freq: float = 196.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    src = sawtooth(2.0 * np.pi * freq * t) + 0.5 * sawtooth(2.0 * np.pi * (freq * 1.5) * t)
    b, a = butter(2, [550.0 / (SAMPLE_RATE / 2.0), 2200.0 / (SAMPLE_RATE / 2.0)], "band")
    env = np.exp(-t * 5.0).astype(np.float32)
    return finalize_stereo(np.tanh(lfilter(b, a, src) * env * 2.0))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("phonk_808_kick.wav", "Clipped 808 Kick", "q", synth_clipped_808(0.65, 43.65), True),
        ("trap_snare.wav", "Crispy Trap Snare", "w", synth_trap_snare(), False),
        ("hat_roll_4x.wav", "Hat Roll 4x", "e", synth_hihat_roll(0.24, 4), True),
        ("cowbell_c5.wav", "Phonk Bell C5", "a", synth_phonk_cowbell(0.38, 523.25), True),
        ("cowbell_eb5.wav", "Phonk Bell Eb5", "s", synth_phonk_cowbell(0.38, 622.25), True),
        ("cowbell_g5.wav", "Phonk Bell G5", "d", synth_phonk_cowbell(0.38, 783.99), True),
        ("sub_808_g1.wav", "808 Glide G1", "z", synth_clipped_808(0.75, 49.00), True),
        ("vox_chop_lo.wav", "LoFi Vox Chop", "x", synth_memphis_vox_chop(0.45, 196.0), True),
        ("hat_roll_6x.wav", "Fast Roll 6x", "c", synth_hihat_roll(0.24, 6), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 18:
            # Pitched Drift Phonk Cowbell Scale across 2 octaves
            audio = synth_phonk_cowbell(0.36, root_freq=freq * 2.0)
            label, choke = f"Cowbell {n_lbl}", True
        else:
            # Pitched 808 Sub Bass Scale
            sub_midi = 36 + (step - 18)
            audio = synth_clipped_808(0.65, sub_freq=midi_to_freq(sub_midi))
            label, choke = f"808 Sub {midi_to_label(sub_midi)}", True

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads