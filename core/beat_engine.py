import os
import threading
from typing import Optional, List, Dict, Tuple, Any
import numpy as np
import sounddevice as sd
import soundfile as sf
import librosa


class BeatEngine:
    """
    Standalone Solo Engine (HIVE-Ready Module):
    Polyphonic pad sampler, pitch-shifter, BPM master clock, metronome synthesizer,
    and sample-accurate quantized overdub loop recorder.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._lock = threading.Lock()

        # Polyphonic Sample Cache & Active Voices
        self.sample_cache: Dict[Tuple[str, float], np.ndarray] = {}
        self.active_voices: List[Dict[str, Any]] = []

        # Master Output Level
        self.master_volume: float = 0.85

        # BPM Clock, Timing & Loop Buffer State
        self.is_running: bool = False
        self.is_recording: bool = False
        self.metronome_enabled: bool = True
        self.bpm: float = 120.0
        self.bars: int = 2
        self.quantize: str = "1/16"

        self.playhead: int = 0
        self.total_samples: int = int((60.0 / self.bpm) * 4.0 * self.bars * self.sample_rate)
        self.loop_buffer: np.ndarray = np.zeros((self.total_samples, 2), dtype=np.float32)
        self.history: List[np.ndarray] = []

        self.stream: Optional[sd.OutputStream] = None

        # Pre-synthesized Metronome Clicks (Downbeat High, Beat Low)
        self._click_high = self._synthesize_click(1400.0, 0.035)
        self._click_low = self._synthesize_click(900.0, 0.030)

    def _synthesize_click(self, freq_hz: float, duration_sec: float) -> np.ndarray:
        """Generates a crisp sine-wave metronome click in RAM."""
        n_samples = int(self.sample_rate * duration_sec)
        t = np.arange(n_samples, dtype=np.float32) / self.sample_rate
        envelope = np.exp(-t * 80.0).astype(np.float32)
        mono = (np.sin(2.0 * np.pi * freq_hz * t) * envelope * 0.35).astype(np.float32)
        return np.column_stack((mono, mono))

    def load_sample(self, file_path: str, pitch_steps: float = 0.0) -> Optional[np.ndarray]:
        """
        Loads an instrument or drum sample into RAM as stereo float32,
        applying optional semitone pitch-shifting and caching for zero-latency triggers.
        """
        if not file_path or not os.path.exists(file_path):
            return None

        cache_key = (os.path.abspath(file_path), round(float(pitch_steps), 2))
        if cache_key in self.sample_cache:
            return self.sample_cache[cache_key]

        try:
            data, file_sr = sf.read(file_path, dtype="float32")
            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.shape[1] == 1:
                data = np.tile(data, (1, 2))
            elif data.shape[1] > 2:
                data = data[:, :2]

            if file_sr != self.sample_rate:
                new_len = int(len(data) * (self.sample_rate / file_sr))
                x_old = np.arange(len(data))
                x_new = np.linspace(0, len(data) - 1, new_len)
                left = np.interp(x_new, x_old, data[:, 0]).astype(np.float32)
                right = np.interp(x_new, x_old, data[:, 1]).astype(np.float32)
                data = np.column_stack((left, right))

            if abs(pitch_steps) >= 0.05:
                mono = data.mean(axis=1)
                shifted = librosa.effects.pitch_shift(mono, sr=self.sample_rate, n_steps=float(pitch_steps))
                data = np.column_stack((shifted.astype(np.float32), shifted.astype(np.float32)))

            self.sample_cache[cache_key] = data
            return data
        except Exception as e:
            print(f"[BeatEngine] Error loading sample '{file_path}': {e}")
            return None

    def configure_transport(self, bpm: float = 120.0, bars: int = 2, quantize: str = "1/16", metronome: bool = True):
        """Updates BPM, bar count, timing quantization grid, and metronome click state."""
        bpm = max(40.0, min(240.0, float(bpm)))
        bars = max(1, int(bars))
        new_total = max(1, int((60.0 / bpm) * 4.0 * bars * self.sample_rate))

        with self._lock:
            self.bpm = bpm
            self.bars = bars
            self.quantize = quantize
            self.metronome_enabled = bool(metronome)

            if new_total != self.total_samples:
                new_buf = np.zeros((new_total, 2), dtype=np.float32)
                copy_len = min(len(self.loop_buffer), new_total)
                new_buf[:copy_len] = self.loop_buffer[:copy_len]
                self.loop_buffer = new_buf
                self.total_samples = new_total
                self.playhead = self.playhead % self.total_samples
                self.history.clear()

    def _ensure_stream(self):
        """Starts the dedicated low-latency OutputStream if not already running."""
        if self.stream is not None and self.stream.active:
            return

        def callback(outdata: np.ndarray, frames: int, time_info: Any, status: Any):
            if status:
                print(f"[BeatEngine] Stream Status: {status}")

            mix = np.zeros((frames, 2), dtype=np.float32)

            with self._lock:
                # 1. Render active polyphonic pad voices
                active = []
                for voice in self.active_voices:
                    buf = voice["data"]
                    pos = voice["pos"]
                    vol = voice["vol"]
                    rem = len(buf) - pos
                    if rem > 0:
                        take = min(frames, rem)
                        mix[:take] += buf[pos:pos + take] * vol
                        voice["pos"] += take
                        if voice["pos"] < len(buf):
                            active.append(voice)
                self.active_voices = active

                # 2. Render repeating loop buffer & metronome clock
                if self.is_running and self.total_samples > 0:
                    start_pos = self.playhead
                    end_pos = start_pos + frames

                    if end_pos <= self.total_samples:
                        mix += self.loop_buffer[start_pos:end_pos]
                    else:
                        first_part = self.total_samples - start_pos
                        second_part = frames - first_part
                        mix[:first_part] += self.loop_buffer[start_pos:]
                        mix[first_part:] += self.loop_buffer[:second_part]

                    if self.metronome_enabled:
                        samples_per_beat = max(1, int((60.0 / self.bpm) * self.sample_rate))
                        total_beats = max(1, self.bars * 4)

                        for beat_idx in range(total_beats):
                            beat_sample = beat_idx * samples_per_beat
                            click = self._click_high if (beat_idx % 4 == 0) else self._click_low
                            c_len = len(click)

                            rel_pos = (start_pos - beat_sample) % self.total_samples
                            if rel_pos < c_len:
                                take = min(frames, c_len - rel_pos)
                                mix[:take] += click[rel_pos:rel_pos + take]
                            else:
                                offset = (beat_sample - start_pos) % self.total_samples
                                if offset < frames:
                                    take = min(frames - offset, c_len)
                                    mix[offset:offset + take] += click[:take]

                    self.playhead = end_pos % self.total_samples

            mix *= self.master_volume
            np.clip(mix, -1.0, 1.0, out=mix)
            outdata[:] = mix

        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=2,
                callback=callback,
                blocksize=512
            )
            self.stream.start()
        except Exception as e:
            print(f"[BeatEngine] Stream initialization error: {e}")

    def trigger_pad(
        self,
        slot_idx: int,
        file_path: str,
        pitch_steps: float = 0.0,
        volume: float = 1.0,
        choke: bool = False
    ) -> bool:
        """
        Plays a pad sample immediately and, if Live Overdub Recording is armed,
        quantizes the hit to the timing grid and writes it into the loop buffer.
        """
        sample_data = self.load_sample(file_path, pitch_steps)
        if sample_data is None or len(sample_data) == 0:
            return False

        self._ensure_stream()

        with self._lock:
            if choke:
                self.active_voices = [v for v in self.active_voices if v.get("slot_idx") != slot_idx]

            self.active_voices.append({
                "slot_idx": slot_idx,
                "data": sample_data,
                "pos": 0,
                "vol": float(volume)
            })

            if self.is_running and self.is_recording and self.total_samples > 0:
                self.history.append(self.loop_buffer.copy())
                if len(self.history) > 15:
                    self.history.pop(0)

                write_pos = self._quantize_position(self.playhead)
                scaled = sample_data * float(volume)
                s_len = len(scaled)

                idx = 0
                cur_pos = write_pos % self.total_samples
                while idx < s_len:
                    take = min(s_len - idx, self.total_samples - cur_pos)
                    self.loop_buffer[cur_pos:cur_pos + take] += scaled[idx:idx + take]
                    idx += take
                    cur_pos = (cur_pos + take) % self.total_samples

                np.clip(self.loop_buffer, -1.0, 1.0, out=self.loop_buffer)

        return True

    def _quantize_position(self, sample_pos: int) -> int:
        """Snaps a sample index to the nearest musical subdivision."""
        q_map = {"Off": 0.0, "1/4": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125}
        beat_fraction = q_map.get(self.quantize, 0.25)
        if beat_fraction <= 0.0:
            return sample_pos

        grid_samples = max(1, int((60.0 / self.bpm) * beat_fraction * self.sample_rate))
        snapped = int(round(sample_pos / float(grid_samples)) * grid_samples)
        return snapped % self.total_samples

    def start_loop(self, record_overdub: bool = False):
        self._ensure_stream()
        with self._lock:
            self.is_running = True
            self.is_recording = bool(record_overdub)

    def compile_text_sequence_to_loop(
        self,
        script_text: str,
        key_to_slot_map: Dict[str, Dict[str, Any]],
        clear_existing: bool = True,
        record_undo: bool = True
    ) -> int:
        """
        Parses a text song string into the loop buffer:
        - Characters grouped together (e.g. 'qez') trigger simultaneously on the current step.
        - A single space (' ') advances to the next quantized step.
        - Multiple spaces or '-' create silent step gaps (rests).
        Returns the total number of triggered notes.
        """
        if not script_text:
            return 0

        q_map = {"Off": 0.5, "1/4": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125}
        beat_fraction = q_map.get(self.quantize, 0.5)
        step_samples = max(1, int((60.0 / self.bpm) * beat_fraction * self.sample_rate))

        # Pre-load all referenced samples outside the thread lock
        loaded_audio: Dict[str, Tuple[np.ndarray, float]] = {}
        for k, slot_info in key_to_slot_map.items():
            path = slot_info.get("sample", "")
            if path and os.path.exists(path):
                buf = self.load_sample(path, 0.0)
                if buf is not None:
                    loaded_audio[k.lower()] = (buf, float(slot_info.get("volume", 1.0)))

        # Parse script into step clusters:
        # 'qez e  w' -> Step 0: 'qez', Step 1: 'e', Step 2: '' (gap), Step 3: 'w'
        steps: List[str] = []
        current_cluster = ""
        i = 0
        while i < len(script_text):
            ch = script_text[i]
            if ch in (" ", "\t", "\n"):
                if current_cluster:
                    steps.append(current_cluster)
                    current_cluster = ""
                    # Consume the single separator space; any extra spaces become silent gap steps
                    i += 1
                    while i < len(script_text) and script_text[i] == " ":
                        steps.append("")
                        i += 1
                    continue
                else:
                    steps.append("")
            elif ch in ("-", "_"):
                if current_cluster:
                    steps.append(current_cluster)
                    current_cluster = ""
                steps.append("")
            else:
                current_cluster += ch.lower()
            i += 1

        if current_cluster:
            steps.append(current_cluster)

        notes_rendered = 0
        with self._lock:
            if record_undo:
                self.history.append(self.loop_buffer.copy())
                if len(self.history) > 15:
                    self.history.pop(0)

            target_buf = (
                np.zeros_like(self.loop_buffer)
                if clear_existing
                else self.loop_buffer.copy()
            )

            for step_idx, cluster in enumerate(steps):
                if not cluster:
                    continue
                write_start = (step_idx * step_samples) % self.total_samples
                for char_key in cluster:
                    if char_key not in loaded_audio:
                        continue
                    sample_buf, vol = loaded_audio[char_key]
                    scaled = sample_buf * vol
                    s_len = len(scaled)

                    idx = 0
                    cur_pos = write_start
                    while idx < s_len:
                        take = min(s_len - idx, self.total_samples - cur_pos)
                        target_buf[cur_pos:cur_pos + take] += scaled[idx:idx + take]
                        idx += take
                        cur_pos = (cur_pos + take) % self.total_samples
                    notes_rendered += 1

            np.clip(target_buf, -1.0, 1.0, out=target_buf)
            self.loop_buffer[:] = target_buf

        return notes_rendered

    def set_recording(self, record_overdub: bool):
        with self._lock:
            self.is_recording = bool(record_overdub)
            if record_overdub and not self.is_running:
                self.is_running = True
        if record_overdub:
            self._ensure_stream()

    def stop_loop(self):
        with self._lock:
            self.is_running = False
            self.is_recording = False
            self.playhead = 0
            self.active_voices.clear()

    def undo_overdub(self) -> bool:
        with self._lock:
            if not self.history:
                return False
            self.loop_buffer = self.history.pop()
            return True

    def clear_loop(self):
        with self._lock:
            self.history.append(self.loop_buffer.copy())
            if len(self.history) > 15:
                self.history.pop(0)
            self.loop_buffer.fill(0.0)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            samples_per_beat = max(1, int((60.0 / self.bpm) * self.sample_rate))
            current_beat_total = int(self.playhead // samples_per_beat)
            bar_idx = (current_beat_total // 4) + 1
            beat_in_bar = (current_beat_total % 4) + 1
            progress = self.playhead / float(max(1, self.total_samples))
            has_audio = bool(np.max(np.abs(self.loop_buffer)) > 0.001)
            return {
                "is_running": self.is_running,
                "is_recording": self.is_recording,
                "bar": bar_idx,
                "beat": beat_in_bar,
                "progress": progress,
                "bpm": self.bpm,
                "bars": self.bars,
                "has_audio": has_audio
            }

    def export_loop(self, output_path: str) -> Optional[str]:
        with self._lock:
            loop_copy = self.loop_buffer.copy()

        if np.max(np.abs(loop_copy)) <= 0.0001:
            return None

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        sf.write(output_path, loop_copy, self.sample_rate, subtype="PCM_16")
        return output_path

    def render_and_save_tweaked_sample(
        self,
        source_path: str,
        pitch_steps: float = 0.0,
        bass_db: float = 0.0,
        treble_db: float = 0.0,
        target_duration: float = 0.0,
        output_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        Renders Pitch Shift, Bass EQ (<250Hz), Treble EQ (>3500Hz), and Time-Stretch Duration
        from the base sample and writes a new auto-named WAV file into Vault/Presets/Beats/.
        If all tweaks are 0.0, returns the original source_path untouched.
        """
        if not source_path or not os.path.exists(source_path):
            return None

        if (
            abs(pitch_steps) < 0.05
            and abs(bass_db) < 0.1
            and abs(treble_db) < 0.1
            and target_duration <= 0.05
        ):
            return source_path

        if output_dir is None:
            output_dir = os.path.join("Vault", "Presets", "Beats")
        os.makedirs(output_dir, exist_ok=True)

        # Strip any previous auto-generated suffix (_p..., _b..., _t..., _d...) to keep names clean
        raw_stem = os.path.splitext(os.path.basename(source_path))[0]
        for token in ("_p+", "_p-", "_b+", "_b-", "_t+", "_t-", "_d"):
            if token in raw_stem:
                raw_stem = raw_stem.split(token)[0]

        tags = []
        if abs(pitch_steps) >= 0.05:
            tags.append(f"p{pitch_steps:+.0f}")
        if abs(bass_db) >= 0.1:
            tags.append(f"b{bass_db:+.0f}dB")
        if abs(treble_db) >= 0.1:
            tags.append(f"t{treble_db:+.0f}dB")
        if target_duration > 0.05:
            tags.append(f"d{target_duration:.2f}s")

        new_filename = f"{raw_stem}_{'_'.join(tags)}.wav"
        rel_out_path = os.path.join(output_dir, new_filename).replace("\\", "/")

        # Load pitch-shifted audio (or unshifted if pitch_steps == 0)
        base_audio = self.load_sample(source_path, pitch_steps=pitch_steps)
        if base_audio is None or len(base_audio) == 0:
            return source_path

        processed = base_audio.copy()

        # Apply STFT Bass (<250Hz) and Treble (>3500Hz) EQ if non-zero
        if abs(bass_db) >= 0.1 or abs(treble_db) >= 0.1:
            freqs = librosa.fft_frequencies(sr=self.sample_rate)
            bass_mask = freqs < 250.0
            treble_mask = freqs > 3500.0
            bass_mult = float(10.0 ** (bass_db / 20.0))
            treble_mult = float(10.0 ** (treble_db / 20.0))

            channels = []
            for ch in range(processed.shape[1]):
                stft = librosa.stft(processed[:, ch])
                if abs(bass_db) >= 0.1:
                    stft[bass_mask, :] *= bass_mult
                if abs(treble_db) >= 0.1:
                    stft[treble_mask, :] *= treble_mult
                ch_out = librosa.istft(stft, length=len(processed))
                channels.append(ch_out.astype(np.float32))
            processed = np.column_stack(channels)

        # Apply Phase-Vocoder Time-Stretch if a custom Duration Timer (in seconds) is set
        if target_duration > 0.05:
            current_dur = len(processed) / float(self.sample_rate)
            target_samples = max(1, int(target_duration * self.sample_rate))
            if abs(current_dur - target_duration) >= 0.03 and current_dur > 0.01:
                # rate < 1.0 elongates/stretches the sound; rate > 1.0 speeds it up
                stretch_rate = max(0.15, min(6.0, current_dur / float(target_duration)))
                mono_sig = processed.mean(axis=1).astype(np.float32)
                stretched = librosa.effects.time_stretch(mono_sig, rate=stretch_rate)

                # Fit to exact target_samples with a clean 15ms tail fade-out
                if len(stretched) > target_samples:
                    stretched = stretched[:target_samples]
                elif len(stretched) < target_samples:
                    stretched = np.pad(stretched, (0, target_samples - len(stretched)))

                fade_len = min(len(stretched), int(self.sample_rate * 0.015))
                if fade_len > 1:
                    stretched[-fade_len:] *= np.linspace(1.0, 0.0, fade_len, dtype=np.float32)

                processed = np.column_stack((stretched.astype(np.float32), stretched.astype(np.float32)))

        # Normalize if EQ boost pushed peak over 0.98
        peak = float(np.max(np.abs(processed)))
        if peak > 0.98:
            processed = (processed / peak) * 0.95

        sf.write(rel_out_path, processed, self.sample_rate, subtype="PCM_16")
        # Cache the newly baked file at 0.0 additional pitch shift so playback is instant
        self.sample_cache[(os.path.abspath(rel_out_path), 0.0)] = processed
        print(f"[BeatEngine] Auto-generated tweaked preset audio -> {rel_out_path}")
        return rel_out_path