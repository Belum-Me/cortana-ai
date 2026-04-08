"""
cortana/voice_loop.py

Pipeline de voz completo:
  VoiceListener  →  LLM streaming  →  TTS  →  Speaker

Características:
  - Interrupciones: si el usuario habla mientras Cortana responde, detiene el
    TTS inmediatamente (sd.stop) y procesa la nueva entrada.
  - Contexto persistente: core.memory guarda cada turno; el LLM siempre tiene
    historial.
  - Log de turnos en conversacion.log (timestamp + idioma).
  - Errores silenciosos: ningún error crashea el loop.
  - Comandos de parada: "para" / "stop" / "cállate" silencian a Cortana.

TTS disponibles (ver _TTS_BACKEND al fondo del archivo):
  - EdgeTTS   → edge-tts + sounddevice  (principal, español natural)
  - Pyttsx3TTS → pyttsx3 + SAPI5        (placeholder, solo voces instaladas)
"""

import queue
import threading
import time
import logging
from pathlib import Path

import sounddevice as sd

from listener import VoiceListener
from core.llm import chat_fast_stream, pick_filler

# ── Logging de conversación ───────────────────────────────────────────────────

_LOG_PATH = Path(__file__).parent / "conversacion.log"

_conv_log = logging.getLogger("conversacion")
_conv_log.setLevel(logging.INFO)
_conv_log.propagate = False
if not _conv_log.handlers:
    _fh = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    _conv_log.addHandler(_fh)


def _log(role: str, text: str, lang: str) -> None:
    _conv_log.info("[%s] %s: %s", lang.upper(), role.upper(), text)


# ── Comandos de parada ────────────────────────────────────────────────────────

_STOP_WORDS = {"para", "stop", "cállate", "callate", "silencio", "quiet"}


def _is_stop_cmd(text: str) -> bool:
    words = set(text.lower().split())
    return bool(words & _STOP_WORDS)


# ── Backends de TTS ───────────────────────────────────────────────────────────

class EdgeTTS:
    """
    TTS principal: edge-tts + sounddevice.
    sd.stop() interrumpe la reproducción desde cualquier hilo.
    """

    def say(self, text: str) -> None:
        from voice.tts import speak_blocking
        speak_blocking(text)

    def interrupt(self) -> None:
        sd.stop()


class Pyttsx3TTS:
    """
    TTS placeholder: pyttsx3 / SAPI5.
    Nota: en Windows, pyttsx3 debe correr en un único hilo COM.
    La interrupción es chunk-level (espera que el chunk actual termine).
    Para voces en español instala un paquete de voz SAPI5 en Windows.
    """

    def __init__(self):
        self._q: queue.Queue = queue.Queue()
        self._done = threading.Event()
        threading.Thread(target=self._worker, daemon=True, name="pyttsx3").start()

    def _worker(self):
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 155)
        engine.setProperty("volume", 1.0)

        while True:
            text = self._q.get()
            if text is None:
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"[Pyttsx3TTS] {e}")
                try:
                    engine = pyttsx3.init()
                    engine.setProperty("rate", 155)
                except Exception:
                    pass
            finally:
                self._done.set()

    def say(self, text: str) -> None:
        self._done.clear()
        self._q.put(text)
        self._done.wait()

    def interrupt(self) -> None:
        # SAPI5 no soporta stop() seguro desde otro hilo;
        # la interrupción ocurre al terminar el chunk actual.
        pass


# Cambia aquí para alternar entre backends:
_TTS_BACKEND = EdgeTTS


# ── VoiceLoop ─────────────────────────────────────────────────────────────────

