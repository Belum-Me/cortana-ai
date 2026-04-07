VERIFY_PROMPT = """Eres un motor de verificación riguroso. Analiza la siguiente afirmación y determina su validez.

Afirmación: {claim}

Responde SOLO con un JSON:
{{
  "is_valid": true|false|null,
  "confidence": "high|medium|low",
  "explanation": "explicación concisa",
  "correction": "corrección si es falsa, sino null"
}}

- is_valid: true si es correcta, false si es incorrecta, null si no puedes determinar con certeza
- confidence: qué tan seguro estás de tu evaluación
- correction: solo si is_valid es false
"""


def verify_claim(claim: str, client, model: str) -> dict:
    import json

    response = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": VERIFY_PROMPT.format(claim=claim)}]
    )

    text = response.content[0].text.strip()
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {
            "is_valid": None,
            "confidence": "low",
            "explanation": "No se pudo verificar",
            "correction": None
        }
