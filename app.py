"""
Cortana - Siempre activa. Di "Cortana" para hablar con ella.
Ejecutar: python app.py
"""

import threading
import time
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import customtkinter as ctk
from core.memory import init_db
from core.llm import chat_fast
from voice.speaker_profile import verify_speaker, profile_exists, SAMPLE_RATE
from voice.tts import speak_async

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg":       "#1e1e2e",
    "surface":  "#181825",
    "user":     "#313244",
    "cortana":  "#24243e",
    "accent":   "#89b4fa",
    "text":     "#cdd6f4",
    "subtext":  "#6c7086",
    "green":    "#a6e3a1",
    "red":      "#f38ba8",
    "yellow":   "#f9e2af",
    "border":   "#45475a",
}

WAKE_WORDS = ["cortana", "oye cortana", "hey cortana", "hola cortana"]
RECOGNIZER = sr.Recognizer()
RECOGNIZER.energy_threshold = 300
RECOGNIZER.dynamic_energy_threshold = True
RECOGNIZER.pause_threshold = 1.0


class Bubble(ctk.CTkFrame):
    def __init__(self, parent, text: str, is_user: bool):
        super().__init__(parent, fg_color=COLORS["user"] if is_user else COLORS["cortana"], corner_radius=12)
        ctk.CTkLabel(self, text="Tú" if is_user else "Cortana",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COLORS["subtext"] if is_user else COLORS["accent"]
                     ).pack(anchor="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=14),
                     text_color=COLORS["text"], wraplength=520, justify="left"
                     ).pack(anchor="w", padx=12, pady=(0, 10))


class TrainingDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_complete):
        super().__init__(parent)
        self.title("Entrenar tu voz")
        self.geometry("480x300")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.on_complete = on_complete
        self.grab_set()

        ctk.CTkLabel(self, text="Entrenamiento de voz",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COLORS["accent"]).pack(pady=(24, 4))
        ctk.CTkLabel(self,
                     text="Cortana grabará 5 muestras de tu voz.\nHabla con naturalidad 5 segundos cada vez.",
                     font=ctk.CTkFont(size=13), text_color=COLORS["subtext"], justify="center"
                     ).pack(pady=(0, 16))
        self.status = ctk.CTkLabel(self, text="Presiona Iniciar cuando estés listo.",
                                   font=ctk.CTkFont(size=14), text_color=COLORS["text"])
        self.status.pack(pady=6)
        self.bar = ctk.CTkProgressBar(self, width=380)
        self.bar.set(0)
        self.bar.pack(pady=10)
        self.btn = ctk.CTkButton(self, text="Iniciar", font=ctk.CTkFont(size=14, weight="bold"),
                                 fg_color=COLORS["accent"], text_color=COLORS["bg"],
                                 width=200, height=44, command=self._start)
        self.btn.pack(pady=14)

    def _start(self):
        self.btn.configure(state="disabled", text="Entrenando...")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import json
        embeddings = []
        from voice.speaker_profile import _extract_features
        for i in range(5):
            for c in range(3, 0, -1):
                self.after(0, lambda c=c, i=i: self.status.configure(
                    text=f"Muestra {i+1}/5 — Habla en {c}..."))
                time.sleep(1)
            self.after(0, lambda i=i: self.status.configure(
                text=f"Muestra {i+1}/5 — Grabando..."))
            audio = sd.rec(int(5 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
            sd.wait()
            embeddings.append(_extract_features(audio.flatten()).tolist())
            self.after(0, lambda i=i: self.bar.set((i + 1) / 5))

        profile = {
            "embeddings": embeddings,
            "mean_embedding": np.mean(embeddings, axis=0).tolist(),
            "threshold": 0.80,
            "n_samples": 5,
        }
        with open("voice_profile.json", "w") as f:
            json.dump(profile, f)

        self.after(0, lambda: self.status.configure(
            text="Perfil guardado. Cortana ya te reconoce.", text_color=COLORS["green"]))
        self.after(0, lambda: self.btn.configure(
            state="normal", text="Cerrar", command=self._done))

    def _done(self):
        self.on_complete()
        self.destroy()


class CortanaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CORTANA")
        self.geometry("700x860")
        self.minsize(500, 600)
        self.configure(fg_color=COLORS["bg"])
        self._stop = threading.Event()
        self._processing = False
        self._build_ui()
        init_db()
        self.after(800, self._startup)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  CORTANA", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLORS["accent"]).pack(side="left", padx=16)
        self.status_lbl = ctk.CTkLabel(hdr, text="● Iniciando...",
                                       font=ctk.CTkFont(size=12), text_color=COLORS["yellow"])
        self.status_lbl.pack(side="right", padx=16)

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=44)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        ctk.CTkButton(tb, text="Entrenar mi voz", font=ctk.CTkFont(size=12),
                      fg_color=COLORS["border"], text_color=COLORS["text"],
                      hover_color=COLORS["user"], width=140, height=30,
                      command=self._open_training).pack(side="left", padx=12, pady=7)

        # Indicador de escucha
        self.listen_lbl = ctk.CTkLabel(tb, text="🎙 Escucha permanente activa — Di 'Cortana' para hablar",
                                       font=ctk.CTkFont(size=12), text_color=COLORS["green"])
        self.listen_lbl.pack(side="left", padx=12)

        # Chat
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"],
                                             scrollbar_button_color=COLORS["border"])
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # Input
        inp = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=100)
        inp.pack(fill="x")
        inp.pack_propagate(False)
        self.input_box = ctk.CTkTextbox(inp, height=52, font=ctk.CTkFont(size=14),
                                        fg_color=COLORS["user"], text_color=COLORS["text"],
                                        border_color=COLORS["border"], border_width=1, corner_radius=12)
        self.input_box.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=20)
        self.input_box.bind("<Return>", self._on_enter)
        ctk.CTkButton(inp, text="Enviar", font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=COLORS["accent"], text_color=COLORS["bg"],
                      hover_color="#74c7ec", width=90, height=52, corner_radius=12,
                      command=self.send_text).pack(side="right", padx=(0, 12), pady=20)

    def _set_status(self, text, color):
        self.status_lbl.configure(text=text, text_color=color)

    def _add_msg(self, text: str, is_user: bool):
        Bubble(self.scroll, text=text, is_user=is_user).pack(fill="x", pady=4, padx=4)
        self.after(100, lambda: self.scroll._parent_canvas.yview_moveto(1.0))

    def _on_enter(self, event):
        if not event.state & 0x1:
            self.send_text()
            return "break"

    def send_text(self):
        text = self.input_box.get("1.0", "end").strip()
        if not text or self._processing:
            return
        self.input_box.delete("1.0", "end")
        self._respond(text)

    def _respond(self, text: str):
        self._processing = True
        self._add_msg(text, is_user=True)
        self._set_status("● Pensando...", COLORS["accent"])
        self.listen_lbl.configure(text="⏳ Procesando...")
        threading.Thread(target=self._get_and_speak, args=(text,), daemon=True).start()

    def _get_and_speak(self, text: str):
        try:
            reply = chat_fast(text)
        except Exception as e:
            reply = f"Error: {e}"
        self.after(0, lambda: self._add_msg(reply, is_user=False))
        self.after(0, lambda: self._set_status("● Escuchando...", COLORS["yellow"]))
        self.after(0, lambda: self.listen_lbl.configure(
            text="🎙 Escucha permanente activa — Di 'Cortana' para hablar"))
        speak_async(reply)
        self._processing = False

    # ── Escucha permanente ─────────────────────────────────────────────────────

    def _startup(self):
        if not profile_exists():
            self._add_msg(
                "Hola. No tengo tu perfil vocal todavía. Presiona 'Entrenar mi voz' para que solo responda a ti. "
                "De todas formas ya estoy escuchando — di 'Cortana' para hablar.",
                is_user=False
            )
        else:
            self._add_msg("Sistema activo. Te reconozco. Di 'Cortana' para hablar.", is_user=False)
            speak_async("Sistema activo. Estoy escuchando.")

        self._set_status("● Escuchando...", COLORS["yellow"])
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        while not self._stop.is_set():
            if self._processing:
                time.sleep(0.3)
                continue
            try:
                with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
                    RECOGNIZER.adjust_for_ambient_noise(source, duration=0.3)
                    try:
                        audio = RECOGNIZER.listen(source, timeout=3, phrase_time_limit=8)
                    except sr.WaitTimeoutError:
                        continue

                # Extraer numpy para verificacion de voz
                raw = np.frombuffer(
                    audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2),
                    dtype=np.int16
                )
                audio_np = raw.astype(np.float32) / 32768.0

                # Verificar que es el usuario
                if profile_exists():
                    is_me, sim = verify_speaker(audio_np)
                    if not is_me:
                        continue

                # Transcribir
                try:
                    text = RECOGNIZER.recognize_google(audio, language="es-ES")
                except sr.UnknownValueError:
                    continue

                # Detectar wake word o responder si ya se activo
                if any(w in text.lower() for w in WAKE_WORDS):
                    self.after(0, lambda t=text: self._respond(t))

            except Exception:
                time.sleep(0.5)

    # ── Entrenamiento ──────────────────────────────────────────────────────────

    def _open_training(self):
        TrainingDialog(self, on_complete=self._training_done)

    def _training_done(self):
        self._add_msg("Perfecto. Ya tengo tu huella vocal. Solo responderé a tu voz.", is_user=False)
        speak_async("Perfecto. Ya te reconozco.")

    def _on_close(self):
        self._stop.set()
        self.destroy()


if __name__ == "__main__":
    app = CortanaApp()
    app.mainloop()
