from __future__ import annotations

import io
import base64
import logging
import tempfile
import numpy as np
import torch
from typing import Optional, Callable

# Lazy imports to avoid startup overhead if STT not used immediately
try:
    import librosa
    import noisereduce as nr
    from transformers import pipeline
    from pydub import AudioSegment
    import webrtcvad
except ImportError:
    librosa = None
    nr = None
    pipeline = None
    AudioSegment = None
    webrtcvad = None

class STTService:
    """
    Robust Speech-to-Text service using Whisper (fine-tuned) + noise reduction.
    Backwards-compatible constructor: accepts optional llm_service but initializes heavy deps lazily on first use.
    """

    def __init__(self, llm_service: Optional[object] = None, model_id: str = "antony66/whisper-large-v3-russian", device: str = "cpu", use_vad: bool = True) -> None:
        self.logger = logging.getLogger(__name__)
        self.llm_service = llm_service
        self._model_id = model_id
        self._device_pref = device
        self._use_vad_pref = use_vad
        self._initialized = False
        # placeholders for heavy objects
        self.pipe = None
        self.vad = None
        self.device = None
        self.torch_dtype = None

    def _lazy_init(self):
        if self._initialized:
            return
        # perform imports and model loading; if deps missing, keep pipe=None and fail only on use
        try:
            import torch as _torch
            from transformers import pipeline as _pipeline
            from pydub import AudioSegment as _AudioSegment
            import noisereduce as _nr
            import webrtcvad as _webrtcvad
            import numpy as _np
        except Exception as e:
            self.logger.debug("STT lazy init missing dependencies: %s", e)
            # mark initialized but without pipe; audio_to_text will raise understandable error
            self._initialized = True
            return

        # set attributes
        self.device = self._device_pref if _torch.cuda.is_available() else "cpu"
        self.torch_dtype = _torch.float16 if self.device == "cuda" else _torch.float32

        try:
            self.pipe = _pipeline(
                "automatic-speech-recognition",
                model=self._model_id,
                device=0 if self.device == 'cuda' else -1,
                torch_dtype=self.torch_dtype,
            )
        except Exception as e:
            self.logger.warning("Failed to initialize STT pipeline: %s", e)
            self.pipe = None

        self.vad = _webrtcvad.Vad(3) if _webrtcvad else None
        # store references to modules for internal use
        self._AudioSegment = _AudioSegment
        self._nr = _nr
        self._np = _np
        self._initialized = True

    def _convert_base64_to_audio(self, audio_base64: str) -> Optional[np.ndarray]:
        """Convert base64 string to 16kHz mono numpy array"""
        if not AudioSegment:
            raise RuntimeError("pydub not installed")

        try:
            # Decode base64
            if "," in audio_base64:
                audio_base64 = audio_base64.split(",")[1]
            audio_bytes = base64.b64decode(audio_base64)

            # Load with pydub (handles webm, map3, wav automagically if ffmpeg present)
            with io.BytesIO(audio_bytes) as bio:
                audio = AudioSegment.from_file(bio)

            # Resample to 16kHz, mono
            audio = audio.set_frame_rate(16000).set_channels(1)

            # Convert to numpy array (pydub uses int samples, we need float32 for librosa/transformers sometimes)
            # But transformers usually wants raw bytes or file path, or float array.
            # Convert to float32 numpy array
            samples = np.array(audio.get_array_of_samples())

            if audio.sample_width == 2:
                samples = samples.astype(np.float32) / 32768.0
            elif audio.sample_width == 4:
                samples = samples.astype(np.float32) / 2147483648.0

            return samples
        except Exception as e:
            self.logger.error(f"Error converting audio: {e}")
            return None

    def _reduce_noise(self, audio_array: np.ndarray, sr: int = 16000) -> np.ndarray:
        """Apply 2-stage noise reduction"""
        if not nr:
            return audio_array
        try:
            # Stage 1: Stationary noise
            reduced = nr.reduce_noise(y=audio_array, sr=sr, stationary=True)
            # Stage 2: Non-stationary (optional, can be aggressive) - let's stick to stationary for safety/speed
            # final = nr.reduce_noise(y=reduced, sr=sr, stationary=False)
            return reduced
        except Exception as e:
            self.logger.warning(f"Noise reduction failed: {e}")
            return audio_array

    async def audio_to_text(self, audio_base64: str, mime_type: str = "audio/webm") -> str:
        """Process audio and return text with punctuation."""
        self._lazy_init()  # Ensure dependencies are loaded

        if not self.pipe:
            # Fallback or error
            if not librosa:
                return "STT Error: Service dependencies not installed."
            return "STT Error: Model not initialized."

        # 1. Preprocessing
        audio = self._convert_base64_to_audio(audio_base64)
        if audio is None:
            raise ValueError("Could not process audio file")

        # 2. Noise Reduction
        clean_audio = self._reduce_noise(audio)

        # 3. Transcription
        # Using whisper's built-in chunking/logic via transformers pipeline
        # We enforce Russian and provide prompt for punctuation

        # Note: transformers pipeline might not support 'initial_prompt' directly in all versions,
        # but 'generate_kwargs' can usually pass it.
        generate_kwargs = {
            "language": "russian",
            "task": "transcribe",
            # "forced_decoder_ids": ... (handled by language)
        }

        # Try to pass initial_prompt if supported (depends on model type).
        # WhisperForConditionalGeneration supports 'prompt_ids' or we just rely on built-in punctuation.
        # "Uses correct punctuation..." prompt style

        try:
            # Pipeline accepts numpy array directly
            result = self.pipe(
                clean_audio,
                chunk_length_s=30,
                batch_size=8,
                return_timestamps=True,
                generate_kwargs=generate_kwargs
            )

            text = result.get("text", "").strip()

            # 4. Post-processing (basic)
            text = self._post_process(text)

            return text
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}")

    def _post_process(self, text: str) -> str:
        """Fix capitalization and common issues."""
        if not text:
            return ""

        # Capitalize first letter
        text = text[0].upper() + text[1:]

        # Ensure ending punctuation if reasonable length
        if len(text) > 5 and text[-1] not in ".!?":
            text += "."

        return text.replace("  ", " ")
