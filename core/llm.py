import re
import random
import anthropic
from config import ANTHROPIC_API_KEY, MODEL, MAX_TOKENS
from core.identity import get_system_prompt, get_voice_prompt
from core.memory import get_recent_history, save_message, log_override
from core.decision import analyze_intent
from verification.fact_check import verify_claim
from tools.registry import TOOL_DEFINITIONS, execute_tool

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Frases de transición por idioma
_FILLERS = {
    "es": ["Mmh...", "Déjame ver...", "Un momento...", "Claro...", "A ver..."],
    "en": ["Hmm...", "Let me check...", "Sure...", "One sec...", "Got it..."],
}

# Patrón para cortar en límites de oración (. ? ! ;)
_SENTENCE_END = re.compile(r'(?<=[.?!;])\s+')


def pick_filler(lang: str = "es") -> str:
    options = _FILLERS.get(lang, _FILLERS["es"])
    return random.choice(options)


def _history_summary(history: list[dict]) -> str:
    if not history:
        return "Sin historial previo."
    recent = history[-4:]
    return " | ".join(f"{m['role']}: {m['content'][:80]}" for m in recent)


def _handle_tool_calls(response, messages: list[dict]) -> str:
    """Procesa tool calls de Claude y retorna la respuesta final (modo no-streaming)."""
    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=get_system_prompt(),
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def _stream_chunks(messages: list[dict], system: str, on_chunk):
    """
    Hace streaming de la respuesta de Claude. Llama on_chunk(texto) por cada
    oración completa. Maneja tool calls de forma transparente.
    Retorna el texto completo acumulado.
    """
    full_text = ""
    buffer = ""

    def flush_buffer(buf: str) -> str:
        """Corta buf en oraciones, emite las completas, retorna el sobrante."""
        nonlocal full_text
        parts = _SENTENCE_END.split(buf)
        if len(parts) <= 1:
            return buf
        # Las primeras N-1 partes son oraciones completas
        for part in parts[:-1]:
            chunk = part.strip()
            if chunk:
                full_text += chunk + " "
                on_chunk(chunk)
        return parts[-1]  # sobrante sin punto final aún

    with client.messages.stream(
        model=MODEL,
        max_tokens=512,
        system=system,
        tools=TOOL_DEFINITIONS,
        messages=messages,
    ) as stream:
        for token in stream.text_stream:
            buffer += token
            buffer = flush_buffer(buffer)

        # Vaciar lo que quede en el buffer
        remainder = buffer.strip()
        if remainder:
            full_text += remainder
            on_chunk(remainder)

        final = stream.get_final_message()

    # Si el modelo usó herramientas, ejecutarlas y volver a stremear la respuesta
    if final.stop_reason == "tool_use":
        tool_results = []
        for block in final.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "assistant", "content": final.content})
        messages.append({"role": "user", "content": tool_results})
        # Streaming de la respuesta post-herramienta
        full_text += _stream_chunks(messages, system, on_chunk)

    return full_text


def chat_fast_stream(user_input: str, lang: str = "es", on_chunk=None) -> str:
    """
    Versión streaming para voz. Llama on_chunk(texto) por cada oración lista.
    Retorna el texto completo para guardarlo en memoria.
    Si on_chunk es None, retorna la respuesta completa como chat_fast().
    """
    save_message("user", user_input)
    history = get_recent_history()
    messages = list(history)

    if on_chunk is None:
        # Fallback no-streaming
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=get_voice_prompt(),
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        reply = _handle_tool_calls(response, messages)
        save_message("assistant", reply)
        return reply

    full_reply = _stream_chunks(messages, get_voice_prompt(), on_chunk)
    save_message("assistant", full_reply)
    return full_reply


def chat_fast(user_input: str) -> str:
    """Versión sin streaming (compatible con send_text del UI)."""
    return chat_fast_stream(user_input, on_chunk=None)


def chat(user_input: str) -> str:
    save_message("user", user_input)
    history = get_recent_history()
    summary = _history_summary(history)

    analysis = analyze_intent(user_input, summary, client, MODEL)

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
                user_decision=user_input[:100],
            )

    system = get_system_prompt() + opposition_note

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        tools=TOOL_DEFINITIONS,
        messages=list(history),
    )

    reply = _handle_tool_calls(response, list(history))
    save_message("assistant", reply)
    return reply
