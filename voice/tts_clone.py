"""
cortana/voice/tts_clone.py

TTS con clonación de voz usando F5-TTS.
Usa los archivos de referencia en voice_samples/ para replicar
la voz de Cortana en cualquier texto de salida.

Fallback automático a edge-tts si F5-TTS falla o no está cargado.

F5-TTS: https://github.com/SWivid/F5-TTS
Compatible con Python 3.14 (a diferencia de Coqui TTS / XTTS-v2).
"""

import threading
import tempfile
import os
from pathlib import Path
import numpy as np
import sounddevice as sd

# ── Rutas de referencia ───────────────────────────────────────────────────────

_BASE = Path(__file__).parent.parent / "voice_samples"

# Pares (archivo_wav, texto_transcrito) para clonación
REFERENCE_SAMPLES = [
    (
        str(_BASE / "ref_1.wav"),
        "Buenos días, ya es de mañana. Dije buenos días, señor dormilón. "
        "Dormías tan profundamente que no estaba segura de querer despertarte. "
        "Tienes cosas importantes que hacer hoy.",
    ),
    (
        str(_BASE / "ref_2.wav"),
        "Arte más de 40 mil razones por las que sé que es eso lo es real. "
        "Lo sé por el efecto Rayleigh de la emisora es desproporcionado.",
    ),
]

# Referencia activa (índice en REFERENCE_SAMPLES)
_ACTIVE_REF = 0

# ── Carga del modelo ──────────────────────────────────────────────────────────

_model = None
_model_lock = threading.Lock()


def _patch_torchaudio():
    """
    torchaudio 2.9+ usa torchcodec (requiere DLLs de FFmpeg).
    Cuando torchcodec no está disponible, redirigimos torchaudio.load
    a soundfile para no necesitar FFmpeg instalado.
    """
    import torch
    import soundfile as sf
    import torchaudio

    def _sf_load(uri, frame_offset=0, num_frames=-1, normalize=True,
                 channels_first=True, format=None, buffer_size=4096, backend=None):
        data, sr = sf.read(str(uri), dtype="float32", always_2d=True)
        # soundfile → (T, C), torch necesita (C, T)
        tensor = torch.from_numpy(data.T)
        if frame_offset > 0:
            tensor = tensor[:, frame_offset:]
        if num_frames > 0:
            tensor = tensor[:, :num_frames]
        if normalize:
            peak = tensor.abs().max()
            if peak > 1.0:
                tensor = tensor / peak
        return tensor, sr

    # Probar si torchcodec funciona
    try:
        import torchcodec  # noqa: F401
    except Exception:
        torchaudio.load = _sf_load
        print("[F5-TTS] torchaudio parchado: usa soundfile (sin FFmpeg)")


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _patch_torchaudio()
                from f5_tts.api import F5TTS
                print("[F5-TTS] Cargando modelo F5TTS_v1_Base… (primera vez ~1GB)")
                _model = F5TTS(model="F5TTS_v1_Base", device="cpu")
                print("[F5-TTS] Modelo listo.")
    return _model


def preload():
    """Precarga el modelo en background para evitar retraso al primer uso."""
    threading.Thread(target=_get_model, daemon=True, name="f5tts-preload").start()


# ── Síntesis ──────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Elimina markdown y normaliza el texto para TTS."""
    import re
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*",     r"\1", text)
    text = re.sub(r"`(.*?)`",       r"\1", text)
    text = re.sub(r"#{1,6}\s",      "",    text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[-*]\s",        "",    text)
    text = re.sub(r"\n+",           ". ",  text)
    return text.strip()


def synthesize(text: str) -> tuple[np.ndarray, int] | None:
    """
    Genera audio en la voz de Cortana usando F5-TTS.
    Retorna (array_numpy_float32, sample_rate) o None si falla.
    """
    clean = _clean(text)
    if not clean:
        return None

    ref_file, ref_text = REFERENCE_SAMPLES[_ACTIVE_REF]

    if not Path(ref_file).exists():
        print(f"[F5-TTS] Archivo de referencia no encontrado: {ref_file}")
        return None

    try:
        model = _get_model()
        wav, sr, _ = model.infer(
            ref_file=ref_file,
            ref_text=ref_text,
            gen_text=clean,
            remove_silence=True,
            speed=1.0,
            seed=42,           # Seed fijo → voz consistente entre llamadas
        )
        return wav, sr
    except Exception as e:
        print(f"[F5-TTS] Error en síntesis: {e}")
        return None


def speak_clone(text: str, blocking: bool = True) -> bool:
    """
    Reproduce texto con la voz clonada de Cortana.
    Retorna True si usó F5-TTS, False si cayó en el fallback edge-tts.
    """
    result = synthesize(text)

    if result is not None:
        wav, sr = result
        # Normalizar a float32 [-1, 1]
        if wav.dtype != np.float32:
            wav = wav.astype(np.float32)
        peak = np.abs(wav).max()
        if peak > 0:
            wav = wav / peak * 0.9

        if blocking:
            sd.play(wav, sr)
            sd.wait()
        else:
            def _play():
                sd.play(wav, sr)
                sd.wait()
            threading.Thread(target=_play, daemon=True).start()
        return True

    # Fallback a edge-tts si F5-TTS falla
    print("[F5-TTS] Usando fallback edge-tts")
    from voice.tts import speak
    speak(text, blocking=blocking)
    return False


def speak_clone_async(text: str) -> None:
    """Síntesis Y reproducción en hilo separado (no bloquea nada)."""
    threading.Thread(
        target=lambda: speak_clone(text, blocking=True),
        daemon=True,
    ).start()


def set_reference(index: int) -> None:
    """Cambia la muestra de referencia activa (0 = ref_1, 1 = ref_2)."""
    global _ACTIVE_REF
    if 0 <= index < len(REFERENCE_SAMPLES):
        _ACTIVE_REF = index
        print(f"[F5-TTS] Referencia activa: ref_{index + 1}.wav")
    else:
        print(f"[F5-TTS] Índice inválido: {index}")
