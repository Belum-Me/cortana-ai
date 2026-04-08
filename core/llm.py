import anthropic
from config import ANTHROPIC_API_KEY, MODEL, MAX_TOKENS
from core.identity import get_system_prompt
from core.memory import get_recent_history, save_message, log_override
from core.decision import analyze_intent
from verification.fact_check import verify_claim
from tools.registry import TOOL_DEFINITIONS, execute_tool

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _history_summary(history: list[dict]) -> str:
    if not history:
        return "Sin historial previo."
    recent = history[-4:]
    return " | ".join(f"{m['role']}: {m['content'][:80]}" for m in recent)


def _handle_tool_calls(response, messages: list[dict]) -> str:
    """Procesa tool calls de Claude y retorna la respuesta final."""
    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

        # Agregar respuesta del asistente y resultados de herramientas
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # Continuar la conversacion con los resultados
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=get_system_prompt(),
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

    # Extraer texto final
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def chat_fast(user_input: str) -> str:
    """Version rapida para voz: sin analisis previo, respuesta directa."""
    save_message("user", user_input)
    history = get_recent_history()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=get_system_prompt(),
        tools=TOOL_DEFINITIONS,
        messages=history,
    )

    reply = _handle_tool_calls(response, list(history))
    save_message("assistant", reply)
    return reply


def chat(user_input: str) -> str:
    save_message("user", user_input)
    history = get_recent_history()
    summary = _history_summary(history)

    # Analizar intencion y detectar errores
    analysis = analyze_intent(user_input, summary, client, MODEL)

    # Si detecta error factual, agregar nota al system prompt
    opposition_note = ""
    if analysis.get("contains_error") and analysis.get("error_description"):
        verification = verify_claim(analysis["error_description"], client, MODEL)
        if verification.get("is_valid") is False and verification.get("confidence") in ("high", "medium"):
            correction = verification.get("correction", "")
            opposition_note = (
                f"\n\n[NOTA: El usuario comete un error. "
                f"Senalalo antes de responder. Correccion: {correction}]"
            )
            log_override(
                topic=user_input[:100],
                cortana_position=correction,
                user_decision=user_input[:100]
            )

    system = get_system_prompt() + opposition_note

    # Llamada principal con herramientas
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        tools=TOOL_DEFINITIONS,
        messages=history,
    )

    reply = _handle_tool_calls(response, list(history))
    save_message("assistant", reply)
    return reply
