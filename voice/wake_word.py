"""
Detector de wake word para Cortana.
Escucha continuamente el microfono y se activa cuando detecta la palabra "Cortana".
"""

import speech_recognition as sr
import threading
import time

WAKE_WORDS = ["cortana", "oye cortana", "hey cortana", "hola cortana"]

recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.8


def _contains_wake_word(text: str) -> bool:
    text_lower = text.lower().strip()
    return any(w in text_lower for w in WAKE_WORDS)


def listen_for_wake_word(timeout_per_chunk: int = 3) -> bool:
    """
    Escucha brevemente y retorna True si detecta el wake word.
    Disenado para usarse en un loop continuo.
    """
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            try:
                audio = recognizer.listen(source, timeout=timeout_per_chunk, phrase_time_limit=4)
            except sr.WaitTimeoutError:
                return False

        text = recognizer.recognize_google(audio, language="es-ES")
        if _contains_wake_word(text):
            print(f"[Wake word detectada] '{text}'")
            return True
    except sr.UnknownValueError:
        pass
    except sr.RequestError as e:
        print(f"[Wake word STT Error] {e}")
    except Exception:
        pass
    return False


def run_always_on(on_wake_callback, stop_event: threading.Event = None):
    """
    Loop de escucha permanente.
    Llama on_wake_callback() cada vez que detecta el wake word.
    """
    print("Cortana en modo siempre activa. Di 'Cortana' para activar.")
    while True:
        if stop_event and stop_event.is_set():
            break
        if listen_for_wake_word():
            on_wake_callback()
        time.sleep(0.1)