class VoiceLoop:
    """
    Loop de voz siempre activo.

    Uso standalone:
        loop = VoiceLoop()
        loop.start()
        loop.wait()       # bloquea hasta Ctrl+C

    Integración con la app:
        loop = VoiceLoop()
        loop.start()
        # más tarde:
        loop.stop()
    """

    def __init__(self, tts_cls=None):
        self._tts = (tts_cls or _TTS_BACKEND)()
        self._listener = VoiceListener()
        self._listener.on_speech(self._on_speech)

        # Cola con capacidad 1: solo importa el turno más reciente
        self._speech_q: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=1)
        self._interrupt = threading.Event()
        self._speaking = threading.Event()
        self._running = False

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._listener.start()
        threading.Thread(
            target=self._pipeline_loop,
            daemon=True,
            name="voice-pipeline",
        ).start()
        print("[VoiceLoop] Listo. Di 'Cortana' para hablar.")

    def stop(self) -> None:
        self._running = False
        self._interrupt.set()
        self._tts.interrupt()
        self._listener.stop()
        print("[VoiceLoop] Detenido.")

    def wait(self) -> None:
        """Bloquea el hilo principal; sale con Ctrl+C."""
        try:
            while self._running:
                time.sleep(0.2)
        except KeyboardInterrupt:
            self.stop()

    # ── Callback del listener ─────────────────────────────────────────────────

    def _on_speech(self, text: str, lang: str) -> None:
        """Llamado por VoiceListener cada vez que se transcribe habla."""

        if _is_stop_cmd(text):
            print(f"[VoiceLoop] Parada: '{text}'")
            self._interrupt.set()
            self._tts.interrupt()
            self._listener.set_speaking(False)
            return

        if self._speaking.is_set():
            print("[VoiceLoop] Interrupción — nueva entrada recibida")
            self._interrupt.set()
            self._tts.interrupt()
            # Descartar turno anterior de la cola
            while not self._speech_q.empty():
                try:
                    self._speech_q.get_nowait()
                except queue.Empty:
                    break

        try:
            self._speech_q.put_nowait((text, lang))
        except queue.Full:
            pass  # Silencioso: cola ocupada

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _pipeline_loop(self) -> None:
        """Hilo dedicado: procesa un turno a la vez en orden."""
        while self._running:
            try:
                text, lang = self._speech_q.get(timeout=0.5)
            except queue.Empty:
                continue

            self._interrupt.clear()
            self._speaking.set()
            self._listener.set_speaking(True)

            try:
                self._run_turn(text, lang)
            except Exception as e:
                print(f"[VoiceLoop] Error en turno: {e}")
            finally:
                self._speaking.clear()
                self._listener.set_speaking(False)

    def _run_turn(self, text: str, lang: str) -> None:
        """Ejecuta un turno completo: filler → stream LLM → TTS chunk a chunk."""
        _log("user", text, lang)
        print(f"[{lang.upper()}] Usuario: {text}")

        # Frase inmediata mientras la API procesa (~100ms de latencia percibida)
        self._say(pick_filler(lang))
        if self._interrupt.is_set():
            return

        reply_parts: list[str] = []

        def on_chunk(chunk: str) -> None:
            if self._interrupt.is_set():
                return
            reply_parts.append(chunk)
            self._say(chunk)

        try:
            chat_fast_stream(text, lang=lang, on_chunk=on_chunk)
        except Exception as e:
            print(f"[VoiceLoop] Error LLM: {e}")
            if not self._interrupt.is_set():
                self._say("Hubo un error, intenta de nuevo.")

        if reply_parts and not self._interrupt.is_set():
            full = " ".join(reply_parts)
            _log("cortana", full, lang)
            print(f"[{lang.upper()}] Cortana: {full}")

    def _say(self, text: str) -> None:
        """Reproduce texto por TTS respetando la señal de interrupción."""
        if not text or self._interrupt.is_set():
            return
        try:
            self._tts.say(text)
        except Exception as e:
            print(f"[VoiceLoop] Error TTS: {e}")


# ── Punto de entrada standalone ───────────────────────────────────────────────

if __name__ == "__main__":
    loop = VoiceLoop()
    loop.start()
    loop.wait()
