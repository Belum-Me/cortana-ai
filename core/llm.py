import anthropic
from config import ANTHROPIC_API_KEY, MODEL, MAX_TOKENS
from core.identity import get_system_prompt
from core.memory import get_recent_history, save_message

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def chat(user_input: str) -> str:
    save_message("user", user_input)

    history = get_recent_history()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=get_system_prompt(),
        messages=history,
    )

    reply = response.content[0].text
    save_message("assistant", reply)
    return reply
