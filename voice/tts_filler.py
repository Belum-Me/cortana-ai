"""
cortana/voice/tts_filler.py

Reproduce frases de transición pre-generadas con la voz de Cortana.
Si el .wav pre-generado existe, lo reproduce instantáneamente (<50ms).
Si no, sintetiza con edge-tts como fallback.

Flujo típico:
    python tools/prebuild_fillers.py   ← una sola vez
    from voice.tts_filler import play_filler  ← en tiempo real
"""

import random
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

_CACHE_DIR = Path(__file__).parent.parent / "voice_samples" / "fillers"

# Mismas frases que en prebuild_fillers.py y core/llm.py
_FILLERS = {
    "es": ["mmh", "dejame_ver", "un_momento", "claro", "a_ver", "entendido", "bien"],
    "en": ["hmm", "let_me_check", "sure", "one_sec", "got_it", "alright", "okay"],
}

# Texto plano para el fallback edge-tts (mismo orden que _FILLERS)
_FILLER_TEXT = {
    "es": ["Mmh.", "Déjame ver.", "Un momento.", "Claro.", "A ver.", "Entendido.", "Bien."],
    "en": ["Hmm.", "Let me check.", "Sure.", "One sec.", "Got it.", "Alright.", "Okay."],
}


def _cache_available(lang: str) -> bool:
    d = _CACHE_DIR / lang
    return d.exists() and any(d.glob("*.wav"))


def play_filler(lang: str = "es", blocking: bool = True) -> None:
    """
    Reproduce una frase de transición aleatoria en el idioma dado.
    Usa audio pre-generado con voz de Cortana si está disponible,
    si no, sintetiza con edge-tts en tiempo real.
    """
    lang = lang if lang in _FILLERS else "es"

    if _cache_available(lang):
        _play_cached(lang, blocking)
    else:
        _play_edge(lang, blocking)


def _play_cached(lang: str, blocking: bool) -> None:
    keys = _FILLERS[lang]
    key = random.choice(keys)
    path = _CACHE_DIR / lang / f"{key}.wav"

    if not path.exists():
        # Frase específica no generada, buscar cualquiera disponible
        candidates = list((_CACHE_DIR / lang).glob("*.wav"))
        if not candidates:
            _play_edge(lang, blocking)
            return
        path = random.choice(candidates)

    try:
        wav, sr = sf.read(str(path), dtype="float32")
        if wav.ndim == 2:
            wav = wav.mean(axis=1)
        _play_array(wav, sr, blocking)
    except Exception as e:
        print(f"[tts_filler] Error leyendo cache: {e}")
        _play_edge(lang, blocking)


def _play_edge(lang: str, blocking: bool) -> None:
    texts = _FILLER_TEXT[lang]
    text = random.choice(texts)
    try:
        from voice.tts import speak
        speak(text, blocking=blocking)
    except Exception as e:
        print(f"[tts_filler] Error edge-tts: {e}")


def _play_array(wav: np.ndarray, sr: int, blocking: bool) -> None:
    if blocking:
        sd.play(wav, sr)
        sd.wait()
    else:
        threading.Thread(target=lambda: (sd.play(wav, sr), sd.wait()),
                         daemon=True).start()
