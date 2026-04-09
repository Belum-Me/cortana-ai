"""
cortana/voice_loop.py

Pipeline de voz completo:
  VoiceListener  ->  LLM streaming  ->  CortanaTTS  ->  Speaker

- Interrupciones: si el usuario habla, sd.stop() inmediato + nuevo turno
- Contexto persistente (core.memory)
- Log de turnos en conversacion.log (timestamp + idioma)
- Errores silenciosos: nunca crashea el loop
- Comandos "para" / "stop" / "callate" silencian a Cortana
- set_speaking sincronizado con CortanaTTS.is_speaking
"""

import queue
import threading
import time
import logging
from pathlib import Path

from listener import VoiceListener
from core.llm import chat_fast_stream, pick_filler
from tts_engine import CortanaTTS

# ── Log de conversacion ───────────────────────────────────────────────────────

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

_STOP_WORDS = {"para", "stop", "callate", "silencio", "quiet", "calla"}


def _is_stop_cmd(text: str) -> bool:
    words = set(text.lower().split())
    return bool(words & _STOP_WORDS)


# ── VoiceLoop ─────────────────────────────────────────────────────────────────

class VoiceLoop:
    """
    Loop de voz siempre activo.

    Uso standalone:
        loop = VoiceLoop()
        loop.start()
        loop.wait()

    Integracion con la app GUI:
        loop = VoiceLoop()
        loop.start()
        loop.stop()   # al cerrar
    """

    def __init__(self):
        self._tts      = CortanaTTS()
        self._listener = VoiceListener()
        self._listener.on_speech(self._on_speech)

        # Cola maxsize=1: solo el turno mas reciente importa
        self._speech_q: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=1)
        self._running  = False

    # ── Interfaz publica ──────────────────────────────────────────────────────

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
        self._tts.stop()
        self._listener.stop()
        print("[VoiceLoop] Detenido.")

    def wait(self) -> None:
        try:
            while self._running:
                time.sleep(0.2)
        except KeyboardInterrupt:
            self.stop()

    # ── Callback del listener ─────────────────────────────────────────────────

    def _on_speech(self, text: str, lang: str) -> None:
        # Comando de parada
        if _is_stop_cmd(text):
            print(f"[VoiceLoop] Parada: '{text}'")
            self._tts.stop()
            self._listener.set_speaking(False)
            return

        # Interrupcion mientras Cortana habla
        if self._tts.is_speaking:
            print("[VoiceLoop] Interrupcion detectada")
            self._tts.stop()
            # Vaciar turno anterior
            while not self._speech_q.empty():
                try:
                    self._speech_q.get_nowait()
                except queue.Empty:
                    break

        try:
            self._speech_q.put_nowait((text, lang))
        except queue.Full:
            pass

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _pipeline_loop(self) -> None:
        while self._running:
            try:
                text, lang = self._speech_q.get(timeout=0.5)
            except queue.Empty:
                continue

            # Sincronizar: microfono silenciado mientras Cortana habla
            self._listener.set_speaking(True)
            self._tts.resume()       # limpiar stop_event de interrupcion anterior

            try:
                self._run_turn(text, lang)
            except Exception as e:
                print(f"[VoiceLoop] Error en turno: {e}")
            finally:
                self._listener.set_speaking(False)

    def _run_turn(self, text: str, lang: str) -> None:
        _log("user", text, lang)
        print(f"[{lang.upper()}] Usuario: {text}")

        # Frase de transicion — desde cache (voz Cortana) o edge-tts
        filler = pick_filler(lang)
        self._tts.speak(filler, lang=lang, blocking=True)

        if self._tts._stop_event.is_set():
            return

        reply_parts: list[str] = []

        def on_chunk(chunk: str) -> None:
            if self._tts._stop_event.is_set():
                return
            reply_parts.append(chunk)
            self._tts.speak(chunk, lang=lang, blocking=True)

        try:
            chat_fast_stream(text, lang=lang, on_chunk=on_chunk)
        except Exception as e:
            print(f"[VoiceLoop] Error LLM: {e}")
            if not self._tts._stop_event.is_set():
                self._tts.speak("Hubo un error, intenta de nuevo.", lang=lang)

        if reply_parts and not self._tts._stop_event.is_set():
            full = " ".join(reply_parts)
            _log("cortana", full, lang)
            print(f"[{lang.upper()}] Cortana: {full}")


# ── Punto de entrada standalone ───────────────────────────────────────────────

if __name__ == "__main__":
    loop = VoiceLoop()
    loop.start()
    loop.wait()
