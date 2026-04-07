"""
App Android de Cortana - Interfaz movil.
Construir APK con: buildozer android debug
"""

import threading
import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from kivy.core.window import Window
from kivy.metrics import dp

# URL del servidor Cortana (cambiar por la URL de ngrok en produccion)
SERVER_URL = "http://TU_IP_LOCAL:8000"  # ej: http://192.168.1.10:8000


def set_server_url(url: str):
    global SERVER_URL
    SERVER_URL = url.rstrip("/")


class MessageBubble(BoxLayout):
    def __init__(self, text: str, is_user: bool, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.padding = [dp(8), dp(4)]
        self.spacing = dp(8)

        color = get_color_from_hex("#1e1e2e") if not is_user else get_color_from_hex("#313244")
        prefix = "Tu" if is_user else "Cortana"
        full_text = f"[b]{prefix}:[/b] {text}"

        lbl = Label(
            text=full_text,
            markup=True,
            text_size=(Window.width * 0.85, None),
            halign="left",
            valign="top",
            color=get_color_from_hex("#cdd6f4"),
            font_size=dp(15),
            padding=(dp(12), dp(8)),
        )
        lbl.bind(texture_size=lbl.setter("size"))
        lbl.bind(size=self.update_height)

        self.add_widget(lbl)

    def update_height(self, instance, value):
        self.height = value[1] + dp(16)


class CortanaApp(App):
    def build(self):
        Window.clearcolor = get_color_from_hex("#1e1e2e")
        self.title = "Cortana"
        self.listening = False
        self.message_widgets = []

        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), dp(8)])
        title_lbl = Label(
            text="[b]CORTANA[/b]",
            markup=True,
            font_size=dp(20),
            color=get_color_from_hex("#89b4fa"),
            halign="left",
        )
        self.status_lbl = Label(
            text="Conectando...",
            font_size=dp(12),
            color=get_color_from_hex("#6c7086"),
            halign="right",
        )
        header.add_widget(title_lbl)
        header.add_widget(self.status_lbl)
        root.add_widget(header)

        # Chat area
        self.scroll = ScrollView(size_hint=(1, 1))
        self.chat_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=[0, dp(8)],
        )
        self.chat_box.bind(minimum_height=self.chat_box.setter("height"))
        self.scroll.add_widget(self.chat_box)
        root.add_widget(self.scroll)

        # Input area
        input_bar = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(8), padding=[0, dp(8)])

        self.text_input = TextInput(
            hint_text="Escribe o habla con Cortana...",
            multiline=False,
            size_hint_x=0.75,
            background_color=get_color_from_hex("#313244"),
            foreground_color=get_color_from_hex("#cdd6f4"),
            cursor_color=get_color_from_hex("#89b4fa"),
            font_size=dp(15),
        )
        self.text_input.bind(on_text_validate=self.send_text)

        send_btn = Button(
            text="Enviar",
            size_hint_x=0.25,
            background_color=get_color_from_hex("#89b4fa"),
            color=get_color_from_hex("#1e1e2e"),
            bold=True,
            font_size=dp(14),
        )
        send_btn.bind(on_press=self.send_text)

        input_bar.add_widget(self.text_input)
        input_bar.add_widget(send_btn)
        root.add_widget(input_bar)

        # Boton de voz
        self.voice_btn = Button(
            text="Mantener para hablar",
            size_hint_y=None,
            height=dp(56),
            background_color=get_color_from_hex("#313244"),
            color=get_color_from_hex("#cdd6f4"),
            font_size=dp(15),
        )
        self.voice_btn.bind(on_press=self.start_listening)
        self.voice_btn.bind(on_release=self.stop_listening)
        root.add_widget(self.voice_btn)

        # Verificar conexion al servidor
        Clock.schedule_once(self.check_connection, 1)
        # Saludo inicial
        Clock.schedule_once(self.initial_greeting, 2)

        return root

    def check_connection(self, dt):
        def _check():
            try:
                r = requests.get(f"{SERVER_URL}/health", timeout=5)
                if r.status_code == 200:
                    Clock.schedule_once(lambda dt: self.set_status("Conectada", "#a6e3a1"), 0)
                else:
                    Clock.schedule_once(lambda dt: self.set_status("Error de servidor", "#f38ba8"), 0)
            except Exception:
                Clock.schedule_once(lambda dt: self.set_status("Sin conexion", "#f38ba8"), 0)
        threading.Thread(target=_check, daemon=True).start()

    def set_status(self, text: str, color: str):
        self.status_lbl.text = text
        self.status_lbl.color = get_color_from_hex(color)

    def initial_greeting(self, dt):
        self.add_message("Sistema activo. Estoy lista.", is_user=False)

    def add_message(self, text: str, is_user: bool):
        bubble = MessageBubble(text=text, is_user=is_user)
        self.chat_box.add_widget(bubble)
        Clock.schedule_once(lambda dt: self.scroll_to_bottom(), 0.1)

    def scroll_to_bottom(self):
        self.scroll.scroll_y = 0

    def send_text(self, *args):
        text = self.text_input.text.strip()
        if not text:
            return
        self.text_input.text = ""
        self.add_message(text, is_user=True)
        threading.Thread(target=self._send_to_server, args=(text,), daemon=True).start()

    def _send_to_server(self, text: str):
        try:
            r = requests.post(
                f"{SERVER_URL}/chat",
                json={"text": text},
                timeout=30,
            )
            if r.status_code == 200:
                response = r.json()["response"]
            else:
                response = f"Error del servidor: {r.status_code}"
        except requests.exceptions.ConnectionError:
            response = "Sin conexion al servidor Cortana."
        except Exception as e:
            response = f"Error: {e}"

        Clock.schedule_once(lambda dt: self.add_message(response, is_user=False), 0)

    def start_listening(self, *args):
        self.voice_btn.text = "Escuchando..."
        self.voice_btn.background_color = get_color_from_hex("#f38ba8")
        self.listening = True
        threading.Thread(target=self._record_voice, daemon=True).start()

    def stop_listening(self, *args):
        self.listening = False
        self.voice_btn.text = "Mantener para hablar"
        self.voice_btn.background_color = get_color_from_hex("#313244")

    def _record_voice(self):
        """Graba voz y la envia al servidor."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=20)
            text = recognizer.recognize_google(audio, language="es-ES")
            Clock.schedule_once(lambda dt: self.add_message(text, is_user=True), 0)
            self._send_to_server(text)
        except Exception as e:
            Clock.schedule_once(
                lambda dt: self.add_message(f"No te escuche bien. Intenta de nuevo.", is_user=False), 0
            )


if __name__ == "__main__":
    CortanaApp().run()
