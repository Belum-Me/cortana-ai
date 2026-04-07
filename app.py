"""
Cortana - Interfaz de escritorio con escucha permanente e identificacion vocal.
Ejecutar: python app.py
"""

import threading
import time
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import customtkinter as ctk
from core.memory import init_db
from core.llm import chat
from voice.speaker_profile import (
    train_voice, verify_speaker, profile_exists, SAMPLE_RATE
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg": "#1e1e2e",
    "surface": "#181825",
    "user_bubble": "#313244",
    "cortana_bubble": "#1e1e2e",
    "accent": "#89b4fa",
    "text": "#cdd6f4",
    "subtext": "#6c7086",
    "green": "#a6e3a1",
    "red": "#f38ba8",
    "yellow": "#f9e2af",
    "border": "#45475a",
}

WAKE_WORDS = ["cortana", "oye cortana", "hey cortana", "hola cortana"]
RECOGNIZER = sr.Recognizer()
RECOGNIZER.energy_threshold = 300
RECOGNIZER.dynamic_energy_threshold = True
RECOGNIZER.pause_threshold = 1.0


class MessageBubble(ctk.CTkFrame):
    def __init__(self, parent, text: str, is_user: bool):
        color = COLORS["user_bubble"] if is_user else COLORS["cortana_bubble"]
        super().__init__(parent, fg_color=color, corner_radius=12)
        prefix = "Tu" if is_user else "Cortana"
        prefix_color = COLORS["accent"] if not is_user else COLORS["subtext"]

        ctk.CTkLabel(
            self, text=prefix,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=prefix_color,
        ).pack(anchor="w", padx=12, pady=(8, 2))

        ctk.CTkLabel(
            self, text=text,
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text"],
            wraplength=520, justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))


