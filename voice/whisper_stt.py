"""
STT local con faster-whisper. Sin internet, sin API key.
"""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
_model = None


def _get_model(size: str = "base") -> WhisperModel:
    global _model
    if _model is None:
        print(f"[Whisper] Cargando modelo '{size}'... (primera vez tarda ~30s)")
        _model = WhisperModel(size, device="cpu", compute_type="int8")
        print("[Whisper] Modelo listo.")
    return _model


def transcribe_audio(audio_np: np.ndarray, language: str = "es") -> str | None:
    """
    Transcribe un array numpy (float32, mono, 16kHz) a texto.
    Retorna el texto o None si no detectó habla.
    """
    model = _get_model()

    # faster-whisper espera float32 normalizado
    if audio_np.dtype != np.float32:
        audio_np = audio_np.astype(np.float32) / 32768.0

    segments, info = model.transcribe(
        audio_np,
        language=language,
        beam_size=3,
        vad_filter=True,          # filtra segmentos sin habla
        vad_parameters={"min_silence_duration_ms": 500},
    )

    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    if not parts:
        return None
    return " ".join(parts)


def record_and_transcribe(duration: float = 6.0, language: str = "es") -> str | None:
    """Graba y transcribe en un paso."""
    print(f"[Whisper] Grabando {duration}s...")
    audio = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="int16", blocking=True).flatten()
    audio_f = audio.astype(np.float32) / 32768.0
    return transcribe_audio(audio_f, language)
