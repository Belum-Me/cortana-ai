"""
Cortana - IA Personal Avanzada

Modos de ejecucion:
  python main.py            → Modo texto (terminal)
  python main.py --voz      → Modo voz (microfono + altavoz)
  python main.py --bot      → Modo Telegram (control desde celular)
  python main.py --always   → Modo siempre activa (wake word "Cortana")
"""

import sys
from core.memory import init_db
from core.llm import chat


def run_text_mode():
    print("Cortana [texto]. Escribe 'salir' para terminar.\n")
    while True:
        try:
            user_input = input("Tu: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCortana: Hasta luego.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            print("Cortana: Hasta luego.")
            break
        response = chat(user_input)
        print(f"\nCortana: {response}\n")


def run_voice_mode():
    from voice.tts import speak
    from voice.stt import listen_once

    print("Cortana [voz]. Habla cuando veas 'Cortana escuchando...'")
    print("Presiona Ctrl+C para salir.\n")
    speak("Sistema iniciado. Estoy lista.")

    while True:
        try:
            user_input = listen_once()
            if user_input is None:
                continue
            print(f"Tu: {user_input}")
            if any(w in user_input.lower() for w in ("salir", "apagarse", "detente")):
                speak("Hasta luego.")
                break
            response = chat(user_input)
            print(f"Cortana: {response}\n")
            speak(response)
        except KeyboardInterrupt:
            speak("Hasta luego.")
            break


def run_always_on_mode():
    """Wake word mode: Cortana escucha siempre y responde cuando la llaman."""
    from voice.tts import speak
    from voice.stt import listen_once
    from voice.wake_word import listen_for_wake_word
    import threading

    print("Cortana [siempre activa]. Di 'Cortana' para activar. Ctrl+C para salir.")
    speak("Modo siempre activa. Estoy escuchando.")

    def on_wake():
        speak("Dime.")
        user_input = listen_once()
        if user_input:
            print(f"Tu: {user_input}")
            response = chat(user_input)
            print(f"Cortana: {response}\n")
            speak(response)

    stop_event = threading.Event()
    try:
        from voice.wake_word import run_always_on
        run_always_on(on_wake, stop_event)
    except KeyboardInterrupt:
        stop_event.set()
        speak("Hasta luego.")


def run_bot_mode():
    """Modo Telegram: Cortana es controlable desde el celular."""
    from tools.telegram_bot import run_bot
    print("Cortana [Telegram]. Escribe a tu bot desde el celular.")
    print("Presiona Ctrl+C para detener.\n")
    run_bot()


def main():
    init_db()
    args = sys.argv[1:]

    if "--bot" in args or "-b" in args:
        run_bot_mode()
    elif "--always" in args or "-a" in args:
        run_always_on_mode()
    elif "--voz" in args or "-v" in args:
        run_voice_mode()
    else:
        run_text_mode()


if __name__ == "__main__":
    main()
