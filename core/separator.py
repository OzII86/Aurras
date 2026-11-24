import os
from typing import Optional
import torch
import torchaudio
from demucs.pretrained import get_model
from demucs.apply import apply_model

class AudioSeparator:
    """
    Backend engine responsible for splitting mixed audio files into individual stems 
    (vocals, drums, bass, other) using local Demucs machine learning models.
    """
    
    def __init__(self, model_name: str = "htdemucs"):
        """
        Keypoint: Initializes the Demucs stem-separation model locally, 
        automatically detecting available hardware acceleration (CUDA vs CPU).
        
        Controller: Sets the model to evaluation mode for inference.
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Initializing Aurras AudioSeparator on device: {self.device.upper()}")
        
        self.model = get_model(model_name)
        self.model.to(self.device)
        self.model.eval()

    def split_audio(self, input_path: str, output_dir: Optional[str] = None) -> dict:
        """
        Keypoint: Loads an input audio file, normalizes waveform tensors, 
        and passes them through the Demucs neural network for frequency isolation.
        
        Controller: Automatically defaults output storage to assets/audio/split/ 
        if no custom path is provided, saving individual WAV stems.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Audio file not found: {input_path}")

        # Default structured output directory if none provided
        if output_dir is None:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_dir = os.path.join(os.getcwd(), "assets", "audio", "split", base_name)

        os.makedirs(output_dir, exist_ok=True)
        
        # Load audio file using torchaudio
        wav, sample_rate = torchaudio.load(input_path)
        
        # Normalization steps required by Demucs tensor formatting
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        wav = wav.to(self.device)

        print(f"Processing separation for: {os.path.basename(input_path)}...")
        
        # Apply the separation model without tracking gradients
        with torch.no_grad():
            sources = apply_model(self.model, wav[None], device=self.device)[0]

        stem_paths = {}
        source_names = self.model.sources  # Typically ['drums', 'bass', 'other', 'vocals']
        
        for i, source_name in enumerate(source_names):
            stem_audio = sources[i].cpu()
            # Unnormalize audio back to original scale
            stem_audio = stem_audio * ref.std() + ref.mean()
            
            output_file = os.path.join(output_dir, f"{source_name}.wav")
            torchaudio.save(output_file, stem_audio, sample_rate)
            stem_paths[source_name] = output_file
            print(f"Saved stem -> {output_file}")

        return stem_paths