"""
cortana/listener.py

VoiceListener — siempre activo, detección de voz por VAD de energía + ZCR.
Reemplaza webrtcvad (no compatible con Python 3.14 en Windows) con una
implementación equivalente usando numpy + sounddevice.

Estados: IDLE → LISTENING → PROCESSING → SPEAKING → IDLE
"""

import threading
import queue
import time
import numpy as np
import sounddevice as sd
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable


# ── Constantes ─────────────────────────────────────────────────────────────────

SAMPLE_RATE      = 16000
FRAME_MS         = 30                              # ms por frame de análisis
FRAME_SAMPLES    = int(SAMPLE_RATE * FRAME_MS / 1000)  # 480 muestras

# VAD — umbrales
# Si el micrófono es silencioso, bajar RMS_SPEECH a 0.008 o menos
RMS_SPEECH       = 0.010     # RMS mínimo para considerar habla (bajado de 0.018)
ZCR_SPEECH       = 0.08      # Zero Crossing Rate mínimo (bajado de 0.15)
ENERGY_FLOOR     = 0.001     # por debajo = silencio absoluto (bajado de 0.003)

# Timings
SILENCE_TIMEOUT  = 1.2       # segundos de silencio para cerrar turno
PRE_BUFFER_MS    = 400       # ms de audio antes del inicio de habla
MAX_UTTERANCE_S  = 15.0      # máximo de grabación por turno

PRE_BUFFER_FRAMES = int(PRE_BUFFER_MS / FRAME_MS)
SILENCE_FRAMES    = int(SILENCE_TIMEOUT * 1000 / FRAME_MS)
MAX_FRAMES        = int(MAX_UTTERANCE_S * 1000 / FRAME_MS)


# ── Estado ──────────────────────────────────────────────────────────────────────

class State(Enum):
    IDLE       = auto()   # esperando actividad
    LISTENING  = auto()   # detectó habla, grabando
    PROCESSING = auto()   # transcribiendo
    SPEAKING   = auto()   # Cortana está hablando (micrófono silenciado)


@dataclass
class SpeechResult:
    text: str
    language: str
    duration_s: float


# ── VAD ─────────────────────────────────────────────────────────────────────────

def _is_speech(frame: np.ndarray) -> bool:
    """
    Determina si un frame de audio contiene habla.
    Combina RMS (energía) + ZCR (frecuencia de cruces por cero).
    Equivalente funcional a webrtcvad aggressiveness=2.
    """
    if len(frame) == 0:
        return False

    f = frame.astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(f ** 2)))

    if rms < ENERGY_FLOOR:
        return False

    # Zero Crossing Rate: distingue habla de ruido de fondo
    signs = np.sign(f)
    signs[signs == 0] = 1
    zcr = float(np.mean(np.abs(np.diff(signs)) / 2))

    return rms > RMS_SPEECH and zcr > ZCR_SPEECH


# ── Transcripción ────────────────────────────────────────────────────────────────

def _transcribe(audio: np.ndarray) -> SpeechResult | None:
    """
    Transcribe con faster-whisper base.
    Detecta idioma automáticamente entre español e inglés.
    """
    from voice.whisper_stt import _get_model

    model = _get_model("base")
    audio_f = audio.astype(np.float32) / 32768.0

    segments, info = model.transcribe(
        audio_f,
        beam_size=3,
        language=None,           # autodetección
        task="transcribe",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )

    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    if not parts:
        return None

    text = " ".join(parts)
    lang = info.language if info.language in ("es", "en") else "es"
    duration = len(audio_f) / SAMPLE_RATE

    return SpeechResult(text=text, language=lang, duration_s=duration)


# ── VoiceListener ────────────────────────────────────────────────────────────────

