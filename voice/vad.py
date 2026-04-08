"""
Voice Activity Detection (VAD) sin pyaudio.
Detecta cuando el usuario empieza y termina de hablar.
"""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK_MS = 80                 # ms por bloque de analisis
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)

SPEECH_THRESHOLD = 0.018     # RMS para detectar que empezó a hablar
SILENCE_THRESHOLD = 0.010    # RMS para detectar silencio
SILENCE_TIMEOUT = 1.4        # segundos de silencio para cortar
MAX_DURATION = 12.0          # grabacion maxima
PRE_BUFFER = 6               # bloques de pre-buffer (antes del speech)


def record_speech(timeout: float = 8.0) -> np.ndarray | None:
    """
    Espera a que el usuario hable, graba hasta que termine.
    Retorna el audio como numpy int16, o None si no hubo habla.
    """
    silence_limit = int(SILENCE_TIMEOUT * 1000 / CHUNK_MS)
    max_chunks = int(MAX_DURATION * 1000 / CHUNK_MS)
    wait_limit = int(timeout * 1000 / CHUNK_MS)

    pre_buffer = []
    chunks = []
    speech_started = False
    silence_count = 0
    waited = 0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK_SAMPLES) as stream:
        while True:
            data, _ = stream.read(CHUNK_SAMPLES)
            chunk = data.flatten()
            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0

            if not speech_started:
                pre_buffer.append(chunk)
                if len(pre_buffer) > PRE_BUFFER:
                    pre_buffer.pop(0)

                if rms > SPEECH_THRESHOLD:
                    speech_started = True
                    chunks = list(pre_buffer) + [chunk]
                else:
                    waited += 1
                    if waited > wait_limit:
                        return None  # timeout esperando habla
            else:
                chunks.append(chunk)
                if rms < SILENCE_THRESHOLD:
                    silence_count += 1
                    if silence_count >= silence_limit:
                        break
                else:
                    silence_count = 0
                if len(chunks) >= max_chunks:
                    break

    if len(chunks) < 3:
        return None
    return np.concatenate(chunks)


def listen_for_wake_word(wake_words: list[str], recognizer, timeout: float = 4.0) -> tuple[bool, str]:
    """
    Graba un fragmento corto y detecta si contiene un wake word.
    Retorna (detectado, texto).
    """
    import speech_recognition as sr
    audio = sd.rec(int(2.5 * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="int16", blocking=True).flatten()
    data = sr.AudioData(audio.tobytes(), SAMPLE_RATE, 2)
    try:
        text = recognizer.recognize_google(data, language="es-ES")
        detected = any(w in text.lower() for w in wake_words)
        return detected, text
    except Exception:
        return False, ""
