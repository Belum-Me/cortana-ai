"""
Wake word detection local con pvporcupine.
No requiere internet. ~1% CPU.

Wake words built-in disponibles:
  jarvis, computer, terminator, alexa, bumblebee,
  picovoice, porcupine, hey google, hey siri, blueberry, etc.

Para usar "cortana" como wake word:
  1. Ve a https://console.picovoice.ai
  2. Crea un modelo personalizado con la palabra "cortana"
  3. Descarga el archivo .ppn
  4. Pon la ruta en PORCUPINE_MODEL_PATH en .env
"""

import os
import threading
import numpy as np
import sounddevice as sd
import pvporcupine
from dotenv import load_dotenv

load_dotenv()

PICOVOICE_KEY = os.getenv("PICOVOICE_KEY", "")
WAKE_WORD = os.getenv("PORCUPINE_KEYWORD", "jarvis")        # wake word built-in
CUSTOM_MODEL = os.getenv("PORCUPINE_MODEL_PATH", "")        # .ppn personalizado (opcional)


class PorcupineListener:
    """
    Escucha wake word con pvporcupine de forma continua y eficiente.
    Cuando detecta la palabra, llama on_wake().
    """

    def __init__(self, on_wake, access_key: str = None):
        self.on_wake = on_wake
        self._access_key = access_key or PICOVOICE_KEY
        self._stop = threading.Event()
        self._active = False
        self._porcupine = None

        if not self._access_key:
            raise ValueError(
                "Falta PICOVOICE_KEY en .env\n"
                "Obtén tu key gratis en: https://console.picovoice.ai/signup"
            )

    def _init_porcupine(self):
        if CUSTOM_MODEL and os.path.exists(CUSTOM_MODEL):
            # Modelo personalizado (ej: "cortana.ppn")
            self._porcupine = pvporcupine.create(
                access_key=self._access_key,
                keyword_paths=[CUSTOM_MODEL],
            )
            print(f"[Porcupine] Modelo personalizado: {CUSTOM_MODEL}")
        else:
            # Wake word built-in
            kw = WAKE_WORD if WAKE_WORD in pvporcupine.KEYWORDS else "jarvis"
            self._porcupine = pvporcupine.create(
                access_key=self._access_key,
                keywords=[kw],
            )
            print(f"[Porcupine] Wake word: '{kw}'")

    def start(self):
        self._init_porcupine()
        threading.Thread(target=self._loop, daemon=True).start()
        print(f"[Porcupine] Escuchando wake word...")

    def stop(self):
        self._stop.set()
        if self._porcupine:
            self._porcupine.delete()

    def set_active(self, v: bool):
        self._active = v

    def _loop(self):
        frame_len = self._porcupine.frame_length
        sr = self._porcupine.sample_rate

        with sd.InputStream(samplerate=sr, channels=1,
                            dtype="int16", blocksize=frame_len) as stream:
            while not self._stop.is_set():
                if self._active:
                    # Vaciar el buffer mientras procesa
                    stream.read(frame_len)
                    continue

                data, _ = stream.read(frame_len)
                pcm = data.flatten().tolist()
                result = self._porcupine.process(pcm)

                if result >= 0:
                    print(f"[Porcupine] Wake word detectada!")
                    self._active = True
                    self.on_wake()


def is_configured() -> bool:
    return bool(PICOVOICE_KEY)