class VoiceListener:
    """
    Listener de voz siempre activo con máquina de estados.

    Uso:
        listener = VoiceListener()
        listener.on_speech(lambda text, lang: print(f"[{lang}] {text}"))
        listener.start()
        ...
        listener.stop()
    """

    def __init__(self):
        self._state       = State.IDLE
        self._state_lock  = threading.Lock()
        self._stop_event  = threading.Event()
        self._callback: Callable[[str, str], None] | None = None
        self._work_q      = queue.Queue()

        # Buffer circular de pre-audio
        self._pre_buffer  = deque(maxlen=PRE_BUFFER_FRAMES)
        self._recording   : list[np.ndarray] = []
        self._silence_n   = 0

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def on_speech(self, callback: Callable[[str, str], None]) -> "VoiceListener":
        """Registra callback(texto, idioma). Retorna self para encadenar."""
        self._callback = callback
        return self

    def set_speaking(self, speaking: bool) -> None:
        """Silencia el micrófono mientras Cortana habla (evita eco)."""
        with self._state_lock:
            if speaking:
                self._state = State.SPEAKING
                self._recording.clear()
                self._silence_n = 0
                print("[Listener] SPEAKING — micrófono silenciado")
            else:
                self._state = State.IDLE
                print("[Listener] IDLE — micrófono activo")

    def start(self, on_ready=None) -> None:
        """Inicia el listener en hilos separados. on_ready() se llama cuando Whisper está listo."""
        from voice.whisper_stt import preload_models
        threading.Thread(
            target=preload_models,
            kwargs={"on_ready": on_ready},
            daemon=True,
        ).start()
        threading.Thread(target=self._audio_loop, daemon=True, name="audio-loop").start()
        threading.Thread(target=self._worker_loop, daemon=True, name="transcription-worker").start()
        print("[Listener] Iniciado. Di 'Cortana' en cualquier momento.")

    def stop(self) -> None:
        """Detiene el listener limpiamente."""
        self._stop_event.set()
        print("[Listener] Detenido.")

    @property
    def state(self) -> State:
        with self._state_lock:
            return self._state

    # ── Loop de audio ──────────────────────────────────────────────────────────

    def _audio_loop(self) -> None:
        """Lee frames del micrófono y aplica la máquina de estados."""
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
        ) as stream:
            while not self._stop_event.is_set():
                frame_data, _ = stream.read(FRAME_SAMPLES)
                frame = frame_data.flatten()
                self._process_frame(frame)

    def _process_frame(self, frame: np.ndarray) -> None:
        with self._state_lock:
            state = self._state

        if state == State.SPEAKING:
            # Ignorar completamente mientras Cortana habla
            return

        if state == State.PROCESSING:
            # No capturar mientras se procesa el turno anterior
            return

        speech = _is_speech(frame)

        if state == State.IDLE:
            self._pre_buffer.append(frame)
            if speech:
                # Inicio de habla detectado
                self._recording = list(self._pre_buffer)
                self._silence_n = 0
                with self._state_lock:
                    self._state = State.LISTENING
                print("[Listener] LISTENING")

        elif state == State.LISTENING:
            self._recording.append(frame)

            if speech:
                self._silence_n = 0
            else:
                self._silence_n += 1

            # Fin de turno: silencio prolongado o duración máxima
            end_of_turn = (
                self._silence_n >= SILENCE_FRAMES or
                len(self._recording) >= MAX_FRAMES
            )

            if end_of_turn:
                audio = np.concatenate(self._recording)
                self._recording = []
                self._silence_n = 0
                with self._state_lock:
                    self._state = State.PROCESSING
                dur = len(audio) / SAMPLE_RATE
                rms_total = float(np.sqrt(np.mean(audio.astype(np.float32)**2))) / 32768.0
                print(f"[Listener] PROCESSING {dur:.1f}s  rms={rms_total:.4f}")
                self._work_q.put(audio)

    # ── Worker de transcripción ────────────────────────────────────────────────

    def _worker_loop(self) -> None:
        """Hilo dedicado a transcripción para no bloquear el audio."""
        while not self._stop_event.is_set():
            try:
                audio = self._work_q.get(timeout=0.5)
            except queue.Empty:
                continue

            result = _transcribe(audio)

            with self._state_lock:
                self._state = State.IDLE

            if result and result.text:
                print(f"[Listener] [{result.language}] \"{result.text}\"")
                if self._callback:
                    threading.Thread(
                        target=self._callback,
                        args=(result.text, result.language),
                        daemon=True,
                    ).start()
            else:
                print("[Listener] IDLE (Whisper no detecto habla)")
