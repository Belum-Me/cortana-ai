"""
cortana/tts_engine.py

CortanaTTS — motor de síntesis de voz para Cortana.

Estrategia híbrida (CPU, tiempo real):
  - Frases cacheadas (fillers, confirmaciones): WAV pre-generado con F5-TTS
    en la voz exacta de Cortana → latencia <50ms
  - Texto libre en streaming: edge-tts → latencia ~200ms por chunk
  - stop(): sd.stop() inmediato, sin clicks

Uso:
    tts = CortanaTTS()
    tts.speak("Hola", lang="es")
    tts.speak_streaming(chunks, lang="es")
    tts.stop()
    print(tts.is_speaking)
"""

import threading
import queue
import re
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

# ── Rutas ─────────────────────────────────────────────────────────────────────

_SAMPLES_DIR = Path(__file__).parent / "voice_samples"
_CACHE_DIR   = _SAMPLES_DIR / "fillers"
_REF_FILES   = [
    str(_SAMPLES_DIR / "ref_1.wav"),
    str(_SAMPLES_DIR / "ref_2.wav"),
]


# ── CortanaTTS ────────────────────────────────────────────────────────────────

class CortanaTTS:
    """
    Motor de TTS de Cortana con soporte para:
    - Reproducción bloqueante y no bloqueante
    - Streaming chunk a chunk
    - Interrupción instantánea (sd.stop)
    - Cache de frases frecuentes en voz clonada de Cortana
    """

    def __init__(self):
        self._stop_event  = threading.Event()
        self._playing     = threading.Event()   # True mientras hay audio
        self._lock        = threading.Lock()     # solo un speak a la vez

        # Cache: clave normalizada → (wav_float32, sample_rate)
        self._cache: dict[str, tuple[np.ndarray, int]] = {}
        self._load_cache()

    # ── Propiedad pública ─────────────────────────────────────────────────────

    @property
    def is_speaking(self) -> bool:
        return self._playing.is_set()

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def speak(self, text: str, lang: str = "es", blocking: bool = True) -> None:
        """
        Sintetiza y reproduce text.
        blocking=True: espera a que termine el audio antes de retornar.
        blocking=False: lanza en hilo y retorna inmediatamente.
        """
        if blocking:
            self._play_text(text, lang)
        else:
            threading.Thread(
                target=self._play_text,
                args=(text, lang),
                daemon=True,
            ).start()

    def speak_streaming(self, text_chunks, lang: str = "es") -> None:
        """
        Recibe un iterable de chunks de texto y los reproduce en secuencia.
        Cada chunk se sintetiza tan pronto llega — no espera el total.
        Respeta stop_event entre chunks.
        """
        for chunk in text_chunks:
            if self._stop_event.is_set():
                break
            chunk = chunk.strip()
            if chunk:
                self._play_text(chunk, lang)

    def stop(self) -> None:
        """Detiene la reproducción inmediatamente, sin artefactos."""
        self._stop_event.set()
        sd.stop()                  # corta sounddevice en el ciclo actual
        self._playing.clear()

    def resume(self) -> None:
        """Limpia la señal de parada para permitir nuevas reproducciones."""
        self._stop_event.clear()

    # ── Cache ────────────────────────────────────────────────────────────────

    def _load_cache(self) -> None:
        """Carga todos los WAVs pre-generados en memoria."""
        if not _CACHE_DIR.exists():
            return
        for wav_path in _CACHE_DIR.rglob("*.wav"):
            key = self._cache_key(wav_path.stem)
            try:
                wav, sr = sf.read(str(wav_path), dtype="float32")
                if wav.ndim == 2:
                    wav = wav.mean(axis=1)
                self._cache[key] = (wav, sr)
            except Exception as e:
                print(f"[CortanaTTS] cache skip {wav_path.name}: {e}")
        print(f"[CortanaTTS] Cache cargada: {len(self._cache)} frases")

    @staticmethod
    def _cache_key(text: str) -> str:
        """Normaliza texto para lookup en cache."""
        t = text.lower().strip()
        t = re.sub(r"[^\w\s]", "", t)          # quitar puntuación
        t = re.sub(r"\s+", "_", t.strip())
        return t[:40]

    def _cache_hit(self, text: str) -> tuple[np.ndarray, int] | None:
        key = self._cache_key(text)
        return self._cache.get(key)

    # ── Síntesis y reproducción ───────────────────────────────────────────────

    def _play_text(self, text: str, lang: str) -> None:
        """Sintetiza text y lo reproduce de forma bloqueante."""
        if self._stop_event.is_set():
            return

        # 1. Intentar cache (voz de Cortana, instantáneo)
        cached = self._cache_hit(text)
        if cached:
            self._play_array(*cached)
            return

        # 2. edge-tts (rápido, ~200ms, voz Elvira)
        wav, sr = self._synth_edge(text, lang)
        if wav is not None:
            self._play_array(wav, sr)

    def _play_array(self, wav: np.ndarray, sr: int) -> None:
        """Reproduce numpy array por sounddevice, bloqueante hasta que acabe o se pare."""
        if self._stop_event.is_set():
            return
        with self._lock:
            self._playing.set()
            try:
                sd.play(wav, sr)
                sd.wait()           # sd.stop() desde otro hilo hace que wait() retorne
            except Exception as e:
                print(f"[CortanaTTS] play error: {e}")
            finally:
                self._playing.clear()

    @staticmethod
    def _synth_edge(text: str, lang: str) -> tuple[np.ndarray | None, int]:
        """Sintetiza con edge-tts y retorna (array_float32, sample_rate)."""
        import asyncio
        import tempfile
        import os
        import librosa
        import edge_tts

        VOICES = {
            "es": ("es-ES-ElviraNeural", "-8%", "-4Hz"),
            "en": ("en-US-JennyNeural", "-5%",  "0Hz"),
        }
        voice, rate, pitch = VOICES.get(lang, VOICES["es"])

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = f.name
        try:
            async def _synth():
                comm = edge_tts.Communicate(text=text, voice=voice,
                                             rate=rate, pitch=pitch)
                await comm.save(tmp)

            asyncio.run(_synth())
            wav, sr = librosa.load(tmp, sr=22050, mono=True)
            return wav, sr
        except Exception as e:
            print(f"[CortanaTTS] edge-tts error: {e}")
            return None, 0
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: CortanaTTS | None = None


def get_tts() -> CortanaTTS:
    """Retorna la instancia global de CortanaTTS (lazy init)."""
    global _instance
    if _instance is None:
        _instance = CortanaTTS()
    return _instance
