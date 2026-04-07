from core.memory import init_db
from core.llm import chat


def main():
    init_db()
    print("Cortana iniciada. Escribe 'salir' para terminar.\n")

    while True:
        try:
            user_input = input("Tú: ").strip()
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


if __name__ == "__main__":
    main()
