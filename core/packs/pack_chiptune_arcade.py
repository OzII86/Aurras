# core/packs/pack_chiptune_arcade.py
import numpy as np
from core.packs.dsp_primitives import (
    SAMPLE_RATE, FULL_36_KEYS, C_MINOR_SCALE_MIDI,
    midi_to_freq, midi_to_label, sawtooth, finalize_stereo
)

PACK_NAME = "Chiptune_Arcade"
DEFAULT_BPM = 128.0


def synth_8bit_pulse(freq: float = 261.63, duration: float = 0.35, duty: float = 0.25) -> np.ndarray:
    """NES 2A03 style pulse-wave oscillator with 4-bit amplitude quantization."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    phase = (t * freq) % 1.0
    pulse = np.where(phase < duty, 1.0, -1.0).astype(np.float32)
    env = np.round(np.exp(-t * 6.0) * 15.0) / 15.0
    return finalize_stereo(pulse * env.astype(np.float32))


def synth_8bit_arp_coin(duration: float = 0.35, base_f: float = 523.25) -> np.ndarray:
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
    freqs = np.where(t < 0.08, base_f, base_f * 1.5).astype(np.float32)
    phase = np.cumsum(2.0 * np.pi * freqs / SAMPLE_RATE)
    sq = np.sign(np.sin(phase)).astype(np.float32) * np.exp(-t * 5.5)
    return finalize_stereo(sq)


def synth_8bit_noise_drum(duration: float = 0.20, decimate: int = 8) -> np.ndarray:
    n_samples = int(SAMPLE_RATE * duration)
    rng = np.random.default_rng(64)
    raw = rng.choice([-1.0, 1.0], size=n_samples).astype(np.float32)
    stepped = np.repeat(raw[::decimate], decimate)[:n_samples]
    t = np.linspace(0, duration, n_samples, endpoint=False, dtype=np.float32)
    return finalize_stereo(stepped * np.exp(-t * 18.0).astype(np.float32))


def get_36_pads() -> list[tuple[str, str, str, np.ndarray, bool]]:
    pads: list[tuple[str, str, str, np.ndarray, bool]] = [
        ("chip_kick.wav", "8-Bit Kick", "q", synth_8bit_noise_drum(0.18, 22), True),
        ("chip_snare.wav", "8-Bit Snare", "w", synth_8bit_noise_drum(0.22, 6), False),
        ("chip_hat.wav", "8-Bit Hi-Hat", "e", synth_8bit_noise_drum(0.08, 2), True),
        ("coin_pickup.wav", "Arcade Coin", "a", synth_8bit_arp_coin(0.35, 587.33), False),
        ("powerup_arp.wav", "1-Up Arp", "s", synth_8bit_arp_coin(0.45, 392.00), False),
        ("tri_bass_c2.wav", "Tri Bass C2", "d", finalize_stereo(sawtooth(np.linspace(0, 0.4, int(SAMPLE_RATE * 0.4), dtype=np.float32) * 2 * np.pi * 65.41, 0.5)), True),
        ("pulse_c4.wav", "25% Pulse C4", "z", synth_8bit_pulse(261.63, 0.35, 0.25), False),
        ("pulse_eb4.wav", "25% Pulse Eb4", "x", synth_8bit_pulse(311.13, 0.35, 0.25), False),
        ("pulse_g4.wav", "25% Pulse G4", "c", synth_8bit_pulse(392.00, 0.35, 0.25), False),
    ]

    for idx in range(9, 36):
        key = FULL_36_KEYS[idx]
        step = idx - 9
        midi_n = C_MINOR_SCALE_MIDI[step % len(C_MINOR_SCALE_MIDI)]
        freq = midi_to_freq(midi_n)
        n_lbl = midi_to_label(midi_n)

        duty = 0.125 if (step % 2 == 0) else 0.5
        audio = synth_8bit_pulse(freq=freq, duration=0.35, duty=duty)
        label = f"Chip {n_lbl}"
        fname = f"pad_{idx + 1:02d}_{label.lower().replace(' ', '_').replace('#', 's')}.wav"
        pads.append((fname, label, key, audio, False))

    return pads