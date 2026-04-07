import asyncio
import edge_tts
import tempfile
import os
import threading

# Voz seleccionada: española, femenina, neural, firme y clara
# es-ES-ElviraNeural: timbre femenino preciso, autoridad natural, claridad impecable
VOICE = "es-ES-ElviraNeural"

# Configuracion de personalidad vocal de Cortana:
# Rate ligeramente reducido para pausas naturales y ritmo reflexivo
# Pitch levemente bajo para autoridad intelectual sin perder feminidad
RATE = "-8%"
PITCH = "-4Hz"
VOLUME = "+0%"


async def _synthesize(text: str, output_path: str):
    """Sintetiza texto a audio con la voz de Cortana."""
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=RATE,
        pitch=PITCH,
        volume=VOLUME,
    )
    await communicate.save(output_path)


def _clean_text_for_speech(text: str) -> str:
    """Limpia markdown y simbolos para una lectura natural."""
    import re
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)         # italic
    text = re.sub(r"`(.*?)`", r"\1", text)           # code inline
    text = re.sub(r"#{1,6}\s", "", text)             # headers
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links
    text = re.sub(r"[-*]\s", "", text)               # bullets
    text = re.sub(r"\n{2,}", ". ", text)             # parrafos
    text = re.sub(r"\n", " ", text)
    return text.strip()


def speak(text: str, blocking: bool = True):
    """Convierte texto a voz y lo reproduce."""
    try:
        from playsound import playsound
    except ImportError:
        print(f"[VOZ] {text}")
        return

    clean = _clean_text_for_speech(text)
    if not clean:
        return

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name

    try:
        asyncio.run(_synthesize(clean, tmp_path))

        if blocking:
            playsound(tmp_path)
        else:
            t = threading.Thread(target=playsound, args=(tmp_path,), daemon=True)
            t.start()
    except Exception as e:
        print(f"[TTS Error] {e}")
        print(f"Cortana: {text}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def speak_async(text: str):
    """Reproduce voz sin bloquear el hilo principal."""
    speak(text, blocking=False)
