"""
Sistema de identificacion de voz del usuario.
Usa MFCC (Mel-Frequency Cepstral Coefficients) para crear
una huella vocal unica y verificar si el audio entrante es del usuario.
"""

import os
import json
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
import librosa
import tempfile

PROFILE_PATH = "voice_profile.json"
SAMPLE_RATE = 16000
SIMILARITY_THRESHOLD = 0.80  # 0.0 - 1.0, mas alto = mas estricto
N_MFCC = 40


def _record_sample(duration: int = 5) -> np.ndarray:
    """Graba audio del microfono por 'duration' segundos."""
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32"
    )
    sd.wait()
    return audio.flatten()


def _extract_features(audio: np.ndarray) -> np.ndarray:
    """Extrae MFCC + delta features del audio para crear la huella vocal."""
    mfcc = librosa.feature.mfcc(y=audio, sr=SAMPLE_RATE, n_mfcc=N_MFCC)
    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)
    combined = np.concatenate([mfcc, delta, delta2], axis=0)
    return np.mean(combined, axis=1)  # Vector de caracteristicas promedio


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calcula similitud coseno entre dos vectores de caracteristicas."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def train_voice(n_samples: int = 5, duration: int = 5, callback=None) -> bool:
    """
    Entrena el perfil vocal grabando n_samples muestras del usuario.
    callback(step, total, message) se llama en cada paso para actualizar UI.
    Retorna True si el entrenamiento fue exitoso.
    """
    embeddings = []

    for i in range(n_samples):
        if callback:
            callback(i + 1, n_samples, f"Muestra {i + 1}/{n_samples} — habla durante {duration} segundos")
        else:
            print(f"Muestra {i + 1}/{n_samples} — habla durante {duration} segundos...")

        audio = _record_sample(duration)
        features = _extract_features(audio)
        embeddings.append(features.tolist())

        if callback:
            callback(i + 1, n_samples, f"Muestra {i + 1} guardada.")
        else:
            print(f"  Muestra {i + 1} guardada.")

    # Guardar perfil como promedio de todas las muestras
    profile = {
        "embeddings": embeddings,
        "mean_embedding": np.mean(embeddings, axis=0).tolist(),
        "threshold": SIMILARITY_THRESHOLD,
        "n_samples": n_samples,
    }

    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f)

    if callback:
        callback(n_samples, n_samples, "Perfil vocal guardado correctamente.")
    else:
        print("Perfil vocal guardado.")

    return True


def profile_exists() -> bool:
    return os.path.exists(PROFILE_PATH)


def load_profile() -> dict | None:
    if not profile_exists():
        return None
    with open(PROFILE_PATH, "r") as f:
        return json.load(f)


def verify_speaker(audio: np.ndarray) -> tuple[bool, float]:
    """
    Verifica si el audio pertenece al usuario registrado.
    Retorna (es_el_usuario, similitud).
    """
    profile = load_profile()
    if not profile:
        return True, 1.0  # Sin perfil, acepta todo

    features = _extract_features(audio)
    mean_emb = np.array(profile["mean_embedding"])
    threshold = profile.get("threshold", SIMILARITY_THRESHOLD)

    similarity = _cosine_similarity(features, mean_emb)
    return similarity >= threshold, similarity


def verify_from_file(wav_path: str) -> tuple[bool, float]:
    """Verifica desde un archivo WAV."""
    audio, sr = librosa.load(wav_path, sr=SAMPLE_RATE)
    return verify_speaker(audio)
