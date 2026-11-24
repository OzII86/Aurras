# core/packs/pack_lofi_midnight.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo, karplus_strong_pluck
)

PACK_NAME = "LoFi_Midnight"
DEFAULT_BPM = 84.0


def synth_lofi_kick(duration: float = 0.45) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = 50.0 + 85.0 * np.exp(-t * 35.0)
    phase = np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)
    thump = np.sin(phase) * np.exp(-t * 7.5)
    b, a = butter(2, 420.0 / (SAMPLE_RATE / 2.0), "low")
    return finalize_stereo(lfilter(b, a, np.tanh(thump * 1.5)))


def synth_lazy_rim_snare(duration: float = 0.24) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    rim = np.sin(2.0 * np.pi * 480.0 * t) * np.exp(-t * 55.0) * 0.7
    rng = np.random.default_rng(19)
    dust = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t * 24.0) * 0.4
    b, a = butter(2, 2600.0 / (SAMPLE_RATE / 2.0), "low")
    return finalize_stereo(lfilter(b, a, rim + dust))


def synth_shaker(duration: float = 0.16) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(88)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(2, [3500.0 / (SAMPLE_RATE / 2.0), 8500.0 / (SAMPLE_RATE / 2.0)], "band")
    env = np.sin(np.pi * (t / duration)) ** 2
    return finalize_stereo(lfilter(b, a, noise) * env.astype(np.float32))


def synth_rhodes_chord(duration: float = 1.2, root_freq: float = 174.61) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freqs = [root_freq, root_freq * 1.25, root_freq * 1.5, root_freq * 1.875]
    voice = np.zeros_like(t)
    for f in freqs:
        tine = np.sin(2.0 * np.pi * (f * 7.0) * t) * np.exp(-t * 22.0) * 0.45
        body = np.sin(2.0 * np.pi * f * t + tine) * np.exp(-t * 2.4)
        voice += body
    trem_l = (0.75 + 0.25 * np.sin(2.0 * np.pi * 4.5 * t)).astype(np.float32)
    trem_r = (0.75 - 0.25 * np.sin(2.0 * np.pi * 4.5 * t)).astype(np.float32)
    return finalize_stereo(np.column_stack((voice * trem_l, voice * trem_r)))


def synth_upright_bass(duration: float = 0.65, freq: float = 73.42) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    pluck = karplus_strong_pluck(freq, duration, decay=0.992, brightness=0.25)
    sub = np.sin(2.0 * np.pi * freq * t) * np.exp(-t * 4.5) * 0.8
    return finalize_stereo(pluck + sub.astype(np.float32))


def synth_vibraphone(duration: float = 1.0, freq: float = 392.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    motor = 0.8 + 0.2 * np.sin(2.0 * np.pi * 6.2 * t)
    bar = (np.sin(2.0 * np.pi * freq * t) + 0.2 * np.sin(2.0 * np.pi * (freq * 4.0) * t) * np.exp(-t * 18.0)) * motor
    env = np.exp(-t * 2.8).astype(np.float32)
    return finalize_stereo((bar * env).astype(np.float32))


def synth_muted_horn(duration: float = 0.75, freq: float = 293.66) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    brass = sawtooth(2.0 * np.pi * freq * t)
    b, a = butter(2, [650.0 / (SAMPLE_RATE / 2.0), 1950.0 / (SAMPLE_RATE / 2.0)], "band")
    env = ((1.0 - np.exp(-t * 20.0)) * np.exp(-t * 3.5)).astype(np.float32)
    return finalize_stereo(lfilter(b, a, brass) * env)


def synth_tape_flute(duration: float = 0.85, freq: float = 523.25) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    wow = 1.0 + 0.005 * np.sin(2.0 * np.pi * 3.2 * t)
    phase = np.cumsum(2.0 * np.pi * (freq * wow) / SAMPLE_RATE)
    tri = sawtooth(phase, width=0.5)
    rng = np.random.default_rng(33)
    breath = rng.standard_normal(len(t)).astype(np.float32) * 0.08
    b, a = butter(2, 1600.0 / (SAMPLE_RATE / 2.0), "low")
    env = ((1.0 - np.exp(-t * 16.0)) * np.exp(-t * 2.6)).astype(np.float32)
    return finalize_stereo(lfilter(b, a, tri + breath) * env)


def synth_vinyl_texture(duration: float = 1.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(123)
    hiss = rng.standard_normal(len(t)).astype(np.float32) * 0.08
    pops = np.where(rng.random(len(t)) > 0.9985, rng.uniform(-0.8, 0.8, len(t)), 0.0).astype(np.float32)
    b, a = butter(2, [500.0 / (SAMPLE_RATE / 2.0), 4200.0 / (SAMPLE_RATE / 2.0)], "band")
    return finalize_stereo(lfilter(b, a, hiss + pops))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("dusty_kick.wav", "Dusty Kick", "q", synth_lofi_kick(), True),
        ("lazy_rim_snare.wav", "Lazy Rimshot", "w", synth_lazy_rim_snare(), False),
        ("shaker_groove.wav", "Warm Shaker", "e", synth_shaker(), True),
        ("rhodes_fmaj7.wav", "Rhodes FMaj7", "a", synth_rhodes_chord(), True),
        ("upright_bass.wav", "Upright Bass", "s", synth_upright_bass(), True),
        ("vibraphone_g4.wav", "Vibraphone G4", "d", synth_vibraphone(), False),
        ("muted_horn.wav", "Muted Horn D4", "z", synth_muted_horn(), True),
        ("tape_flute.wav", "Tape Flute C5", "x", synth_tape_flute(), True),
        ("vinyl_crackle.wav", "Vinyl Texture", "c", synth_vinyl_texture(), False),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            u_midi = 36 + step * 2
            audio = synth_upright_bass(0.60, freq=midi_to_freq(u_midi))
            label, choke = f"Upright {midi_to_label(u_midi)}", True
        elif step < 18:
            audio = synth_vibraphone(0.85, freq=freq)
            label, choke = f"Vibes {n_lbl}", False
        else:
            audio = synth_rhodes_chord(1.0, root_freq=freq * 0.5)
            label, choke = f"Rhodes {n_lbl}", True

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads