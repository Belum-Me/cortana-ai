import sys
from core.memory import init_db
from core.llm import chat


def run_text_mode():
    """Modo texto: interaccion por teclado."""
    print("Cortana [modo texto]. Escribe 'salir' para terminar.\n")
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
    """Modo voz: interaccion por microfono y altavoz."""
    from voice.tts import speak
    from voice.stt import listen_once

    print("Cortana [modo voz]. Habla cuando veas 'Cortana escuchando...'")
    print("Presiona Ctrl+C para salir.\n")

    speak("Sistema iniciado. Estoy lista.", blocking=True)

    while True:
        try:
            user_input = listen_once()

            if user_input is None:
                continue

            print(f"Tu: {user_input}")

            if any(w in user_input.lower() for w in ("salir", "apagarse", "detente", "para")):
                speak("Hasta luego.")
                break

            response = chat(user_input)
            print(f"Cortana: {response}\n")
            speak(response)

        except KeyboardInterrupt:
            print("\nCortana: Hasta luego.")
            speak("Hasta luego.")
            break


def main():
    init_db()

    # Modo por argumento: python main.py --voz
    if "--voz" in sys.argv or "-v" in sys.argv:
        run_voice_mode()
    else:
        run_text_mode()


if __name__ == "__main__":
    main()
