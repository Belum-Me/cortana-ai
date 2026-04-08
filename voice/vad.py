"""
VAD + Wake Word detection 100% local con faster-whisper.
Sin internet, sin API keys.
"""

import queue
import threading
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK_DURATION = 2.5
OVERLAP = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)
OVERLAP_SAMPLES = int(SAMPLE_RATE * OVERLAP)

SPEECH_THRESHOLD = 0.015
SILENCE_THRESHOLD = 0.009
SILENCE_TIMEOUT = 1.4
MAX_DURATION = 12.0


def transcribe(audio_np: np.ndarray, language: str = "es") -> str | None:
    """Transcribe con faster-whisper (local). Sin internet."""
    from voice.whisper_stt import transcribe_audio
    return transcribe_audio(audio_np, language=language, model_size="base")


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
    Graba y detecta wake word en paralelo usando faster-whisper (tiny).
    100% local, sin internet, sin API keys.
    """

    def __init__(self, wake_words: list[str], on_wake):
        self.wake_words = [w.lower() for w in wake_words]
        self.on_wake = on_wake
        self._audio_q = queue.Queue(maxsize=4)
        self._stop = threading.Event()
        self._active = False
        self._prev_tail = np.zeros(OVERLAP_SAMPLES, dtype="int16")

    def start(self):
        # Precargar modelos en background para evitar retraso al primer uso
        threading.Thread(target=self._preload, daemon=True).start()
        threading.Thread(target=self._recorder, daemon=True).start()
        threading.Thread(target=self._processor, daemon=True).start()

    def _preload(self):
        from voice.whisper_stt import preload_models
        print("[Whisper] Precargando modelos...")
        preload_models()
        print("[Whisper] Modelos listos. Di 'Cortana' para hablar.")

    def stop(self):
        self._stop.set()

    def set_active(self, v: bool):
        self._active = v

    def _recorder(self):
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=CHUNK_SAMPLES) as stream:
            while not self._stop.is_set():
                data, _ = stream.read(CHUNK_SAMPLES)
                chunk = data.flatten()
                combined = np.concatenate([self._prev_tail, chunk])
                self._prev_tail = chunk[-OVERLAP_SAMPLES:]
                if not self._active:
                    try:
                        self._audio_q.put_nowait(combined)
                    except queue.Full:
                        pass

    def _processor(self):
        from voice.whisper_stt import contains_wake_word
        while not self._stop.is_set():
            try:
                audio = self._audio_q.get(timeout=1.0)
            except queue.Empty:
                continue

            if self._active:
                continue

            # Verificar nivel de energía antes de transcribir
            audio_f = audio.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(audio_f ** 2))
            if rms < 0.005:
                continue

            detected, text = contains_wake_word(audio_f, self.wake_words)
            if text:
                print(f"[oído] {text}")
            if detected:
                self._active = True
                self.on_wake(text)
