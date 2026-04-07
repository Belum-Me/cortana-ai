"""
Analisis de audio ambiental.
Cortana puede escuchar el entorno y reportar lo que percibe.
"""

import speech_recognition as sr
import tempfile
import os
import numpy as np

recognizer = sr.Recognizer()


def record_ambient(duration: int = 10) -> str | None:
    """
    Graba audio ambiental durante 'duration' segundos.
    Retorna la ruta del archivo WAV temporal.
    """
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wav

        sample_rate = 16000
        print(f"Grabando entorno por {duration} segundos...")
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16"
        )
        sd.wait()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        wav.write(tmp_path, sample_rate, audio_data)
        return tmp_path
    except Exception as e:
        print(f"[Ambient] Error grabando: {e}")
        return None


def transcribe_ambient(duration: int = 10) -> str:
    """
    Graba y transcribe lo que escucha en el entorno.
    """
    tmp_path = record_ambient(duration)
    if not tmp_path:
        return "No pude acceder al microfono."

    try:
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language="es-ES")
        return text if text else "No detecte habla clara en el entorno."
    except sr.UnknownValueError:
        return "No detecte habla clara en el entorno."
    except Exception as e:
        return f"Error al analizar el entorno: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def get_ambient_level() -> dict:
    """
    Mide el nivel de ruido ambiental actual.
    Retorna nivel (silencioso/moderado/ruidoso) y volumen en dB.
    """
    try:
        import sounddevice as sd
        sample_rate = 16000
        duration = 2
        data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
        rms = float(np.sqrt(np.mean(data ** 2)))
        db = 20 * np.log10(rms + 1e-10)

        if db < -40:
            level = "silencioso"
        elif db < -20:
            level = "moderado"
        else:
            level = "ruidoso"

        return {"level": level, "db": round(db, 1)}
    except Exception as e:
        return {"level": "desconocido", "db": None, "error": str(e)}
