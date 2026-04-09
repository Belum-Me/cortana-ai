"""
cortana/tools/prebuild_fillers.py

Pre-genera las frases de transición (fillers) con F5-TTS usando la voz
de Cortana. Ejecutar una sola vez; los .wav quedan en voice_samples/fillers/.

Uso:
    python tools/prebuild_fillers.py

Las frases generadas serán usadas automáticamente por voice/tts_filler.py
en tiempo real sin retraso.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
import numpy as np
import soundfile as sf

from voice.tts_clone import _patch_torchaudio, _get_model, REFERENCE_SAMPLES, _clean

OUTPUT_DIR = Path(__file__).parent.parent / "voice_samples" / "fillers"

FILLERS = {
    "es": [
        "Mmh.",
        "Dejame ver.",
        "Un momento.",
        "Claro.",
        "A ver.",
        "Entendido.",
        "Bien.",
    ],
    "en": [
        "Hmm.",
        "Let me check.",
        "Sure.",
        "One sec.",
        "Got it.",
        "Alright.",
        "Okay.",
    ],
}


def _safe_filename(text: str) -> str:
    return text.lower().replace(" ", "_").replace(".", "").replace(",", "")[:30]


def prebuild(force: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _patch_torchaudio()
    model = _get_model()
    ref_file, ref_text = REFERENCE_SAMPLES[0]  # usar ref_1 (español natural)

    total = sum(len(v) for v in FILLERS.values())
    done = 0

    for lang, phrases in FILLERS.items():
        lang_dir = OUTPUT_DIR / lang
        lang_dir.mkdir(exist_ok=True)

        for phrase in phrases:
            out_path = lang_dir / f"{_safe_filename(phrase)}.wav"

            if out_path.exists() and not force:
                print(f"[skip] {out_path.name}")
                done += 1
                continue

            print(f"[{done+1}/{total}] Generando '{phrase}'…")
            try:
                wav, sr, _ = model.infer(
                    ref_file=ref_file,
                    ref_text=ref_text,
                    gen_text=_clean(phrase),
                    remove_silence=True,
                    nfe_step=8,    # 1/4 de pasos = ~4x más rápido, calidad suficiente para frases cortas
                    speed=1.0,
                    seed=42,
                )
                # Normalizar y guardar
                if wav.dtype != np.float32:
                    wav = wav.astype(np.float32)
                peak = np.abs(wav).max()
                if peak > 0:
                    wav = wav / peak * 0.9
                sf.write(str(out_path), wav, sr, subtype="PCM_16")
                print(f"    OK: {len(wav)/sr:.2f}s → {out_path.name}")
            except Exception as e:
                print(f"    ERROR: {e}")

            done += 1

    print(f"\nFin. {done}/{total} frases en {OUTPUT_DIR}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    prebuild(force=force)
