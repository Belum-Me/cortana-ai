"""
VAD con grabacion y transcripcion en paralelo.
Nunca pierde el wake word porque graba sin parar.
"""

import queue
import threading
import numpy as np
import sounddevice as sd
import speech_recognition as sr

SAMPLE_RATE = 16000
CHUNK_DURATION = 2.0          # segundos por bloque de deteccion
OVERLAP = 0.5                 # segundos de solapamiento entre bloques
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
OVERLAP_SAMPLES = int(SAMPLE_RATE * OVERLAP)

SPEECH_THRESHOLD = 0.015
SILENCE_THRESHOLD = 0.009
SILENCE_TIMEOUT = 1.4
MAX_DURATION = 12.0

_recognizer = sr.Recognizer()


def transcribe(audio: np.ndarray, language: str = "es-ES") -> str | None:
    data = sr.AudioData(audio.tobytes(), SAMPLE_RATE, 2)
    try:
        return _recognizer.recognize_google(data, language=language)
    except Exception:
        return None


def record_speech(timeout: float = 6.0) -> np.ndarray | None:
    """Graba con VAD: espera habla, corta en silencio."""
    CHUNK_MS = 80
    CHUNK_S = int(SAMPLE_RATE * CHUNK_MS / 1000)
    silence_limit = int(SILENCE_TIMEOUT * 1000 / CHUNK_MS)
    max_chunks = int(MAX_DURATION * 1000 / CHUNK_MS)
    wait_limit = int(timeout * 1000 / CHUNK_MS)
    PRE = 5

    pre_buf, chunks = [], []
    started, silence_n, waited = False, 0, 0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK_S) as stream:
        while True:
            data, _ = stream.read(CHUNK_S)
            chunk = data.flatten()
            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0

            if not started:
                pre_buf.append(chunk)
                if len(pre_buf) > PRE:
                    pre_buf.pop(0)
                if rms > SPEECH_THRESHOLD:
                    started = True
                    chunks = list(pre_buf) + [chunk]
                else:
                    waited += 1
                    if waited > wait_limit:
                        return None
            else:
                chunks.append(chunk)
                if rms < SILENCE_THRESHOLD:
                    silence_n += 1
                    if silence_n >= silence_limit:
                        break
                else:
                    silence_n = 0
                if len(chunks) >= max_chunks:
                    break

    return np.concatenate(chunks) if len(chunks) > 3 else None


class ContinuousListener:
    """
    Graba y transcribe en paralelo sin tiempo muerto.
    Llama on_wake(texto) cuando detecta el wake word.
    """

    def __init__(self, wake_words: list[str], on_wake):
        self.wake_words = [w.lower() for w in wake_words]
        self.on_wake = on_wake
        self._audio_q = queue.Queue(maxsize=4)
        self._stop = threading.Event()
        self._active = False   # True cuando está procesando un comando
        self._prev_tail = np.zeros(OVERLAP_SAMPLES, dtype="int16")

    def start(self):
        threading.Thread(target=self._recorder, daemon=True).start()
        threading.Thread(target=self._processor, daemon=True).start()

    def stop(self):
        self._stop.set()

    def set_active(self, v: bool):
        self._active = v

    def _recorder(self):
        """Graba bloques continuos y los mete en la cola."""
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=CHUNK_SAMPLES) as stream:
            while not self._stop.is_set():
                data, _ = stream.read(CHUNK_SAMPLES)
                chunk = data.flatten()

                # Solapar con el final del bloque anterior
                combined = np.concatenate([self._prev_tail, chunk])
                self._prev_tail = chunk[-OVERLAP_SAMPLES:]

                if not self._active:
                    try:
                        self._audio_q.put_nowait(combined)
                    except queue.Full:
                        pass  # descartar si cola llena

    def _processor(self):
        """Transcribe bloques y detecta wake word."""
        while not self._stop.is_set():
            try:
                audio = self._audio_q.get(timeout=1.0)
            except queue.Empty:
                continue

            if self._active:
                continue

            text = transcribe(audio)
            if not text:
                continue

            print(f"[oído] {text}")

            if any(w in text.lower() for w in self.wake_words):
                self._active = True
                self.on_wake(text)
