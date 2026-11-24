# core/packs/pack_starter.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo
)

PACK_NAME = "Starter_Pack"
DEFAULT_BPM = 120.0


def synth_808_kick(duration: float = 0.65) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = 44.0 + 111.0 * np.exp(-t * 28.0)
    phase = np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)
    body = np.sin(phase) * np.exp(-t * 5.2)
    click = np.sin(2.0 * np.pi * 1100.0 * t) * np.exp(-t * 140.0) * 0.35
    return finalize_stereo(np.tanh((body + click) * 1.6))


def synth_crisp_snare(duration: float = 0.32) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    tone1 = np.sin(2.0 * np.pi * 185.0 * t) * np.exp(-t * 24.0)
    tone2 = np.sin(2.0 * np.pi * 330.0 * t) * np.exp(-t * 32.0)
    rng = np.random.default_rng(42)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(2, 1200.0 / (SAMPLE_RATE / 2.0), "high")
    wires = lfilter(b, a, noise) * np.exp(-t * 15.5)
    return finalize_stereo((tone1 * 0.45) + (tone2 * 0.25) + (wires * 0.65))


def synth_hihat(duration: float = 0.08, open_hat: bool = False) -> np.ndarray:
    if open_hat:
        duration = 0.45
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    ratios = [205.3, 304.4, 369.6, 522.7, 540.0, 800.0]
    metal = np.zeros_like(t, dtype=np.float32)
    for f in ratios:
        metal += np.sign(np.sin(2.0 * np.pi * f * t)).astype(np.float32)
    rng = np.random.default_rng(101)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    metal = (metal * 0.5) + (noise * 0.5)
    b, a = butter(3, 6500.0 / (SAMPLE_RATE / 2.0), "high")
    filtered = lfilter(b, a, metal)
    env = np.exp(-t * (6.5 if open_hat else 48.0)).astype(np.float32)
    return finalize_stereo(filtered * env)


def synth_perc_clap(duration: float = 0.28) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(77)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(2, [900.0 / (SAMPLE_RATE / 2.0), 3800.0 / (SAMPLE_RATE / 2.0)], "band")
    band_noise = lfilter(b, a, noise)
    env = np.zeros_like(t, dtype=np.float32)
    for delay_ms in (0.0, 0.011, 0.022):
        mask = t >= delay_ms
        env[mask] += np.exp(-(t[mask] - delay_ms) * 130.0) * 0.6
    env += np.exp(-t * 16.0) * 0.45
    rim = np.sin(2.0 * np.pi * 920.0 * t) * np.exp(-t * 85.0) * 0.4
    return finalize_stereo((band_noise * env) + rim)


def synth_industrial_bass(duration: float = 0.55, freq: float = 65.41) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    saw1 = sawtooth(2.0 * np.pi * (freq * 0.996) * t)
    saw2 = sawtooth(2.0 * np.pi * (freq * 1.004) * t)
    sub = (np.sin(2.0 * np.pi * (freq * 0.5) * t) * 1.2).astype(np.float32)
    b, a = butter(3, 520.0 / (SAMPLE_RATE / 2.0), "low")
    filt_l = lfilter(b, a, (saw1 * 0.5) + (sub * 0.6))
    filt_r = lfilter(b, a, (saw2 * 0.5) + (sub * 0.6))
    env = ((1.0 - np.exp(-t * 180.0)) * np.exp(-t * 4.2)).astype(np.float32)
    return finalize_stereo(np.column_stack((np.tanh(filt_l * env * 1.8), np.tanh(filt_r * env * 1.8))))


def _piano_voice(t: np.ndarray, freq: float) -> np.ndarray:
    mod_env = np.exp(-t * 14.0) * 2.2
    modulator = np.sin(2.0 * np.pi * (freq * 2.0) * t) * mod_env
    carrier = np.sin((2.0 * np.pi * freq * t) + modulator)
    harm2 = np.sin(2.0 * np.pi * (freq * 2.0) * t) * 0.30 * np.exp(-t * 7.0)
    harm3 = np.sin(2.0 * np.pi * (freq * 3.0) * t) * 0.12 * np.exp(-t * 11.0)
    amp_env = (1.0 - np.exp(-t * 350.0)) * np.exp(-t * 3.2)
    return ((carrier + harm2 + harm3) * amp_env).astype(np.float32)


def synth_piano_note(duration: float = 0.85, freq: float = 261.63) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    return finalize_stereo(np.column_stack((_piano_voice(t, freq * 0.999), _piano_voice(t, freq * 1.001))))


def synth_piano_chord(duration: float = 1.15) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    chord_freqs = [130.81, 196.00, 233.08, 293.66, 311.13]
    left = np.zeros_like(t, dtype=np.float32)
    right = np.zeros_like(t, dtype=np.float32)
    for idx, f in enumerate(chord_freqs):
        v = _piano_voice(t, f)
        left += v * float(0.75 - (idx * 0.08))
        right += v * float(0.45 + (idx * 0.08))
    return finalize_stereo(np.column_stack((left, right)))


def synth_cyber_pluck(duration: float = 0.45, freq: float = 196.00) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    s1 = sawtooth(2.0 * np.pi * (freq * 0.995) * t)
    s2 = sawtooth(2.0 * np.pi * (freq * 1.005) * t)
    sq = (np.sign(np.sin(2.0 * np.pi * (freq * 2.0) * t)) * 0.35).astype(np.float32)
    b, a = butter(2, 1800.0 / (SAMPLE_RATE / 2.0), "low")
    env = ((1.0 - np.exp(-t * 400.0)) * np.exp(-t * 9.5)).astype(np.float32)
    return finalize_stereo(np.column_stack((lfilter(b, a, s1 + sq) * env, lfilter(b, a, s2 + sq) * env)))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("kick_808.wav", "808 Sub Kick", "q", synth_808_kick(), True),
        ("snare_crisp.wav", "Crisp Snare", "w", synth_crisp_snare(), False),
        ("hihat_closed.wav", "Closed Hat", "e", synth_hihat(open_hat=False), True),
        ("hihat_open.wav", "Open Hat", "a", synth_hihat(open_hat=True), True),
        ("perc_clap.wav", "Clap / Rim", "s", synth_perc_clap(), False),
        ("bass_industrial.wav", "Industrial Bass", "d", synth_industrial_bass(), True),
        ("piano_c4.wav", "Grand Piano C4", "z", synth_piano_note(), False),
        ("chord_cm9.wav", "Dark Keys Cm9", "x", synth_piano_chord(), True),
        ("synth_pluck.wav", "Cyber Pluck G3", "c", synth_cyber_pluck(), False),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            b_midi = 36 + step * 2
            audio = synth_industrial_bass(0.50, freq=midi_to_freq(b_midi))
            label, choke = f"Sub Bass {midi_to_label(b_midi)}", True
        elif step < 18:
            audio = synth_piano_note(0.80, freq=freq)
            label, choke = f"Piano {n_lbl}", False
        else:
            audio = synth_cyber_pluck(0.45, freq=freq)
            label, choke = f"Synth {n_lbl}", False

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads