"""
STT local con faster-whisper. Sin internet, sin API key.
- Modelo 'tiny': para detección de wake word (rápido, ~200ms)
- Modelo 'base': para transcripción de comandos (preciso, ~800ms)
"""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000

_models = {}


def _get_model(size: str = "base") -> WhisperModel:
    if size not in _models:
        sizes = {"tiny": "75MB", "base": "150MB", "small": "500MB"}
        print(f"[Whisper] Cargando modelo '{size}'... (primera vez descarga ~{sizes.get(size, '?')})")
        _models[size] = WhisperModel(size, device="cpu", compute_type="int8")
        print(f"[Whisper] Modelo '{size}' listo.")
    return _models[size]


def preload_models():
    """Carga ambos modelos al inicio para evitar retrasos después."""
    _get_model("tiny")
    _get_model("base")


def transcribe_audio(audio_np: np.ndarray, language: str = "es",
                     model_size: str = "base") -> str | None:
    """Transcribe array numpy float32 mono 16kHz a texto."""
    model = _get_model(model_size)

    if audio_np.dtype != np.float32:
        audio_np = audio_np.astype(np.float32) / 32768.0

    segments, _ = model.transcribe(
        audio_np,
        language=language,
        beam_size=3,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
    )

    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    return " ".join(parts) if parts else None


def contains_wake_word(audio_np: np.ndarray, wake_words: list[str],
                       language: str = "es") -> tuple[bool, str]:
    """
    Usa el modelo 'tiny' para detectar rápido si el audio contiene
    alguna de las wake words. Retorna (detectado, texto).
    """
    text = transcribe_audio(audio_np, language=language, model_size="tiny")
    if not text:
        return False, ""
    text_lower = text.lower().strip()
    detected = any(w in text_lower for w in wake_words)
    return detected, text