class TrainingDialog(ctk.CTkToplevel):
    """Ventana de entrenamiento de voz."""

    def __init__(self, parent, on_complete):
        super().__init__(parent)
        self.title("Entrenar tu voz")
        self.geometry("480x320")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.on_complete = on_complete
        self.grab_set()

        ctk.CTkLabel(
            self, text="Entrenamiento de voz",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(pady=(24, 4))

        ctk.CTkLabel(
            self,
            text="Cortana grabara 5 muestras de tu voz.\nHabla con naturalidad durante 5 segundos cada vez.",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["subtext"],
            justify="center",
        ).pack(pady=(0, 20))

        self.status_label = ctk.CTkLabel(
            self, text="Presiona Iniciar cuando estes listo.",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text"],
        )
        self.status_label.pack(pady=8)

        self.progress = ctk.CTkProgressBar(self, width=380)
        self.progress.set(0)
        self.progress.pack(pady=12)

        self.start_btn = ctk.CTkButton(
            self, text="Iniciar entrenamiento",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            width=220, height=44,
            command=self._start_training,
        )
        self.start_btn.pack(pady=16)

    def _start_training(self):
        self.start_btn.configure(state="disabled", text="Entrenando...")
        threading.Thread(target=self._run_training, daemon=True).start()

    def _run_training(self):
        def callback(step, total, message):
            self.after(0, lambda: self.status_label.configure(text=message))
            self.after(0, lambda: self.progress.set(step / total))
            time.sleep(0.5)

        # Countdown antes de cada muestra
        for i in range(5):
            for countdown in range(3, 0, -1):
                self.after(0, lambda c=countdown, s=i: self.status_label.configure(
                    text=f"Muestra {s+1}/5 — Habla en {c}..."
                ))
                time.sleep(1)
            # Grabar
            self.after(0, lambda s=i: self.status_label.configure(
                text=f"Muestra {s+1}/5 — Grabando 5 segundos..."
            ))
            self.after(0, lambda s=i: self.progress.set((s + 0.5) / 5))

            audio = sd.rec(
                int(5 * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32"
            )
            sd.wait()

            from voice.speaker_profile import _extract_features
            if not hasattr(self, "_embeddings"):
                self._embeddings = []
            self._embeddings.append(_extract_features(audio.flatten()).tolist())

            self.after(0, lambda s=i: self.progress.set((s + 1) / 5))

        # Guardar perfil
        import json
        profile = {
            "embeddings": self._embeddings,
            "mean_embedding": np.mean(self._embeddings, axis=0).tolist(),
            "threshold": 0.80,
            "n_samples": 5,
        }
        with open("voice_profile.json", "w") as f:
            json.dump(profile, f)

        self.after(0, lambda: self.status_label.configure(
            text="Perfil vocal guardado. Cortana ya te reconoce.",
            text_color=COLORS["green"]
        ))
        self.after(0, lambda: self.start_btn.configure(
            state="normal", text="Cerrar", command=self._finish
        ))

    def _finish(self):
        self.on_complete()
        self.destroy()


class CortanaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CORTANA")
        self.geometry("700x860")
        self.minsize(500, 600)
        self.configure(fg_color=COLORS["bg"])
        self.resizable(True, True)

        self._always_on = False
        self._always_on_thread = None
        self._stop_event = threading.Event()

        self._build_ui()
        init_db()
        self.after(500, self._startup)

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="  CORTANA",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(side="left", padx=16)

        self.status_label = ctk.CTkLabel(
            header, text="● Iniciando...",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["yellow"],
        )
        self.status_label.pack(side="right", padx=16)

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=44)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        self.train_btn = ctk.CTkButton(
            toolbar, text="Entrenar mi voz",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["border"],
            text_color=COLORS["text"],
            hover_color=COLORS["user_bubble"],
            width=140, height=30,
            command=self._open_training,
        )
        self.train_btn.pack(side="left", padx=12, pady=7)

        self.always_on_btn = ctk.CTkButton(
            toolbar, text="Escucha permanente: OFF",
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["border"],
            text_color=COLORS["subtext"],
            hover_color=COLORS["user_bubble"],
            width=200, height=30,
            command=self._toggle_always_on,
        )
        self.always_on_btn.pack(side="left", padx=4, pady=7)

        # Chat
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
        )
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # Input
        input_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=100)
        input_frame.pack(fill="x")
        input_frame.pack_propagate(False)

        self.input_box = ctk.CTkTextbox(
            input_frame, height=52,
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["user_bubble"],
            text_color=COLORS["text"],
            border_color=COLORS["border"],
            border_width=1, corner_radius=12,
        )
        self.input_box.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=20)
        self.input_box.bind("<Return>", self._on_enter)

        self.send_btn = ctk.CTkButton(
            input_frame, text="Enviar",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            hover_color="#74c7ec",
            width=90, height=52, corner_radius=12,
            command=self.send_message,
        )
        self.send_btn.pack(side="right", padx=(0, 12), pady=20)

        # Boton voz
        self.voice_btn = ctk.CTkButton(
            self, text="Mantener para hablar",
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["user_bubble"],
            text_color=COLORS["text"],
            hover_color=COLORS["border"],
            height=44, corner_radius=0,
        )
        self.voice_btn.pack(fill="x")
        self.voice_btn.bind("<ButtonPress-1>", self._start_voice)
        self.voice_btn.bind("<ButtonRelease-1>", self._stop_voice)

    def _startup(self):
        if profile_exists():
            self._set_status("● Activa", COLORS["green"])
            self._add_message("Sistema activo. Te reconozco. Estoy lista.", is_user=False)
        else:
            self._set_status("● Sin perfil vocal", COLORS["yellow"])
            self._add_message(
                "Hola. Para que solo responda a tu voz, presiona 'Entrenar mi voz' en la barra superior.",
                is_user=False
            )

    def _set_status(self, text, color):
        self.status_label.configure(text=text, text_color=color)

    def _add_message(self, text: str, is_user: bool):
        bubble = MessageBubble(self.scroll, text=text, is_user=is_user)
        bubble.pack(fill="x", pady=4, padx=4)
        self.after(100, lambda: self.scroll._parent_canvas.yview_moveto(1.0))

    def _on_enter(self, event):
        if not event.state & 0x1:
            self.send_message()
            return "break"

    def send_message(self):
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            return
        self.input_box.delete("1.0", "end")
        self._add_message(text, is_user=True)
        self.send_btn.configure(state="disabled", text="...")
        self._set_status("● Pensando...", COLORS["accent"])
        threading.Thread(target=self._get_response, args=(text,), daemon=True).start()

    def _get_response(self, text: str):
        try:
            response = chat(text)
        except Exception as e:
            response = f"Error: {e}"
        self.after(0, lambda: self._show_response(response))

    def _show_response(self, response: str):
        self._add_message(response, is_user=False)
        self.send_btn.configure(state="normal", text="Enviar")
        status = "● Escuchando..." if self._always_on else "● Activa"
        color = COLORS["yellow"] if self._always_on else COLORS["green"]
        self._set_status(status, color)

    # ─── Voz manual ───────────────────────────────────────────────────────────

    def _start_voice(self, event):
        self.voice_btn.configure(text="Escuchando...", fg_color=COLORS["red"], text_color="white")
        threading.Thread(target=self._listen_and_send, daemon=True).start()

    def _stop_voice(self, event):
        self.voice_btn.configure(
            text="Mantener para hablar",
            fg_color=COLORS["user_bubble"],
            text_color=COLORS["text"],
        )

    def _listen_and_send(self, verify=True):
        """Graba, verifica voz y envia al chat."""
        try:
            audio_data, recognized_text = self._capture_voice()
            if not recognized_text:
                self.after(0, lambda: self._add_message("No te escuche bien.", is_user=False))
                return

            # Verificar que es el usuario
            if verify and profile_exists():
                is_user, similarity = verify_speaker(audio_data)
                if not is_user:
                    self.after(0, lambda: self._set_status(
                        f"● Voz no reconocida ({similarity:.0%})", COLORS["red"]
                    ))
                    return

            self.after(0, lambda t=recognized_text: self._add_message(t, is_user=True))
            self.after(0, lambda: self._set_status("● Pensando...", COLORS["accent"]))
            response = chat(recognized_text)
            self.after(0, lambda r=response: self._show_response(r))

        except Exception as e:
            self.after(0, lambda: self._add_message(f"Error de voz: {e}", is_user=False))
        finally:
            self.after(0, lambda: self.voice_btn.configure(
                text="Mantener para hablar",
                fg_color=COLORS["user_bubble"],
                text_color=COLORS["text"],
            ))

    def _capture_voice(self) -> tuple[np.ndarray, str | None]:
        """Graba audio del microfono y lo convierte a texto + array numpy."""
        with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
            RECOGNIZER.adjust_for_ambient_noise(source, duration=0.5)
            audio = RECOGNIZER.listen(source, timeout=10, phrase_time_limit=20)

        # Array de numpy para verificacion
        raw = np.frombuffer(audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2), dtype=np.int16)
        audio_np = raw.astype(np.float32) / 32768.0

        try:
            text = RECOGNIZER.recognize_google(audio, language="es-ES")
        except sr.UnknownValueError:
            text = None
        return audio_np, text

    # ─── Escucha permanente ────────────────────────────────────────────────────

    def _toggle_always_on(self):
        if self._always_on:
            self._stop_always_on()
        else:
            self._start_always_on()

    def _start_always_on(self):
        self._always_on = True
        self._stop_event.clear()
        self.always_on_btn.configure(
            text="Escucha permanente: ON",
            fg_color=COLORS["green"],
            text_color=COLORS["bg"],
        )
        self._set_status("● Escuchando...", COLORS["yellow"])
        self._always_on_thread = threading.Thread(
            target=self._always_on_loop, daemon=True
        )
        self._always_on_thread.start()

    def _stop_always_on(self):
        self._always_on = False
        self._stop_event.set()
        self.always_on_btn.configure(
            text="Escucha permanente: OFF",
            fg_color=COLORS["border"],
            text_color=COLORS["subtext"],
        )
        self._set_status("● Activa", COLORS["green"])

    def _always_on_loop(self):
        """Loop de escucha permanente: espera wake word, verifica voz, responde."""
        while not self._stop_event.is_set():
            try:
                with sr.Microphone(sample_rate=SAMPLE_RATE) as source:
                    RECOGNIZER.adjust_for_ambient_noise(source, duration=0.3)
                    try:
                        audio = RECOGNIZER.listen(source, timeout=3, phrase_time_limit=5)
                    except sr.WaitTimeoutError:
                        continue

                raw = np.frombuffer(
                    audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2),
                    dtype=np.int16
                )
                audio_np = raw.astype(np.float32) / 32768.0

                # Verificar identidad antes de transcribir
                if profile_exists():
                    is_user, sim = verify_speaker(audio_np)
                    if not is_user:
                        continue  # No es el usuario, ignorar

                # Transcribir
                try:
                    text = RECOGNIZER.recognize_google(audio, language="es-ES")
                except sr.UnknownValueError:
                    continue

                # Detectar wake word
                if any(w in text.lower() for w in WAKE_WORDS):
                    self.after(0, lambda: self._set_status("● Activada!", COLORS["accent"]))
                    self.after(0, lambda t=text: self._add_message(t, is_user=True))

                    response = chat(text)
                    self.after(0, lambda r=response: self._add_message(r, is_user=False))
                    self.after(0, lambda: self._set_status("● Escuchando...", COLORS["yellow"]))

            except Exception:
                time.sleep(0.5)

    # ─── Entrenamiento ─────────────────────────────────────────────────────────

    def _open_training(self):
        TrainingDialog(self, on_complete=self._on_training_complete)

    def _on_training_complete(self):
        self._set_status("● Activa", COLORS["green"])
        self._add_message(
            "Perfecto. Ya tengo tu huella vocal. De ahora en adelante solo respondere a tu voz.",
            is_user=False
        )


if __name__ == "__main__":
    app = CortanaApp()
    app.mainloop()
