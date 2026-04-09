"""
Cortana - Di "Cortana" para hablar con ella.
Ejecutar: python app.py
"""

import threading
import customtkinter as ctk
from core.memory import init_db
from core.llm import chat_fast_stream
from listener import VoiceListener
from tts_engine import CortanaTTS, get_tts
from voice_loop import _is_stop_cmd

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
        super().__init__(parent,
                         fg_color=COLORS["user"] if is_user else COLORS["cortana"],
                         corner_radius=12)
        ctk.CTkLabel(self,
                     text="Tu" if is_user else "Cortana",
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

        self._busy     = False
        self._tts      = get_tts()                 # CortanaTTS singleton
        self._listener = VoiceListener()
        self._listener.on_speech(self._on_speech)

        self._build_ui()
        init_db()
        self.after(500, self._startup)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  CORTANA",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLORS["accent"]).pack(side="left", padx=16)
        self.status_lbl = ctk.CTkLabel(hdr, text="Iniciando...",
                                       font=ctk.CTkFont(size=12),
                                       text_color=COLORS["yellow"])
        self.status_lbl.pack(side="right", padx=16)

        self.banner = ctk.CTkLabel(self,
                                   text="Di  \"Cortana\"  para hablar",
                                   font=ctk.CTkFont(size=13, weight="bold"),
                                   fg_color=COLORS["surface"],
                                   text_color=COLORS["green"],
                                   corner_radius=0, height=36)
        self.banner.pack(fill="x")

        # Label de lo que escuchó (debug / feedback visual)
        self.heard_lbl = ctk.CTkLabel(self,
                                      text="",
                                      font=ctk.CTkFont(size=11),
                                      fg_color=COLORS["bg"],
                                      text_color=COLORS["subtext"],
                                      corner_radius=0, height=20)
        self.heard_lbl.pack(fill="x")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"],
                                              scrollbar_button_color=COLORS["border"])
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        inp = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=100)
        inp.pack(fill="x")
        inp.pack_propagate(False)
        self.input_box = ctk.CTkTextbox(inp, height=52, font=ctk.CTkFont(size=14),
                                         fg_color=COLORS["user"], text_color=COLORS["text"],
                                         border_color=COLORS["border"], border_width=1,
                                         corner_radius=12)
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

    # ── Entrada de texto ──────────────────────────────────────────────────────

    def _on_enter(self, event):
        if not event.state & 0x1:
            self.send_text()
            return "break"

    def send_text(self):
        text = self.input_box.get("1.0", "end").strip()
        if not text or self._busy:
            return
        self.input_box.delete("1.0", "end")
        threading.Thread(target=self._respond, args=(text, "es"), daemon=True).start()

    # ── Pipeline de respuesta ────────────────────────────────────────────────

    def _respond(self, text: str, lang: str = "es"):
        self._busy = True
        self._tts.resume()
        self._listener.set_speaking(True)

        self.after(0, lambda: self._add(text, is_user=True))
        self.after(0, lambda: self._status("Pensando...", COLORS["accent"]))
        self.after(0, lambda: self._banner("Procesando...", COLORS["yellow"]))

        # Frase de transicion (voz Cortana desde cache, o edge-tts)
        from core.llm import pick_filler
        self._tts.speak(pick_filler(lang), lang=lang, blocking=True)

        full_reply_parts: list[str] = []

        def _on_chunk(chunk: str):
            if self._tts._stop_event.is_set():
                return
            full_reply_parts.append(chunk)
            if len(full_reply_parts) == 1:
                self.after(0, lambda: self._status("Hablando...", COLORS["green"]))
            self._tts.speak(chunk, lang=lang, blocking=True)

        try:
            chat_fast_stream(text, lang=lang, on_chunk=_on_chunk)
        except Exception as e:
            msg = f"Error: {e}"
            full_reply_parts.append(msg)
            self._tts.speak(msg, lang=lang)

        if full_reply_parts and not self._tts._stop_event.is_set():
            full_reply = " ".join(full_reply_parts)
            self.after(0, lambda: self._add(full_reply, is_user=False))

        self.after(0, lambda: self._status("Escuchando...", COLORS["yellow"]))
        self.after(0, lambda: self._banner("Di  \"Cortana\"  para hablar", COLORS["green"]))
        self._busy = False
        self._listener.set_speaking(False)

    # ── Voz entrante ─────────────────────────────────────────────────────────

    def _on_speech(self, text: str, lang: str):
        # Mostrar siempre lo que escuchó (feedback visual)
        preview = text[:60] + "..." if len(text) > 60 else text
        try:
            self.after(0, lambda: self.heard_lbl.configure(
                text=f"Escuche: \"{preview}\""))
        except RuntimeError:
            return  # ventana ya cerrada

        def _ui(fn):
            try: self.after(0, fn)
            except RuntimeError: pass

        # Comando de parada
        if _is_stop_cmd(text):
            print(f"[app] Parada: '{text}'")
            self._tts.stop()
            _ui(lambda: self._status("Escuchando...", COLORS["green"]))
            _ui(lambda: self._banner("Di  \"Cortana\"  para hablar", COLORS["green"]))
            return

        # Interrupcion mientras responde
        if self._busy:
            text_lower = text.lower()
            if any(w in text_lower for w in WAKE_WORDS):
                print(f"[app] Interrupcion con wake word")
                self._tts.stop()
                def _relaunch():
                    import time
                    for _ in range(30):
                        if not self._busy:
                            break
                        time.sleep(0.1)
                    threading.Thread(
                        target=self._respond, args=(text, lang), daemon=True
                    ).start()
                threading.Thread(target=_relaunch, daemon=True).start()
            return

        # Activacion normal
        text_lower = text.lower()
        if not any(w in text_lower for w in WAKE_WORDS):
            print(f"[ignorado/{lang}] {text}")
            return

        print(f"[activado/{lang}] {text}")
        _ui(lambda: self._banner("Escuchando...", COLORS["red"]))
        _ui(lambda: self._status("Activada", COLORS["accent"]))
        threading.Thread(target=self._respond, args=(text, lang), daemon=True).start()

    # ── Startup / cierre ─────────────────────────────────────────────────────

    def _startup(self):
        self._add("Sistema activo. Di Cortana para hablar.", is_user=False)
        self._status("Cargando modelos...", COLORS["yellow"])

        def _on_ready():
            self.after(0, lambda: self._status("Escuchando...", COLORS["green"]))
            self.after(0, lambda: self._banner("Di  \"Cortana\"  para hablar", COLORS["green"]))
            print("[App] Modelos listos. Escuchando.")

        self._listener.start(on_ready=_on_ready)
        self._tts.speak("Sistema activo.", lang="es", blocking=False)

    def _on_close(self):
        self._tts.stop()
        self._listener.stop()
        self.destroy()


if __name__ == "__main__":
    app = CortanaApp()
    app.mainloop()
