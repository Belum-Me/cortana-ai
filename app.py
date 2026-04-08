"""
Cortana - Di "Cortana" para hablar con ella.
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
from voice.tts import speak_async
from voice.vad import record_speech, transcribe, ContinuousListener
from voice.porcupine_ww import is_configured as porcupine_configured

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg":      "#1e1e2e",
    "surface": "#181825",
    "user":    "#313244",
    "cortana": "#24243e",
    "accent":  "#89b4fa",
    "text":    "#cdd6f4",
    "subtext": "#6c7086",
    "green":   "#a6e3a1",
    "red":     "#f38ba8",
    "yellow":  "#f9e2af",
    "border":  "#45475a",
}

WAKE_WORDS = ["cortana", "oye cortana", "hey cortana"]
SAMPLE_RATE = 16000




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


class CortanaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CORTANA")
        self.geometry("700x860")
        self.minsize(500, 600)
        self.configure(fg_color=COLORS["bg"])
        self._stop = threading.Event()
        self._busy = False
        self._porcupine = None
        self._listener = ContinuousListener(WAKE_WORDS, self._on_wake)
        self._build_ui()
        init_db()
        self.after(500, self._startup)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  CORTANA",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLORS["accent"]).pack(side="left", padx=16)
        self.status_lbl = ctk.CTkLabel(hdr, text="● Iniciando...",
                                       font=ctk.CTkFont(size=12),
                                       text_color=COLORS["yellow"])
        self.status_lbl.pack(side="right", padx=16)

        # Indicador
        self.banner = ctk.CTkLabel(self,
                                   text="🎙 Di  \"Cortana\"  para hablar",
                                   font=ctk.CTkFont(size=13, weight="bold"),
                                   fg_color=COLORS["surface"],
                                   text_color=COLORS["green"],
                                   corner_radius=0, height=36)
        self.banner.pack(fill="x")

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
        ctk.CTkButton(inp, text="Enviar",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=COLORS["accent"], text_color=COLORS["bg"],
                      hover_color="#74c7ec", width=90, height=52, corner_radius=12,
                      command=self.send_text).pack(side="right", padx=(0, 12), pady=20)

    def _status(self, text, color):
        self.status_lbl.configure(text=text, text_color=color)

    def _banner(self, text, color):
        self.banner.configure(text=text, text_color=color)

    def _add(self, text: str, is_user: bool):
        Bubble(self.scroll, text, is_user).pack(fill="x", pady=4, padx=4)
        self.after(100, lambda: self.scroll._parent_canvas.yview_moveto(1.0))

    def _on_enter(self, event):
        if not event.state & 0x1:
            self.send_text()
            return "break"

    def send_text(self):
        text = self.input_box.get("1.0", "end").strip()
        if not text or self._busy:
            return
        self.input_box.delete("1.0", "end")
        threading.Thread(target=self._respond, args=(text,), daemon=True).start()

    def _respond(self, text: str):
        self._busy = True
        self.after(0, lambda: self._add(text, is_user=True))
        self.after(0, lambda: self._status("● Pensando...", COLORS["accent"]))
        self.after(0, lambda: self._banner("⏳ Procesando...", COLORS["yellow"]))
        try:
            reply = chat_fast(text)
        except Exception as e:
            reply = f"Error: {e}"
        self.after(0, lambda: self._add(reply, is_user=False))
        self.after(0, lambda: self._status("● Escuchando...", COLORS["yellow"]))
        self.after(0, lambda: self._banner("🎙 Di  \"Cortana\"  para hablar", COLORS["green"]))
        speak_async(reply)
        self._busy = False
        self._listener.set_active(False)
        if self._porcupine:
            self._porcupine.set_active(False)

    def _startup(self):
        if porcupine_configured():
            from voice.porcupine_ww import PorcupineListener, WAKE_WORD
            import os
            ww = os.getenv("PORCUPINE_KEYWORD", "jarvis")
            self._add(f"Sistema activo. Di «{ww}» para hablar. (Porcupine activo)", is_user=False)
            self._porcupine = PorcupineListener(on_wake=self._on_wake_porcupine)
            self._porcupine.start()
        else:
            self._add("Sistema activo. Di «Cortana» para hablar.", is_user=False)
            self._listener.start()

        self._status("● Escuchando...", COLORS["yellow"])
        speak_async("Sistema activo. Estoy escuchando.")

    def _on_wake_porcupine(self):
        """Callback de Porcupine: ya detectó la wake word, grabar comando."""
        print("[Porcupine] Wake word — grabando comando...")
        self.after(0, lambda: self._banner("🔴 Escuchando tu pregunta...", COLORS["red"]))
        self.after(0, lambda: self._status("● Activada", COLORS["accent"]))

        cmd_audio = record_speech(timeout=5.0)
        cmd_text = transcribe(cmd_audio) if cmd_audio is not None else None
        print(f"[Whisper] {cmd_text}")

        if cmd_text:
            threading.Thread(target=self._respond, args=(cmd_text,), daemon=True).start()
        else:
            self.after(0, lambda: self._banner("🎙 Di la wake word para hablar", COLORS["green"]))
            self.after(0, lambda: self._status("● Escuchando...", COLORS["yellow"]))
            if self._porcupine:
                self._porcupine.set_active(False)

    def _on_wake(self, wake_text: str):
        """Llamado cuando se detecta el wake word."""
        print(f"[wake] {wake_text}")
        self.after(0, lambda: self._banner("🔴 Escuchando tu pregunta...", COLORS["red"]))
        self.after(0, lambda: self._status("● Activada", COLORS["accent"]))

        # Grabar comando con VAD
        cmd_audio = record_speech(timeout=5.0)
        cmd_text = transcribe(cmd_audio) if cmd_audio is not None else None
        print(f"[cmd] {cmd_text}")

        full = f"{wake_text}. {cmd_text}" if cmd_text else wake_text
        threading.Thread(target=self._respond, args=(full,), daemon=True).start()

    def _on_close(self):
        self._listener.stop()
        if self._porcupine:
            self._porcupine.stop()
        self._stop.set()
        self.destroy()


if __name__ == "__main__":
    app = CortanaApp()
    app.mainloop()
