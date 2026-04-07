import anthropic
from config import ANTHROPIC_API_KEY, MODEL, MAX_TOKENS
from core.identity import get_system_prompt
from core.memory import get_recent_history, save_message, log_override
from core.decision import analyze_intent
from verification.fact_check import verify_claim

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

OPPOSITION_PREFIX = "[CORTANA SE OPONE] "
COMPLY_PREFIX = "[ACATANDO DECISION] "


def _history_summary(history: list[dict]) -> str:
    if not history:
        return "Sin historial previo."
    recent = history[-4:]
    return " | ".join(f"{m['role']}: {m['content'][:80]}" for m in recent)


def chat(user_input: str) -> str:
    save_message("user", user_input)
    history = get_recent_history()
    summary = _history_summary(history)

    # Analizar intención y detectar errores
    analysis = analyze_intent(user_input, summary, client, MODEL)

    # Si detecta error factual, verificar y preparar oposición
    opposition_note = ""
    if analysis.get("contains_error") and analysis.get("error_description"):
        verification = verify_claim(analysis["error_description"], client, MODEL)
        if verification.get("is_valid") is False and verification.get("confidence") in ("high", "medium"):
            correction = verification.get("correction", "")
            opposition_note = (
                f"\n\n[NOTA INTERNA PARA CORTANA: El usuario parece cometer un error. "
                f"Debes señalarlo con claridad antes de responder. "
                f"Corrección sugerida: {correction}]"
            )
            log_override(
                topic=user_input[:100],
                cortana_position=correction,
                user_decision=user_input[:100]
            )

    # Construir system prompt con nota de oposición si aplica
    system = get_system_prompt() + opposition_note

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=history,
    )

    reply = response.content[0].text
    save_message("assistant", reply)
    return reply
