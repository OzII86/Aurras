import os
import wave
import librosa
import threading
import time
import numpy as np
import sounddevice as sd
import soundfile as sf

from typing import Optional, List, Any
from core.dsp import FourBandEQ, VolumeFader

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

class AudioEngine:
    """
    Backend engine responsible for real-time microphone recording, 
    live amplitude chunk tracking, pitch shifting, and frequency filtering (EQ).
    """
    
    def __init__(self, sample_rate: int = 44100):
        """
        Keypoint: Sets default sample rates and initializes recording state variables.
        """
        self.sample_rate = sample_rate
        self.is_recording = False
        self.recorded_audio: List[np.ndarray] = []
        self.stream: Optional[sd.InputStream] = None
        self._last_mic_chunk: List[float] = []
        self._live_peak_history = []
        
        # Default gain settings for mic input and speaker output to prevent feedback loops
        self.mic_input_gain = 0.8
        self.speaker_output_gain = 0.75
        self.current_console_params = {}

        # Initialize a delay buffer for echo effects
        self.max_delay_samples = sample_rate * 2  # 2 seconds max memory
        self.delay_buffer = np.zeros((self.max_delay_samples, 2), dtype=np.float32)
        self.delay_write_pos = 0

        # Initialize console parameters for live peak tracking and effect application
        self.current_console_params = {}
        self.stage_peaks = {"mic": 0.0, "gain": 0.0, "eq": 0.0, "delay": 0.0, "speaker": 0.0}

        # DSP Racks
        self.channel_eqs = {}
        self.mic_fader = VolumeFader(self.sample_rate)
        

    def get_live_peak_history(self) -> List[float]:
        """Returns the full accumulated peak history of the current recording session."""
        return self._live_peak_history

    def get_recent_mic_peak(self) -> List[float]:
        """Returns the latest active microphone amplitude buffer for live visual feedback."""
        return self._last_mic_chunk

    def play_timeline_mix(self, file_paths: list[str]):
        """
        Keypoint: Mixes and plays back multiple active timeline audio tracks simultaneously.
        """
        pass
    
    def start_recording(self, mute_output: bool = False, target_track_idx: int = 0):
        """
        Initializes a duplex audio stream for simultaneous microphone 
        recording and optional live speaker monitoring passthrough.
        """
        self.recorded_audio = []
        self._live_peak_history = []
        self.is_recording = True
        self.mute_output = mute_output
        self.active_record_track_idx = target_track_idx
        self._warmup_chunks = 5 # Number of initial chunks to ignore for hardware relay warmup

        # Pulls dynamic fade time from the UI slider and trigger the DSP
        fade_time = 0.15
        if self.current_console_params:
            fade_time = float(self.current_console_params.get("mic_fade", 0.5))
            
        self.mic_fader.trigger_fade(fade_time, fade_type='in')

        v8s_device_idx = None
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if "V8S" in dev.get('name', '') and dev.get('max_input_channels', 0) > 0:
                    v8s_device_idx = idx
                    break
        except Exception as e:
            print(f"Device query warning: {e}")

        def callback(indata: Optional[np.ndarray], outdata: np.ndarray, frames: int, time_info: Any, status: Any):
            if status:
                print(f"AudioEngine Stream Status: {status}")
            
            if indata is None:
                outdata.fill(0)
                self.stage_peaks["mic"] = 0.0
                self.stage_peaks["speaker"] = 0.0
                return
            
            # Throw away the hardware's initialization garbage
            if getattr(self, '_warmup_chunks', 0) > 0:
                self._warmup_chunks -= 1
                outdata.fill(0)  # Keep speakers dead silent
                return           # Abort the rest of the loop so nothing gets recorded

            self.stage_peaks["mic"] = float(np.max(np.abs(indata)))

            # 1. HARDWARE INPUT (Mic Preamp Volume)
            if self.current_console_params:
                mic_gain = float(self.current_console_params.get("mic_vol", 80)) / 100.0
            else:
                mic_gain = 0.8
                
            raw_mic_signal: np.ndarray = indata * mic_gain

            # ---> ROUTE THROUGH STANDALONE FADER DSP (Kills all clicks)
            raw_mic_signal = self.mic_fader.process(raw_mic_signal)

            # --- ROUTE TO THE ARMED CHANNEL STRIP ---
            channels = self.current_console_params.get("channels", []) if self.current_console_params else []
            ch_params = channels[self.active_record_track_idx] if self.active_record_track_idx < len(channels) else {}

            # 2. PRE-FADER INSERTS (Gain, EQ, Echo)
            if hasattr(self, 'apply_channel_inserts'):
                insert_signal = self.apply_channel_inserts(raw_mic_signal, ch_params, is_live=True)
            else:
                insert_signal = raw_mic_signal.copy()

            # 3. RECORDING BRANCH (Stores the raw mic signal into a buffer for later export)
            if self.is_recording:
                mono_data = insert_signal.mean(axis=1, keepdims=True) if insert_signal.ndim == 2 and insert_signal.shape[1] > 1 else insert_signal.copy()
                if mono_data.ndim == 1:
                    mono_data = mono_data.reshape(-1, 1)
                    
                self.recorded_audio.append(mono_data)
                try:
                    frame_peak = float(np.max(np.abs(mono_data)))
                    self._live_peak_history.append(frame_peak)
                    
                    chunk_vals = np.abs(mono_data[::max(1, len(mono_data) // 10)]).flatten()
                    self._last_mic_chunk = chunk_vals.tolist()
                except Exception:
                    pass

            # 4. POST-FADER MIX (Pan, Fader, and correct Peak Meter assignment)
            if hasattr(self, 'apply_channel_fader'):
                monitor_signal = self.apply_channel_fader(insert_signal, ch_params, is_live=True, track_idx=self.active_record_track_idx)
            else:
                monitor_signal = insert_signal.copy()

            # 5. HARDWARE OUTPUT (Speaker Master Volume)
            if not getattr(self, 'mute_output', False) and mic_gain > 0.0:
                if self.current_console_params:
                    speaker_gain = float(self.current_console_params.get("speaker_vol", 75)) / 100.0
                else:
                    speaker_gain = 0.75
                    
                passthrough: np.ndarray = monitor_signal * speaker_gain
                self.stage_peaks["speaker"] = float(np.max(np.abs(passthrough)))
                
                if passthrough.ndim == 2 and passthrough.shape[1] == 2:
                    outdata[:] = passthrough
                else:
                    tiled: np.ndarray = np.tile(passthrough, (1, 2)) if (passthrough.ndim == 1 or passthrough.shape[1] == 1) else passthrough
                    outdata[:] = tiled
            else:
                outdata.fill(0)
                self.stage_peaks["speaker"] = 0.0

        def stream_worker():
            try:
                kwargs = {
                    "samplerate": self.sample_rate,
                    "channels": 2,
                    "callback": callback
                }
                if v8s_device_idx is not None:
                    kwargs["device"] = v8s_device_idx

                with sd.Stream(**kwargs):
                    while self.is_recording:
                        sd.sleep(100)
            except Exception as e:
                print(f"AudioEngine Stream Error: {e}")
                self.is_recording = False

        self._record_thread = threading.Thread(target=stream_worker, daemon=True)
        self._record_thread.start()

    def set_mute_output(self, mute: bool):
        """Updates internal mute monitoring state."""
        self.mute_output = mute
        print(f"AudioEngine: Monitoring mute set to -> {mute}")

    def stop_recording(self, output_path: str) -> Optional[str]:
        """Terminates the active recording session and flushes buffered audio to disk."""
        if not self.is_recording:
            return None

        self.is_recording = False
        self._last_mic_chunk = []
        self._live_peak_history = []

        # Give the worker thread a brief moment to finish up
        time.sleep(0.1)

        if self.recorded_audio:
            try:
                audio_data = np.concatenate(self.recorded_audio, axis=0)
                
                # Apply a 15ms fade-out to the tail to prevent cutoff clicks
                fade_out_samples = int(self.sample_rate * 0.015)
                if len(audio_data) > fade_out_samples:
                    fade_curve = np.linspace(1.0, 0.0, fade_out_samples, dtype=np.float32)
                    if audio_data.ndim > 1:
                        audio_data[-fade_out_samples:] *= fade_curve.reshape(-1, 1)
                    else:
                        audio_data[-fade_out_samples:] *= fade_curve

                if audio_data.dtype != np.int16:
                    audio_data = np.clip(audio_data * 32767.0, -32767, 32767).astype(np.int16)
                    
                sf.write(output_path, audio_data, self.sample_rate)
                print(f"Recording successfully saved to: {output_path}")
                return output_path
            except Exception as e:
                print(f"Error saving recording: {e}")
        return None

    def play_audio(self, file_path: str):
        """
        Keypoint: Loads an audio file and plays it back through the default system output device.
        """
        if not os.path.exists(file_path):
            print(f"Error: Audio file not found for playback: {file_path}")
            return
            
        data, sr = sf.read(file_path)
        sd.play(data, sr)

    def stop_playback(self):
        """Immediately halts active audio playback streams."""
        self.is_playing = False
        if hasattr(self, 'playback_stream') and self.playback_stream:
            try:
                self.playback_stream.stop()
                self.playback_stream.close()
            except Exception:
                pass
            self.playback_stream = None
        sd.stop()

    def start_live_playback(self, tracks, zoom_scale=1.0, on_progress=None, on_stop=None):
        """Streams dry timeline audio into live DSP chunks for real-time manipulation."""
        self.stop_playback()
        self.is_playing = True
        self.playback_position = 0
        self.playback_buffers = []
        
        # Reset DSP states so old audio doesn't bleed into the new playback
        self.channel_eqs.clear()
        if hasattr(self, 'delay_buffer'):
            self.delay_buffer.fill(0)
        
        max_len = 0
        
        # 1. Pre-Load DRY audio into RAM
        for i, track in enumerate(tracks):
            if getattr(track, 'muted', False):
                continue
                
            track_idx = getattr(track, 'track_id', i)
            track_audio = np.zeros(0, dtype=np.float32)
            
            for clip in track.clips:
                path = clip.get("path")
                if not path or not os.path.exists(path):
                    continue
                    
                audio_data = None
                try:
                    ext = os.path.splitext(path)[1].lower()
                    if HAS_SOUNDFILE and ext in ['.mp3', '.flac', '.ogg', '.m4a', '.wav']:
                        data, file_sr = sf.read(path, dtype='float32')
                        if data.ndim > 1: data = data.mean(axis=1)
                        if file_sr != self.sample_rate:
                            new_len = int(len(data) * (self.sample_rate / file_sr))
                            audio_data = np.interp(np.linspace(0, len(data) - 1, new_len), np.arange(len(data)), data).astype(np.float32)
                        else:
                            audio_data = data
                    else:
                        with wave.open(path, 'rb') as wf:
                            n_channels = wf.getnchannels()
                            n_frames = wf.getnframes()
                            data = np.frombuffer(wf.readframes(n_frames), dtype=np.int16).astype(np.float32)
                            if n_channels > 1: data = data.reshape(-1, n_channels).mean(axis=1)
                            audio_data = data / 32767.0
                            
                    if audio_data is None or len(audio_data) == 0:
                        continue

                    start_x = clip.get("start_x", 50)
                    start_sec = max(0.0, (start_x - 50) / (10.0 * zoom_scale))
                    start_sample = int(start_sec * self.sample_rate)

                    req_len = start_sample + len(audio_data)
                    if req_len > len(track_audio):
                        track_audio = np.pad(track_audio, (0, req_len - len(track_audio)))
                        
                    track_audio[start_sample:req_len] += audio_data
                    
                except Exception as e:
                    print(f"Error loading clip {path}: {e}")
                    
            if len(track_audio) > max_len:
                max_len = len(track_audio)
                
            self.playback_buffers.append({"track_idx": track_idx, "data": track_audio})
            
        self.max_playback_length = max_len
        
        if self.max_playback_length == 0:
            self.is_playing = False
            if on_stop: on_stop()
            return
            
        # 2. Open Live Output Stream Callback
        def callback(outdata, frames, time_info, status):
            if status: print(f"Playback Status: {status}")
            if not getattr(self, 'is_playing', False):
                raise sd.CallbackStop()

            chunk_size = frames
            
            if self.playback_position >= self.max_playback_length:
                outdata.fill(0)
                if on_stop: on_stop()
                raise sd.CallbackStop()

            master_chunk = np.zeros((chunk_size, 2), dtype=np.float32)
            channels = self.current_console_params.get("channels", [])

            for tb in self.playback_buffers:
                data = tb["data"]
                rem = len(data) - self.playback_position
                if rem <= 0:
                    continue
                    
                slice_len = min(chunk_size, rem)
                raw_chunk = data[self.playback_position:self.playback_position + slice_len].copy()
                
                if len(raw_chunk) < chunk_size:
                    padded = np.zeros(chunk_size, dtype=np.float32)
                    padded[:len(raw_chunk)] = raw_chunk
                    raw_chunk = padded

                # APPLY LIVE DSP Math
                ch_params = channels[tb["track_idx"]] if tb["track_idx"] < len(channels) else {}
                processed = self.apply_channel_inserts(raw_chunk, ch_params, is_live=True)
                processed = self.apply_channel_fader(processed, ch_params, is_live=True, track_idx=tb["track_idx"])

                if processed.ndim == 1:
                    processed = np.column_stack((processed, processed))
                elif processed.shape[1] == 1:
                    processed = np.tile(processed, (1, 2))

                master_chunk += processed

            speaker_vol = self.current_console_params.get("speaker_vol", 75.0) / 100.0
            master_chunk *= speaker_vol
            
            outdata[:] = master_chunk
            self.playback_position += chunk_size
            
            if on_progress:
                on_progress(self.playback_position / self.sample_rate)
                
        try:
            self.playback_stream = sd.OutputStream(
                samplerate=self.sample_rate, 
                channels=2, 
                callback=callback,
                blocksize=2048  # Keeps DSP latency low for live knob sweeps
            )
            self.playback_stream.start()
        except Exception as e:
            print(f"Failed to start live playback stream: {e}")
            self.is_playing = False

    def trim_audio(self, input_path: str, output_path: str, start_sec: float, end_sec: float) -> str:
        """
        Keypoint: Clips/trims an audio file between a specified start and end timestamp (in seconds).
        """
        y, sr = librosa.load(input_path, sr=self.sample_rate)
        int_sr = int(sr)
        
        start_sample = int(start_sec * int_sr)
        end_sample = int(end_sec * int_sr)
        
        start_sample = max(0, start_sample)
        end_sample = min(len(y), end_sample)
        
        y_trimmed = y[start_sample:end_sample]
        
        sf.write(output_path, y_trimmed, int_sr)
        print(f"Trimmed audio saved to: {output_path}")
        return output_path

    def mix_and_export_timeline(self, tracks, output_path="assets/temp/mix/master_mix.wav", sample_rate=44100, zoom_scale=1.0, console_params=None):
        """
        Sums and mixes all active tracks, routing each through its respective 
        DAW channel strip (EQ, Pan, Fader) and exporting a stereo master mix.
        """
        if console_params is None:
            console_params = {}

        if not os.path.isabs(output_path):
            output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        track_buffers = []
        max_length_samples = sample_rate * 2
        
        channels = console_params.get("channels", [])

        for i, track in enumerate(tracks):
            if getattr(track, 'muted', False):
                continue
            
            # Map the timeline track to its corresponding channel strip on the mixer
            track_idx = getattr(track, 'track_id', i)
            ch_params = channels[track_idx] if track_idx < len(channels) else {}
            
            for clip in track.clips:
                path = clip.get("path")
                if not path or not os.path.exists(path):
                    continue
                
                audio_data = None
                try:
                    ext = os.path.splitext(path)[1].lower()
                    
                    if HAS_SOUNDFILE and ext in ['.mp3', '.flac', '.ogg', '.m4a', '.wav']:
                        data, file_sr = sf.read(path, dtype='float32')
                        if data.ndim > 1:
                            audio_data = data.mean(axis=1)
                        else:
                            audio_data = data
                        
                        if file_sr != sample_rate:
                            new_len = int(len(audio_data) * (sample_rate / file_sr))
                            audio_data = np.interp(
                                np.linspace(0, len(audio_data) - 1, new_len),
                                np.arange(len(audio_data)),
                                audio_data
                            ).astype(np.float32)
                    else:
                        with wave.open(path, 'rb') as wf:
                            n_channels = wf.getnchannels()
                            n_frames = wf.getnframes()
                            audio_bytes = wf.readframes(n_frames)
                            audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                            if n_channels > 1:
                                audio_data = audio_data.reshape(-1, n_channels).mean(axis=1)
                            audio_data /= 32767.0

                    if audio_data is None or len(audio_data) == 0:
                        continue

                    start_x = clip.get("start_x", 50)
                    pixels_per_sec = 10.0 * zoom_scale
                    start_sec = max(0.0, (start_x - 50) / pixels_per_sec)
                    start_sample = int(start_sec * sample_rate)

                    total_samples_needed = start_sample + len(audio_data)
                    if total_samples_needed > max_length_samples:
                        max_length_samples = total_samples_needed

                    padded_audio = np.zeros(total_samples_needed, dtype=np.float32)
                    padded_audio[start_sample:start_sample + len(audio_data)] = audio_data
                    
                    # ---> APPLY INDIVIDUAL CHANNEL STRIP EFFECTS HERE <---
                    if hasattr(self, 'apply_channel_inserts'):
                        padded_audio = self.apply_channel_inserts(padded_audio, ch_params, is_live=False)
                    if hasattr(self, 'apply_channel_fader'):
                        padded_audio = self.apply_channel_fader(padded_audio, ch_params, is_live=False)

                    # Ensure the processed track is Stereo (2 columns) so Pan settings survive
                    if padded_audio.ndim == 1:
                        padded_audio = np.column_stack((padded_audio, padded_audio))
                    elif len(padded_audio.shape) > 1 and padded_audio.shape[-1] == 1:
                        padded_audio = np.column_stack((padded_audio, padded_audio))

                    track_buffers.append(padded_audio)
                    
                except Exception as e:
                    print(f"Error processing clip {path}: {e}")

        if not track_buffers:
            print("Mixing Warning: No valid audio clips found to mix. Export aborted.")
            return None

        # Create a Stereo Master Mix array
        master_mix = np.zeros((max_length_samples, 2), dtype=np.float32)
        
        # Sum all the processed stereo tracks together
        for buf in track_buffers:
            master_mix[:len(buf)] += buf

        # Apply Master Speaker Volume (Hardware I/O)
        speaker_vol = console_params.get("speaker_vol", 75.0) / 100.0
        master_mix *= speaker_vol

        # Prevent clipping
        peak = np.max(np.abs(master_mix))
        if peak > 1.0:
            master_mix = master_mix / peak

        master_mix_int16 = (master_mix * 32767.0).clip(-32767, 32767).astype(np.int16)

        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(2)  # ---> FIX: Export as True Stereo
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(master_mix_int16.tobytes())

        print(f"Stereo master mix successfully exported to -> {output_path}")
        return output_path
    
    def clean_temp_directory(self):
        """Purges all temporary audio artifacts from the assets/temp/ subdirectories."""
        temp_root = os.path.join(os.getcwd(), "assets", "temp")
        if os.path.exists(temp_root):
            for root, dirs, files in os.walk(temp_root, topdown=False):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except Exception as e:
                        print(f"Warning: Could not remove temp file {file}: {e}")
            print("Temp directory cleaned successfully.")
    
    def shift_pitch(self, input_path: str, output_path: str, n_steps: float) -> str:
        """
        Keypoint: Loads audio data and applies a phase vocoder to shift pitch without altering duration.
        """
        y, sr = librosa.load(input_path, sr=self.sample_rate)
        int_sr = int(sr)
        
        y_shifted = librosa.effects.pitch_shift(y, sr=int_sr, n_steps=n_steps)
        
        sf.write(output_path, y_shifted, int_sr)
        print(f"Pitch-shifted audio saved to: {output_path}")
        return output_path

    def apply_channel_inserts(self, audio_data: np.ndarray, channel_params: dict, is_live: bool = False) -> np.ndarray:
        """Applies PRE-FADER effects (Gain, EQ, Echo) to be printed to the recording."""
        if audio_data is None or len(audio_data) == 0:
            return np.array([], dtype=np.float32) if audio_data is None else audio_data

        processed = audio_data.copy()

        # 1. Preamp Gain (Trim)
        gain_db = float(channel_params.get("gain", 0.0))
        processed *= (10.0 ** (gain_db / 20.0))

        # 2. 4-Band Parametric EQ (Routed to Standalone DSP)
        ch_name = channel_params.get("name", "ch_1")
        if ch_name not in self.channel_eqs:
            self.channel_eqs[ch_name] = FourBandEQ(self.sample_rate)
            
        low_db = float(channel_params.get("eq_low", 0.0))
        mid_db = float(channel_params.get("eq_mid", 0.0))
        high_db = float(channel_params.get("eq_high", 0.0))
        bass_db = float(channel_params.get("eq_bass", 0.0))
        
        processed = self.channel_eqs[ch_name].process(processed, bass_db, low_db, mid_db, high_db)

        # 3. Echo FX Send (Mono-safe)
        echo_mix = float(channel_params.get("fx_echo", 0.0)) / 100.0
        if echo_mix > 0.0 and is_live and hasattr(self, 'delay_buffer'):
            delay_samples = max(1, int(self.sample_rate * (250.0 / 1000.0))) 
            chunk_len = len(processed)
            
            read_start = (self.delay_write_pos - delay_samples) % self.max_delay_samples
            read_end = read_start + chunk_len
            
            if read_end <= self.max_delay_samples:
                delayed_sig = self.delay_buffer[read_start:read_end]
            else:
                delayed_sig = np.concatenate((self.delay_buffer[read_start:], self.delay_buffer[:read_end - self.max_delay_samples]), axis=0)

            # Match shapes so we can mix them
            if delayed_sig.shape != processed.shape:
                if processed.ndim == 1:
                    delayed_sig = delayed_sig[:chunk_len, 0]
                else:
                    delayed_sig = delayed_sig[:chunk_len, :processed.shape[1]]

            write_end = self.delay_write_pos + chunk_len
            write_data = processed + (delayed_sig * 0.5)
            
            if write_data.ndim == 1:
                write_data_stereo = np.column_stack((write_data, write_data))
            elif write_data.shape[1] == 1:
                write_data_stereo = np.tile(write_data, (1, 2))
            else:
                write_data_stereo = write_data
            
            if write_end <= self.max_delay_samples:
                self.delay_buffer[self.delay_write_pos:write_end] = write_data_stereo
            else:
                split_idx = self.max_delay_samples - self.delay_write_pos
                self.delay_buffer[self.delay_write_pos:] = write_data_stereo[:split_idx]
                self.delay_buffer[:write_end - self.max_delay_samples] = write_data_stereo[split_idx:]

            self.delay_write_pos = write_end % self.max_delay_samples
            processed = processed + (delayed_sig * echo_mix)

        return processed

    def apply_channel_fader(self, audio_data: np.ndarray, channel_params: dict, is_live: bool = False, track_idx: int = 0) -> np.ndarray:
        """Applies POST-FADER mix controls (Mute, Pan, Volume) for monitoring and playback."""
        if audio_data is None or len(audio_data) == 0:
            return np.array([], dtype=np.float32) if audio_data is None else audio_data

        processed = audio_data.copy()

        # 1. Hard Mute (Kills output instantly without affecting recording)
        if channel_params.get("mute", False):
            processed.fill(0.0)
            if is_live: self.stage_peaks[f"channel_{track_idx}"] = 0.0
            return processed

        # 2. Pan (L/R Stereo Placement)
        pan_val = float(channel_params.get("pan", 0.0)) / 100.0 
        left_mult = min(1.0, 1.0 - pan_val)
        right_mult = min(1.0, 1.0 + pan_val)
        
        if processed.ndim == 1 or processed.shape[1] == 1:
            processed = np.column_stack((processed.flatten() * left_mult, processed.flatten() * right_mult))
        else:
            processed[:, 0] *= left_mult
            processed[:, 1] *= right_mult

        # 3. Main Channel Fader
        fader_db = float(channel_params.get("fader", 0.0))
        if fader_db <= -59.0:
            processed.fill(0.0)
        else:
            processed *= (10.0 ** (fader_db / 20.0))

        # Peak extraction for the UI meter mapped to the correct track
        if is_live: 
            self.stage_peaks[f"channel_{track_idx}"] = float(np.max(np.abs(processed)))

        return processed

    def update_live_stream_parameters(self, console_params: dict):
        """Applies real-time mic input scaling and speaker output gain to active streams."""
        self.current_console_params = console_params
        mic_vol = console_params.get("mic_vol", 80.0) / 100.0
        speaker_vol = console_params.get("speaker_vol", 75.0) / 100.0

        self.mic_input_gain = mic_vol if mic_vol > 0.0 else 0.0
        self.speaker_output_gain = speaker_vol

    def adjust_eq(self, input_path: str, output_path: str, bass_gain: float = 0.0, mid_gain: float = 0.0, treble_gain: float = 0.0) -> str:
        """
        Keypoint: Performs STFT to isolate frequency bins and apply decibel gain modifications.
        """
        y, sr = librosa.load(input_path, sr=self.sample_rate)
        int_sr = int(sr)
        
        stft = librosa.stft(y)
        frequencies = librosa.fft_frequencies(sr=int_sr)

        bass_mask = frequencies < 250
        mid_mask = (frequencies >= 250) & (frequencies < 4000)
        treble_mask = frequencies >= 4000

        stft[bass_mask, :] *= 10 ** (bass_gain / 20)
        stft[mid_mask, :] *= 10 ** (mid_gain / 20)
        stft[treble_mask, :] *= 10 ** (treble_gain / 20)

        y_eq = librosa.istft(stft)
        
        sf.write(output_path, y_eq, int_sr)
        print(f"EQ-adjusted audio saved to: {output_path}")
        return output_path

    def start_loop_recording(self, backing_track_path: str, output_path: str, bpm: float = 120.0):
        """
        Keypoint: Plays an existing backing track in a loop while simultaneously 
        recording a new mic stream, locked to the active BPM clock.
        """
        self.is_recording = True
        measure_duration = (60.0 / bpm) * 4.0
        print(f"Starting loop recording at {bpm} BPM (Measure length: {measure_duration:.2f}s)")

        self._loop_thread = threading.Thread(
            target=self._run_tempo_loop_worker, 
            args=(backing_track_path, output_path, measure_duration), 
            daemon=True
        )
        self._loop_thread.start()

    def _run_tempo_loop_worker(self, backing_track_path: str, output_path: str, interval: float):
        """
        Keypoint: Background worker managing synchronized loop playback and input recording.
        """
        fs = 44100
        recorded_frames = []

        def callback(indata, frames, time_info, status):
            if self.is_recording:
                self.recorded_audio.append(indata.copy())
                try:
                    # Capture immediate frame peak for live visualization
                    frame_peak = float(np.max(np.abs(indata)))
                    self._live_peak_history.append(frame_peak)
                except Exception:
                    pass

        try:
            with sd.InputStream(samplerate=fs, channels=1, callback=callback):
                while self.is_recording:
                    if backing_track_path and os.path.exists(backing_track_path):
                        self.play_audio(backing_track_path)
                    
                    start_wait = time.time()
                    while self.is_recording and (time.time() - start_wait) < interval:
                        time.sleep(0.05)
                        
        except Exception as e:
            print(f"Error during tempo loop recording: {e}")

        if recorded_frames:
            audio_data = np.concatenate(recorded_frames, axis=0)
            audio_data = (audio_data * 32767).astype(np.int16)
            
            with wave.open(output_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(fs)
                wf.writeframes(audio_data.tobytes())
            print(f"Loop recording successfully saved to -> {output_path}")

    def audio_callback(self, indata, outdata, frames, time_info, status):
        """Real-time audio stream callback ensuring feedback prevention via volume control."""
        if status:
            print(f"Audio Stream Status: {status}")

        # Apply speaker volume scaling to prevent runaway gain loops
        outdata[:] = indata * getattr(self, "speaker_output_gain", 0.75)
        
        # If mic input gain is zeroed out, mute the passthrough buffer
        if getattr(self, "mic_input_gain", 1.0) == 0.0:
            outdata.fill(0)

    def stop_loop_recording(self):
        """Halts the active tempo loop session."""
        self.is_recording = False
        self._last_mic_chunk = []
        print("Stopping tempo loop recording.")