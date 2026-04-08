"""
TTS para Cortana usando edge-tts + sounddevice (compatible Windows Python 3.14)
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
RATE = "-8%"
PITCH = "-4Hz"


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
    """TTS síncrono. Usado en el pipeline de streaming para encadenar chunks."""
    speak(text, blocking=True)


def speak_async(text: str):
    speak(text, blocking=False)
