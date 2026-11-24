# core/packs/pack_gothic_cathedral.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo, karplus_strong_pluck
)

PACK_NAME = "Gothic_Cathedral"
DEFAULT_BPM = 96.0


def synth_war_taiko(duration: float = 0.75) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    f1 = 58.0 + 65.0 * np.exp(-t * 22.0)
    f2 = 87.0 + 40.0 * np.exp(-t * 18.0)
    drum = (np.sin(np.cumsum(2.0 * np.pi * f1 / SAMPLE_RATE)) + 0.5 * np.sin(np.cumsum(2.0 * np.pi * f2 / SAMPLE_RATE))) * np.exp(-t * 4.2)
    rng = np.random.default_rng(55)
    slap = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t * 60.0) * 0.35
    return finalize_stereo(np.tanh((drum + slap) * 1.7))


def synth_tubular_bell(duration: float = 1.3, freq: float = 261.63) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    mod = np.sin(2.0 * np.pi * (freq * 3.51) * t) * np.exp(-t * 5.0) * 3.0
    bell = np.sin(2.0 * np.pi * freq * t + mod) * np.exp(-t * 2.2)
    overtone = np.sin(2.0 * np.pi * (freq * 2.76) * t) * np.exp(-t * 4.5) * 0.35
    return finalize_stereo((bell + overtone).astype(np.float32))


def synth_dungeon_chains(duration: float = 0.42) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(73)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(3, 3800.0 / (SAMPLE_RATE / 2.0), "high")
    metal = lfilter(b, a, noise)
    env = np.zeros_like(t)
    for offset in (0.0, 0.045, 0.095, 0.15):
        m = t >= offset
        env[m] += np.exp(-(t[m] - offset) * 55.0)
    return finalize_stereo(metal * env)


def synth_pipe_organ_chord(duration: float = 1.2, root_freq: float = 146.83) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    notes = [root_freq, root_freq * 1.1892, root_freq * 1.4983, root_freq * 2.0]
    drawbars = [(0.5, 0.5), (1.0, 1.0), (2.0, 0.7), (3.0, 0.35), (4.0, 0.45)]
    left = np.zeros_like(t)
    right = np.zeros_like(t)
    for n in notes:
        for mult, amp in drawbars:
            left += np.sin(2.0 * np.pi * (n * mult * 0.999) * t) * amp
            right += np.sin(2.0 * np.pi * (n * mult * 1.001) * t) * amp
    env = ((1.0 - np.exp(-t * 25.0)) * np.exp(-t * 1.4)).astype(np.float32)
    return finalize_stereo(np.column_stack((left * env, right * env)))


def synth_pizzicato_strings(duration: float = 0.5, freq: float = 196.0) -> np.ndarray:
    p1 = karplus_strong_pluck(freq, duration, decay=0.988, brightness=0.35)
    p2 = karplus_strong_pluck(freq * 1.5, duration, decay=0.988, brightness=0.35)
    return finalize_stereo(np.column_stack((p1 + p2 * 0.5, p2 + p1 * 0.5)))


def synth_cello_bow(duration: float = 1.1, freq: float = 98.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    vibrato = np.sin(2.0 * np.pi * 5.2 * t) * 0.006
    inst_freq = freq * (1.0 + vibrato)
    phase = np.cumsum(2.0 * np.pi * inst_freq / SAMPLE_RATE)
    bow = sawtooth(phase)
    b, a = butter(2, 680.0 / (SAMPLE_RATE / 2.0), "low")
    env = ((1.0 - np.exp(-t * 9.0)) * np.exp(-t * 1.8)).astype(np.float32)
    return finalize_stereo(lfilter(b, a, bow) * env)


def synth_harpsichord(duration: float = 0.75, freq: float = 220.0) -> np.ndarray:
    s1 = karplus_strong_pluck(freq, duration, decay=0.996, brightness=0.52)
    s2 = karplus_strong_pluck(freq * 2.0, duration, decay=0.994, brightness=0.55) * 0.55
    return finalize_stereo(np.column_stack((s1 + s2, s1 * 0.8 + s2 * 1.1)))


def synth_glass_harp(duration: float = 1.1, freq: float = 587.33) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    shimmer = 1.0 + 0.15 * np.sin(2.0 * np.pi * 6.0 * t)
    tone = (np.sin(2.0 * np.pi * freq * t) + 0.25 * np.sin(2.0 * np.pi * (freq * 2.0) * t)) * shimmer
    env = ((1.0 - np.exp(-t * 14.0)) * np.exp(-t * 2.5)).astype(np.float32)
    return finalize_stereo(tone * env)


def synth_sub_drop(duration: float = 1.1) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = 110.0 * np.exp(-t * 1.4) + 28.0
    phase = np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)
    boom = np.sin(phase) * np.exp(-t * 2.1)
    return finalize_stereo(np.tanh(boom * 1.9))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("war_taiko.wav", "War Taiko", "q", synth_war_taiko(), True),
        ("tubular_bell.wav", "Cathedral Bell", "w", synth_tubular_bell(), False),
        ("dungeon_chains.wav", "Chain Rattle", "e", synth_dungeon_chains(), False),
        ("pipe_organ_dm.wav", "Pipe Organ Dm", "a", synth_pipe_organ_chord(), True),
        ("pizzicato_str.wav", "Pizzicato Str", "s", synth_pizzicato_strings(), False),
        ("cello_bow.wav", "Dark Cello G2", "d", synth_cello_bow(), True),
        ("harpsichord_a3.wav", "Harpsichord A3", "z", synth_harpsichord(), False),
        ("glass_harp.wav", "Glass Harp D5", "x", synth_glass_harp(), False),
        ("sub_drop_fx.wav", "Sub Drop Boom", "c", synth_sub_drop(), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            c_midi = 36 + step * 2
            audio = synth_cello_bow(0.95, freq=midi_to_freq(c_midi))
            label, choke = f"Cello {midi_to_label(c_midi)}", True
        elif step < 18:
            audio = synth_harpsichord(0.70, freq=freq)
            label, choke = f"Harpsi {n_lbl}", False
        else:
            audio = synth_pipe_organ_chord(1.0, root_freq=freq * 0.5)
            label, choke = f"Organ {n_lbl}", True

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads