"""
Cortana - Di "Cortana" para hablar con ella.
Ejecutar: python app.py
"""

import threading
import customtkinter as ctk
from core.memory import init_db
from core.llm import chat_fast
from voice.tts import speak_async
from listener import VoiceListener

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
        self._listener = VoiceListener()
        self._listener.on_speech(self._on_speech)
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
        self._listener.set_speaking(True)
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
        self._listener.set_speaking(False)

    def _startup(self):
        self._add("Sistema activo. Di «Cortana» para hablar.", is_user=False)
        self._status("● Cargando modelos...", COLORS["yellow"])
        self._listener.start()
        speak_async("Sistema activo. Cargando modelos de voz.")

    def _on_speech(self, text: str, lang: str):
        """Llamado por VoiceListener cuando se transcribe habla."""
        if self._busy:
            return

        text_lower = text.lower()
        has_wake = any(w in text_lower for w in WAKE_WORDS)
        if not has_wake:
            print(f"[ignorado/{lang}] {text}")
            return

        print(f"[activado/{lang}] {text}")
        self.after(0, lambda: self._banner("🔴 Escuchando...", COLORS["red"]))
        self.after(0, lambda: self._status("● Activada", COLORS["accent"]))
        threading.Thread(target=self._respond, args=(text,), daemon=True).start()

    def _on_close(self):
        self._listener.stop()
        self.destroy()


if __name__ == "__main__":
    app = CortanaApp()
    app.mainloop()
