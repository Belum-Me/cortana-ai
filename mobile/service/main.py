"""
Servicio de fondo para Android.
Se ejecuta siempre, incluso cuando la app esta minimizada.
Detecta el wake word 'Cortana' y notifica a la app principal.
"""

import time
import requests
import speech_recognition as sr
from android.broadcast import BroadcastReceiver  # type: ignore
from jnius import autoclass  # type: ignore

# Importar SERVER_URL del archivo de configuracion
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVER_URL = "http://TU_IP_LOCAL:8000"
WAKE_WORDS = ["cortana", "oye cortana", "hey cortana"]

recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.8


def send_notification(title: str, message: str):
    """Envia notificacion al usuario en el celular."""
    try:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        NotificationManager = autoclass("android.app.NotificationManager")
        NotificationCompat = autoclass("androidx.core.app.NotificationCompat")
        context = PythonActivity.mActivity

        builder = NotificationCompat.Builder(context, "cortana_channel")
        builder.setContentTitle(title)
        builder.setContentText(message)
        builder.setPriority(NotificationCompat.PRIORITY_HIGH)
        builder.setAutoCancel(True)

        nm = context.getSystemService(context.NOTIFICATION_SERVICE)
        nm.notify(1, builder.build())
    except Exception as e:
        print(f"[Service] Error notificacion: {e}")


def listen_for_wake_word() -> bool:
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=4)
        text = recognizer.recognize_google(audio, language="es-ES").lower()
        return any(w in text for w in WAKE_WORDS)
    except Exception:
        return False


def handle_wake():
    """Cuando detecta el wake word, escucha el comando y lo manda al servidor."""
    try:
        send_notification("Cortana", "Escuchando...")
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=8, phrase_time_limit=20)
        command = recognizer.recognize_google(audio, language="es-ES")

        r = requests.post(f"{SERVER_URL}/chat", json={"text": command}, timeout=30)
        if r.status_code == 200:
            response = r.json()["response"]
            # Truncar para notificacion
            preview = response[:100] + "..." if len(response) > 100 else response
            send_notification("Cortana", preview)
    except Exception as e:
        print(f"[Service] Error: {e}")


if __name__ == "__main__":
    print("[Cortana Service] Servicio de fondo iniciado.")
    while True:
        if listen_for_wake_word():
            handle_wake()
        time.sleep(0.1)
