"""
cortana/test_clone.py

Prueba de clonación de voz con F5-TTS.

NOTA: Coqui TTS (pip install TTS) requiere Python < 3.12 y no puede
instalarse en Python 3.14. F5-TTS es el equivalente moderno: mismo
mecanismo de clonación 0-shot, soporta español, compatible con Python 3.14.

Uso:
    python test_clone.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf

REF_1 = Path(__file__).parent / "voice_samples" / "ref_1.wav"
REF_2 = Path(__file__).parent / "voice_samples" / "ref_2.wav"
OUTPUT = Path(__file__).parent / "voice_samples" / "test_output.wav"
TEST_TEXT = "Hola, soy Cortana. ¿En qué puedo ayudarte?"


def main():
    print("=" * 60)
    print("Test de clonación de voz — F5-TTS (XTTS-v2 equivalente)")
    print("=" * 60)

    # Verificar referencias
    for p in [REF_1, REF_2]:
        if not p.exists():
            print(f"ERROR: No existe {p}")
            print("Ejecuta: python tools/prebuild_fillers.py")
            return
        info = sf.info(str(p))
        print(f"Referencia: {p.name} — {info.duration:.1f}s @ {info.samplerate}Hz")

    # Parche torchaudio (no necesita FFmpeg)
    from voice.tts_clone import _patch_torchaudio, _get_model, REFERENCE_SAMPLES
    _patch_torchaudio()

    print(f"\nCargando modelo F5TTS_v1_Base...")
    model = _get_model()
    print("Modelo listo.")

    ref_file, ref_text = REFERENCE_SAMPLES[0]

    print(f"\nSintetizando: '{TEST_TEXT}'")
    print("(Primera vez: ~1-2 min en CPU con nfe_step=16)\n")

    wav, sr, _ = model.infer(
        ref_file=ref_file,
        ref_text=ref_text,
        gen_text=TEST_TEXT,
        remove_silence=True,
        nfe_step=16,
        speed=1.0,
        seed=42,
    )

    # Normalizar
    wav = wav.astype(np.float32)
    peak = np.abs(wav).max()
    if peak > 0:
        wav = wav / peak * 0.9

    # Guardar
    sf.write(str(OUTPUT), wav, sr, subtype="PCM_16")
    duration = len(wav) / sr
    print(f"Guardado: {OUTPUT}")
    print(f"Duracion: {duration:.2f}s @ {sr}Hz")

    # Reproducir
    print("\nReproduciendo...")
    sd.play(wav, sr)
    sd.wait()
    print("Listo.")


if __name__ == "__main__":
    main()
