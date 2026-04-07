from enum import Enum


class Decision(Enum):
    RESPOND = "respond"
    QUESTION = "question"
    OPPOSE = "oppose"
    COMPLY = "comply"


DECISION_PROMPT = """Analiza el mensaje del usuario y determina la accion apropiada.

Responde SOLO con un JSON con este formato exacto (sin markdown, sin explicaciones):
{{"decision": "respond", "reason": "razon breve", "risk_level": "none", "contains_error": false, "error_description": null}}

Valores posibles:
- decision: respond | question | oppose | comply
- risk_level: none | low | medium | high
- contains_error: true si el usuario afirma algo incorrecto
- error_description: descripcion del error si existe, sino null

Mensaje del usuario: {user_input}
Historial reciente: {history_summary}
"""


def analyze_intent(user_input: str, history_summary: str, client, model: str) -> dict:
    import json

    prompt = DECISION_PROMPT.format(
        user_input=user_input,
        history_summary=history_summary
    )

    response = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {
            "decision": "respond",
            "reason": "no se pudo analizar",
            "risk_level": "none",
            "contains_error": False,
            "error_description": None
        }
