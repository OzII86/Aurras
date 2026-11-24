# core/packs/pack_cyber_industrial.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, lfilter, sawtooth, butter, finalize_stereo
)

PACK_NAME = "Cyber_Industrial"
DEFAULT_BPM = 130.0


def synth_doom_kick(duration: float = 0.6) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = 38.0 + 180.0 * np.exp(-t * 32.0)
    phase = np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)
    sub = np.sin(phase) * np.exp(-t * 4.5)
    buzz = sawtooth(phase * 2.0) * np.exp(-t * 18.0) * 0.45
    return finalize_stereo(np.tanh((sub + buzz) * 2.8))


def synth_gated_snare(duration: float = 0.28) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    body = np.sin(2.0 * np.pi * 195.0 * t) * np.exp(-t * 18.0)
    rng = np.random.default_rng(11)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(2, 900.0 / (SAMPLE_RATE / 2.0), "high")
    gated_env = np.where(t < 0.18, 1.0, np.exp(-(t - 0.18) * 65.0)).astype(np.float32)
    return finalize_stereo(np.tanh((body * 0.6 + lfilter(b, a, noise) * gated_env * 0.5) * 1.8))


def synth_anvil_hit(duration: float = 0.45) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freqs = [540.0, 825.0, 1190.0, 1740.0, 2410.0, 3180.0]
    sig_sum = np.zeros_like(t)
    for idx, f in enumerate(freqs):
        sig_sum += np.sin(2.0 * np.pi * f * t + np.sin(2.0 * np.pi * (f * 1.414) * t) * 1.5) * np.exp(-t * (8.0 + idx * 5.0))
    return finalize_stereo(np.tanh(sig_sum * 1.4))


def synth_steam_valve(duration: float = 0.35) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(99)
    noise = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(2, [1800.0 / (SAMPLE_RATE / 2.0), 5500.0 / (SAMPLE_RATE / 2.0)], "band")
    env = (1.0 - np.exp(-t * 90.0)) * np.exp(-t * 9.0)
    return finalize_stereo(lfilter(b, a, noise) * env.astype(np.float32))


def synth_acid_303(duration: float = 0.45, freq: float = 65.41) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    raw = sawtooth(2.0 * np.pi * freq * t)
    b, a = butter(3, 950.0 / (SAMPLE_RATE / 2.0), "low")
    filt = lfilter(b, a, raw)
    zap = np.sin(2.0 * np.pi * (freq * 4.0 + 900.0 * np.exp(-t * 26.0)) * t) * np.exp(-t * 16.0) * 0.45
    env = np.exp(-t * 5.5).astype(np.float32)
    return finalize_stereo(np.tanh((filt + zap) * env * 2.2))


def synth_bitcrush_bass(duration: float = 0.65, freq: float = 55.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    wave = sawtooth(2.0 * np.pi * freq * t) + np.sin(2.0 * np.pi * (freq * 0.5) * t)
    crushed = np.round(wave * 6.0) / 6.0
    crushed = np.repeat(crushed[::4], 4)[:len(t)]
    b, a = butter(2, 1600.0 / (SAMPLE_RATE / 2.0), "low")
    env = np.exp(-t * 3.8).astype(np.float32)
    return finalize_stereo(lfilter(b, a, crushed) * env)


def synth_dystopian_horn(duration: float = 1.1, freq: float = 65.41) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    detunes = [0.992, 0.997, 1.0, 1.004, 1.009]
    left = np.zeros_like(t)
    right = np.zeros_like(t)
    for i, d in enumerate(detunes):
        s = sawtooth(2.0 * np.pi * (freq * d) * t)
        left += s * (0.8 - i * 0.1)
        right += s * (0.4 + i * 0.1)
    b, a = butter(2, 750.0 / (SAMPLE_RATE / 2.0), "low")
    env = ((1.0 - np.exp(-t * 18.0)) * np.exp(-t * 2.2)).astype(np.float32)
    return finalize_stereo(np.column_stack((lfilter(b, a, left) * env, lfilter(b, a, right) * env)))


def synth_dark_choir_pad(duration: float = 1.25) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    notes = [130.81, 155.56, 196.00, 261.63]
    raw_l = np.zeros_like(t)
    raw_r = np.zeros_like(t)
    for f in notes:
        raw_l += sawtooth(2.0 * np.pi * (f * 0.998) * t)
        raw_r += sawtooth(2.0 * np.pi * (f * 1.002) * t)
    b1, a1 = butter(2, [600.0 / (SAMPLE_RATE / 2.0), 900.0 / (SAMPLE_RATE / 2.0)], "band")
    b2, a2 = butter(2, [1050.0 / (SAMPLE_RATE / 2.0), 1450.0 / (SAMPLE_RATE / 2.0)], "band")
    env = ((1.0 - np.exp(-t * 10.0)) * np.exp(-t * 1.8)).astype(np.float32)
    out_l = (lfilter(b1, a1, raw_l) + lfilter(b2, a2, raw_l) * 0.6) * env
    out_r = (lfilter(b1, a1, raw_r) + lfilter(b2, a2, raw_r) * 0.6) * env
    return finalize_stereo(np.column_stack((out_l, out_r)))


def synth_cyber_riser(duration: float = 0.8) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    step_idx = np.floor(t * 16.0)
    freq = 180.0 * (1.06 ** step_idx)
    phase = np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)
    sig_out = np.sign(np.sin(phase)).astype(np.float32) * (t / duration)
    b, a = butter(2, 2400.0 / (SAMPLE_RATE / 2.0), "low")
    return finalize_stereo(lfilter(b, a, sig_out))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("doom_kick.wav", "Doom Sub Kick", "q", synth_doom_kick(), True),
        ("gated_snare.wav", "Gated Snare", "w", synth_gated_snare(), False),
        ("anvil_clank.wav", "Anvil Clank", "e", synth_anvil_hit(), False),
        ("steam_valve.wav", "Steam Valve", "a", synth_steam_valve(), True),
        ("acid_303.wav", "Acid 303 Bass", "s", synth_acid_303(), True),
        ("bitcrush_bass.wav", "Bitcrush Sub", "d", synth_bitcrush_bass(), True),
        ("dystopian_horn.wav", "Dystopian Horn", "z", synth_dystopian_horn(), True),
        ("dark_choir.wav", "Dark Choir Pad", "x", synth_dark_choir_pad(), True),
        ("cyber_riser.wav", "Cyber Riser FX", "c", synth_cyber_riser(), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        if step < 9:
            m_note = 36 + step * 2
            audio = synth_acid_303(0.42, freq=midi_to_freq(m_note))
            label, choke = f"Acid {midi_to_label(m_note)}", True
        elif step < 18:
            m_note = 36 + (step - 9) * 2
            audio = synth_bitcrush_bass(0.55, freq=midi_to_freq(m_note))
            label, choke = f"Crush {midi_to_label(m_note)}", True
        else:
            audio = synth_dystopian_horn(0.65, freq=freq * 0.5)
            label, choke = f"Braam {n_lbl}", True

        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, choke))

    return pads