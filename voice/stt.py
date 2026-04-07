import speech_recognition as sr

recognizer = sr.Recognizer()

# Ajustes para captura natural
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 1.2  # Espera 1.2s de silencio antes de cortar


def listen(timeout: int = 10, phrase_time_limit: int = 30) -> str | None:
    """
    Escucha del microfono y convierte a texto.
    Retorna el texto reconocido o None si falla.
    """
    with sr.Microphone() as source:
        print("Cortana escuchando...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit
            )
        except sr.WaitTimeoutError:
            return None

    try:
        text = recognizer.recognize_google(audio, language="es-ES")
        return text.strip()
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"[STT Error] {e}")
        return None


def listen_once() -> str | None:
    """Escucha un unico fragmento de voz."""
    return listen(timeout=10, phrase_time_limit=20)
