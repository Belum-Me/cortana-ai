"""Mide el nivel RMS de tu micrófono en tiempo real. Ctrl+C para salir."""
import numpy as np
import sounddevice as sd

RATE = 16000
CHUNK = 480  # 30ms

print("Habla normalmente. Observa los valores RMS.")
print("Umbral actual de Cortana: RMS_SPEECH=0.018  ENERGY_FLOOR=0.003")
print("Ctrl+C para salir.\n")

with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK) as s:
    while True:
        data, _ = s.read(CHUNK)
        f = data.flatten().astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(f ** 2)))
        bar = int(rms * 1000)
        label = "HABLA" if rms > 0.018 else ("ruido" if rms > 0.003 else "silencio")
        print(f"RMS={rms:.4f}  {'#'*min(bar,50):<50} {label}", end="\r")
