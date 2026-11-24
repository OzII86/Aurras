# core/packs/dsp_primitives.py
from typing import cast
import numpy as np
import scipy.signal as sig

SAMPLE_RATE = 44100

FULL_36_KEYS = [
    "q", "w", "e", "a", "s", "d", "z", "x", "c",
    "r", "t", "y", "f", "g", "h", "v", "b", "n",
    "u", "i", "o", "j", "k", "l", "m", ",", ".",
    "1", "2", "3", "4", "5", "6", "7", "8", "9"
]

C_MINOR_SCALE_MIDI = [
    36, 39, 41, 43, 46, 48, 51, 53, 55,
    58, 60, 63, 65, 67, 70, 72, 75, 77,
    79, 82, 84, 87, 89, 91, 94, 96, 99
]
NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def midi_to_freq(midi_note: int) -> float:
    return float(440.0 * (2.0 ** ((midi_note - 69) / 12.0)))


def midi_to_label(midi_note: int) -> str:
    return f"{NOTE_NAMES[midi_note % 12]}{(midi_note // 12) - 1}"


def lfilter(b: np.ndarray, a: np.ndarray, x: np.ndarray) -> np.ndarray:
    res = sig.lfilter(b, a, x)
    if isinstance(res, tuple):
        return np.asarray(res[0], dtype=np.float32)
    return np.asarray(res, dtype=np.float32)


def sawtooth(phase: np.ndarray, width: float = 1.0) -> np.ndarray:
    return np.asarray(sig.sawtooth(phase, width=width), dtype=np.float32)


def butter(order: int, wn: float | list[float], btype: str) -> tuple[np.ndarray, np.ndarray]:
    res = sig.butter(order, wn, btype=btype, output="ba")  # type: ignore
    b, a = cast(tuple[np.ndarray, np.ndarray], res)
    return np.asarray(b, dtype=np.float64), np.asarray(a, dtype=np.float64)


def finalize_stereo(audio: np.ndarray, tail_ms: float = 15.0) -> np.ndarray:
    data = np.asarray(audio, dtype=np.float32)
    peak = float(np.max(np.abs(data)))
    if peak > 0.0001:
        data = (data / peak) * 0.88

    fade_len = min(len(data), int(SAMPLE_RATE * (tail_ms / 1000.0)))
    if fade_len > 1:
        curve = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
        if data.ndim > 1:
            data[-fade_len:] *= curve.reshape(-1, 1)
        else:
            data[-fade_len:] *= curve

    if data.ndim == 1:
        return np.column_stack((data, data))
    return data


def karplus_strong_pluck(freq: float, duration: float, decay: float = 0.994, brightness: float = 0.5) -> np.ndarray:
    n_samples = int(SAMPLE_RATE * duration)
    delay_len = max(2, int(SAMPLE_RATE / freq))
    rng = np.random.default_rng(int(freq * 100))
    ring_buf = rng.uniform(-1.0, 1.0, delay_len).astype(np.float32)

    out = np.zeros(n_samples, dtype=np.float32)
    for i in range(n_samples):
        idx = i % delay_len
        next_idx = (idx + 1) % delay_len
        out[i] = ring_buf[idx]
        avg = (1.0 - brightness) * ring_buf[idx] + brightness * ring_buf[next_idx]
        ring_buf[idx] = avg * decay
    return out