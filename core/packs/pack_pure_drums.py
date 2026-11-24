# core/packs/pack_pure_drums.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, lfilter, butter, finalize_stereo
)
from core.packs.pack_starter import synth_crisp_snare, synth_hihat, synth_perc_clap, synth_808_kick
from core.packs.pack_lofi_midnight import synth_lofi_kick, synth_lazy_rim_snare, synth_shaker

PACK_NAME = "Pure_Acoustic_Drums"
DEFAULT_BPM = 115.0


def synth_acoustic_tom(duration: float = 0.48, start_freq: float = 140.0, end_freq: float = 82.0) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freq = end_freq + (start_freq - end_freq) * np.exp(-t * 18.0)
    phase = np.cumsum(2.0 * np.pi * freq / SAMPLE_RATE)
    shell = (np.sin(phase) + 0.25 * np.sin(phase * 1.58)) * np.exp(-t * 6.5)
    stick = np.sin(2.0 * np.pi * 1600.0 * t) * np.exp(-t * 110.0) * 0.25
    return finalize_stereo(np.tanh((shell + stick) * 1.4))


def synth_cymbal(duration: float = 0.95, mode: str = "crash") -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freqs = [312.0, 468.0, 695.0, 1042.0, 1580.0, 2420.0, 3890.0]
    cym = np.zeros_like(t)
    for f in freqs:
        cym += np.sin(2.0 * np.pi * f * t + np.sin(2.0 * np.pi * (f * 1.37) * t) * 2.0)
    rng = np.random.default_rng(202)
    sizzle = rng.standard_normal(len(t)).astype(np.float32)
    b, a = butter(2, 3200.0 / (SAMPLE_RATE / 2.0), "high")
    shimmer = lfilter(b, a, (cym * 0.45) + (sizzle * 0.55))

    if mode == "bell":
        ping = np.sin(2.0 * np.pi * 1380.0 * t) * np.exp(-t * 6.0) * 0.7
        shimmer = (shimmer * np.exp(-t * 5.0)) + ping
    elif mode == "ride":
        ping = np.sin(2.0 * np.pi * 980.0 * t) * np.exp(-t * 9.0) * 0.4
        shimmer = (shimmer * np.exp(-t * 4.2)) + ping
    else:
        shimmer = shimmer * np.exp(-t * 3.0)
    return finalize_stereo(shimmer.astype(np.float32))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("studio_kick.wav", "Studio Kick", "q", synth_lofi_kick(0.5), True),
        ("studio_snare.wav", "Birch Snare", "w", synth_crisp_snare(0.32), False),
        ("hat_closed.wav", "Closed Hat", "e", synth_hihat(open_hat=False), True),
        ("hat_open.wav", "Open Hat", "a", synth_hihat(open_hat=True), True),
        ("rack_tom_hi.wav", "High Rack Tom", "s", synth_acoustic_tom(0.42, 175.0, 110.0), False),
        ("floor_tom_lo.wav", "Low Floor Tom", "d", synth_acoustic_tom(0.55, 98.0, 55.0), False),
        ("crash_cymbal.wav", "Crash Cymbal", "z", synth_cymbal(0.95, "crash"), False),
        ("ride_cymbal.wav", "Ride Cymbal", "x", synth_cymbal(0.85, "ride"), False),
        ("sidestick_rim.wav", "Rimshot Click", "c", synth_perc_clap(0.25), False),
    ]

    drum_extras = [
        ("Tom 1 Hi", synth_acoustic_tom(0.40, 195.0, 125.0), False),
        ("Tom 2 Mid", synth_acoustic_tom(0.45, 155.0, 95.0), False),
        ("Tom 3 MidLo", synth_acoustic_tom(0.50, 125.0, 72.0), False),
        ("Tom 4 Floor", synth_acoustic_tom(0.58, 90.0, 48.0), False),
        ("Ride Bell", synth_cymbal(0.65, "bell"), False),
        ("Splash Cym", synth_cymbal(0.45, "crash"), False),
        ("Ghost Snare", synth_lazy_rim_snare(0.18), False),
        ("Tight Shaker", synth_shaker(0.14), True),
        ("Sub Kick", synth_808_kick(0.55), True),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        d_label, d_audio, choke = drum_extras[step % len(drum_extras)]
        bank_num = (step // len(drum_extras)) + 1
        label = f"{d_label} V{bank_num}" if bank_num > 1 else d_label
        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_')}.wav"
        pads.append((fname, label, key, d_audio, choke))

    return pads