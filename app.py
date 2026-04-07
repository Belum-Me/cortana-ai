"""
Cortana - Interfaz de escritorio / preview de la app movil.
Ejecutar: python app.py
"""

import threading
import customtkinter as ctk
from core.memory import init_db
from core.llm import chat

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
    "border": "#45475a",
}


class MessageBubble(ctk.CTkFrame):
    def __init__(self, parent, text: str, is_user: bool):
        color = COLORS["user_bubble"] if is_user else COLORS["cortana_bubble"]
        super().__init__(parent, fg_color=color, corner_radius=12)

        prefix = "Tu" if is_user else "Cortana"
        prefix_color = COLORS["accent"] if not is_user else COLORS["subtext"]

        header = ctk.CTkLabel(
            self,
            text=prefix,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=prefix_color,
        )
        header.pack(anchor="w", padx=12, pady=(8, 2))

        msg = ctk.CTkLabel(
            self,
            text=text,
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text"],
            wraplength=520,
            justify="left",
        )
        msg.pack(anchor="w", padx=12, pady=(0, 10))


class CortanaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CORTANA")
        self.geometry("680x820")
        self.minsize(500, 600)
        self.configure(fg_color=COLORS["bg"])
        self.resizable(True, True)
        self._build_ui()
        init_db()
        self.after(500, self._greeting)

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="  CORTANA",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(side="left", padx=16, pady=12)

        self.status_label = ctk.CTkLabel(
            header,
            text="● Activa",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["green"],
        )
        self.status_label.pack(side="right", padx=16)

        # Chat area
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["bg"],
            scrollbar_button_color=COLORS["border"],
        )
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # Input area
        input_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=100)
        input_frame.pack(fill="x")
        input_frame.pack_propagate(False)

        self.input_box = ctk.CTkTextbox(
            input_frame,
            height=52,
            font=ctk.CTkFont(size=14),
            fg_color=COLORS["user_bubble"],
            text_color=COLORS["text"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12,
        )
        self.input_box.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=20)
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)

        self.send_btn = ctk.CTkButton(
            input_frame,
            text="Enviar",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            hover_color="#74c7ec",
            width=90,
            height=52,
            corner_radius=12,
            command=self.send_message,
        )
        self.send_btn.pack(side="right", padx=(0, 12), pady=20)

        # Boton de voz
        self.voice_btn = ctk.CTkButton(
            self,
            text="Mantener para hablar",
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["user_bubble"],
            text_color=COLORS["text"],
            hover_color=COLORS["border"],
            height=44,
            corner_radius=0,
        )
        self.voice_btn.pack(fill="x")
        self.voice_btn.bind("<ButtonPress-1>", self._start_voice)
        self.voice_btn.bind("<ButtonRelease-1>", self._stop_voice)

    def _greeting(self):
        self._add_message("Sistema cognitivo activo. Estoy lista.", is_user=False)

    def _add_message(self, text: str, is_user: bool):
        bubble = MessageBubble(self.scroll, text=text, is_user=is_user)
        bubble.pack(fill="x", pady=4, padx=4)
        self.after(100, lambda: self.scroll._parent_canvas.yview_moveto(1.0))

    def _on_enter(self, event):
        if not event.state & 0x1:  # Shift no presionado
            self.send_message()
            return "break"

    def send_message(self):
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            return
        self.input_box.delete("1.0", "end")
        self._add_message(text, is_user=True)
        self.send_btn.configure(state="disabled", text="...")
        self.status_label.configure(text="● Pensando...", text_color=COLORS["accent"])
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
        self.status_label.configure(text="● Activa", text_color=COLORS["green"])

    def _start_voice(self, event):
        self.voice_btn.configure(
            text="Escuchando...",
            fg_color=COLORS["red"],
            text_color="white",
        )
        threading.Thread(target=self._listen_voice, daemon=True).start()

    def _stop_voice(self, event):
        self.voice_btn.configure(
            text="Mantener para hablar",
            fg_color=COLORS["user_bubble"],
            text_color=COLORS["text"],
        )

    def _listen_voice(self):
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=20)
            text = recognizer.recognize_google(audio, language="es-ES")
            self.after(0, lambda: self._add_message(text, is_user=True))
            self.after(0, lambda: self.status_label.configure(
                text="● Pensando...", text_color=COLORS["accent"]
            ))
            response = chat(text)
            self.after(0, lambda: self._show_response(response))
        except Exception:
            self.after(0, lambda: self._add_message(
                "No te escuche bien. Intenta de nuevo.", is_user=False
            ))
        finally:
            self.after(0, lambda: self.voice_btn.configure(
                text="Mantener para hablar",
                fg_color=COLORS["user_bubble"],
                text_color=COLORS["text"],
            ))


if __name__ == "__main__":
    app = CortanaApp()
    app.mainloop()
