"""
STT usando sounddevice (sin pyaudio) + Google Speech Recognition.
"""

import numpy as np
import sounddevice as sd
import speech_recognition as sr

SAMPLE_RATE = 16000
RECOGNIZER = sr.Recognizer()


def record_audio(duration: float = 6.0) -> np.ndarray:
    """Graba audio del microfono y retorna array numpy."""
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocking=True,
    )
    return audio.flatten()


def numpy_to_audiodata(audio_np: np.ndarray) -> sr.AudioData:
    """Convierte array numpy int16 a AudioData de SpeechRecognition."""
    return sr.AudioData(audio_np.tobytes(), SAMPLE_RATE, 2)


def transcribe(audio_np: np.ndarray, language: str = "es-ES") -> str | None:
    """Transcribe audio numpy a texto."""
    audio_data = numpy_to_audiodata(audio_np)
    try:
        return RECOGNIZER.recognize_google(audio_data, language=language)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"[STT] Error de red: {e}")
        return None


def listen_once(duration: float = 6.0) -> tuple[np.ndarray, str | None]:
    """Graba y transcribe en un solo paso. Retorna (audio, texto)."""
    audio = record_audio(duration)
    text = transcribe(audio)
    return audio, text
