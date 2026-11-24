import numpy as np
import scipy.signal as sig

class FourBandEQ:
    """
    Standalone Stateful 4-Band Parametric Equalizer.
    Splits audio into Bass (<100Hz), Low (100-800Hz), Mid (800-4kHz), and High (>4kHz).
    """
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        nyquist = sample_rate / 2.0
        
        # 4-Band Crossovers (Type-ignored due to Pylance stub limitations)
        self.b_bass, self.a_bass = sig.butter(2, 100 / nyquist, btype='low', output='ba')  # type: ignore
        self.b_low, self.a_low = sig.butter(2, [100 / nyquist, 800 / nyquist], btype='band', output='ba')  # type: ignore
        self.b_mid, self.a_mid = sig.butter(2, [800 / nyquist, 4000 / nyquist], btype='band', output='ba')  # type: ignore
        self.b_high, self.a_high = sig.butter(2, 4000 / nyquist, btype='high', output='ba')  # type: ignore
        
        self.zi_state = None
        self.n_channels = 1

    def process(self, audio_chunk: np.ndarray, bass_db: float, low_db: float, mid_db: float, high_db: float) -> np.ndarray:
        if audio_chunk is None or len(audio_chunk) == 0:
            return audio_chunk
            
        n_ch = audio_chunk.shape[1] if audio_chunk.ndim > 1 else 1
        
        # Initialize or resize the state tracker
        if self.zi_state is None or self.n_channels != n_ch:
            self.n_channels = n_ch
            zi_bass = sig.lfilter_zi(self.b_bass, self.a_bass)
            zi_low = sig.lfilter_zi(self.b_low, self.a_low)
            zi_mid = sig.lfilter_zi(self.b_mid, self.a_mid)
            zi_high = sig.lfilter_zi(self.b_high, self.a_high)
            
            self.zi_state = {
                'bass': np.tile(zi_bass, (n_ch, 1)).T if n_ch > 1 else zi_bass,
                'low': np.tile(zi_low, (n_ch, 1)).T if n_ch > 1 else zi_low,
                'mid': np.tile(zi_mid, (n_ch, 1)).T if n_ch > 1 else zi_mid,
                'high': np.tile(zi_high, (n_ch, 1)).T if n_ch > 1 else zi_high
            }

        proc_flat = audio_chunk.flatten() if audio_chunk.ndim == 1 else audio_chunk
        zi = self.zi_state
        
        # Apply filters
        bass_sig, zi['bass'] = sig.lfilter(self.b_bass, self.a_bass, proc_flat, axis=0, zi=zi['bass'])
        low_sig, zi['low'] = sig.lfilter(self.b_low, self.a_low, proc_flat, axis=0, zi=zi['low'])
        mid_sig, zi['mid'] = sig.lfilter(self.b_mid, self.a_mid, proc_flat, axis=0, zi=zi['mid'])
        high_sig, zi['high'] = sig.lfilter(self.b_high, self.a_high, proc_flat, axis=0, zi=zi['high'])
        self.zi_state = zi
        
        # Apply decibel gain mapping
        bass_gain = 10.0 ** (bass_db / 20.0)
        low_gain = 10.0 ** (low_db / 20.0)
        mid_gain = 10.0 ** (mid_db / 20.0)
        high_gain = 10.0 ** (high_db / 20.0)
        
        processed = (bass_sig * bass_gain) + (low_sig * low_gain) + (mid_sig * mid_gain) + (high_sig * high_gain)
        
        if audio_chunk.ndim == 1:
            processed = processed.flatten()
            
        return processed

class VolumeFader:
    """
    Stateful volume fader that enforces a rigid DAC warmup period (pure silence)
    before calculating continuous, click-free fade curves across live chunks.
    """
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.current_sample = 0
        self.total_samples = 0
        self.fade_type = 'in'
        self.is_active = False
        self.warmup_samples = 0

    def trigger_fade(self, duration_sec: float, fade_type: str = 'in'):
        self.total_samples = max(1, int(self.sample_rate * duration_sec))
        self.current_sample = 0
        self.fade_type = fade_type
        
        # ---> FIX: Force 150ms of absolute zero to let hardware relays click on
        self.warmup_samples = int(self.sample_rate * 0.15) if fade_type == 'in' else 0
        self.is_active = True

    def process(self, audio_chunk: np.ndarray) -> np.ndarray:
        if not self.is_active or len(audio_chunk) == 0:
            if self.fade_type == 'out' and self.current_sample >= self.total_samples:
                return audio_chunk * 0.0
            return audio_chunk

        chunk_len = len(audio_chunk)
        curve = np.ones(chunk_len, dtype=np.float32)

        # 1. Handle Hardware Warmup (Absolute Silence)
        idx = 0
        if self.warmup_samples > 0:
            pad = min(chunk_len, self.warmup_samples)
            curve[:pad] = 0.0
            self.warmup_samples -= pad
            idx = pad

        # 2. Handle Fade Curve
        if idx < chunk_len and self.current_sample < self.total_samples:
            rem = chunk_len - idx
            fade_rem = self.total_samples - self.current_sample
            apply_len = min(rem, fade_rem)

            start_r = self.current_sample / self.total_samples
            end_r = (self.current_sample + apply_len) / self.total_samples

            if self.fade_type == 'in':
                curve[idx:idx+apply_len] = np.linspace(start_r, end_r, apply_len, endpoint=False)
            else:
                curve[idx:idx+apply_len] = np.linspace(1.0 - start_r, 1.0 - end_r, apply_len, endpoint=False)
            
            self.current_sample += apply_len
            idx += apply_len

        # 3. Handle Post-Fade Out Silence
        if idx < chunk_len and self.fade_type == 'out':
            curve[idx:] = 0.0

        # Turn off processing if we are completely done
        if self.warmup_samples == 0 and self.current_sample >= self.total_samples:
            self.is_active = False

        if audio_chunk.ndim > 1:
            return audio_chunk * curve.reshape(-1, 1)
        else:
            return audio_chunk * curve