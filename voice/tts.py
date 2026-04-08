"""
TTS para Cortana.

Backends (en orden de prioridad):
1. F5-TTS  — voice cloning con muestras de Cortana (speak_blocking / speak_async)
2. edge-tts — voz neural de Microsoft (fallback cuando F5-TTS no está listo)

Para usar el backend de clonación directamente:
    from voice.tts_clone import speak_clone, speak_clone_async
"""

import asyncio
import tempfile
import os
import threading
import numpy as np
import edge_tts
import sounddevice as sd
import librosa

VOICE = "es-ES-ElviraNeural"
RATE  = "-8%"
PITCH = "-4Hz"

# Activar clonación de voz. False = siempre usa edge-tts (más rápido, menos fiel)
USE_VOICE_CLONE = True


async def _synthesize(text: str, path: str):
    communicate = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(path)


def _clean(text: str) -> str:
    import re
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"#{1,6}\s", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"[-*]\s", "", text)
    text = re.sub(r"\n+", ". ", text)
    return text.strip()


def speak(text: str, blocking: bool = True):
    clean = _clean(text)
    if not clean:
        return

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = f.name

    try:
        asyncio.run(_synthesize(clean, tmp))
        audio, sr = librosa.load(tmp, sr=22050, mono=True)
        if blocking:
            sd.play(audio, sr)
            sd.wait()
        else:
            def _play():
                sd.play(audio, sr)
                sd.wait()
            threading.Thread(target=_play, daemon=True).start()
    except Exception as e:
        print(f"[TTS] {e}")
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def speak_blocking(text: str):
    """
    TTS síncrono. Usa F5-TTS (voz clonada) si USE_VOICE_CLONE=True,
    si no, edge-tts.
    """
    if USE_VOICE_CLONE:
        try:
            from voice.tts_clone import speak_clone
            speak_clone(text, blocking=True)
            return
        except Exception as e:
            print(f"[TTS] F5-TTS falló, usando edge-tts: {e}")
    speak(text, blocking=True)


def speak_async(text: str):
    """
    TTS asíncrono. Usa F5-TTS si USE_VOICE_CLONE=True, si no, edge-tts.
    """
    if USE_VOICE_CLONE:
        try:
            from voice.tts_clone import speak_clone_async
            speak_clone_async(text)
            return
        except Exception as e:
            print(f"[TTS] F5-TTS falló, usando edge-tts: {e}")
    speak(text, blocking=False)
