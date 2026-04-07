from core.memory import save_fact, get_connection


def save_note(key: str, content: str) -> str:
    """Guarda una nota en la memoria persistente."""
    save_fact(key=f"note:{key}", value=content, source="usuario")
    return f"Nota '{key}' guardada."


def get_note(key: str) -> str:
    """Recupera una nota guardada."""
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM facts WHERE key = ?", (f"note:{key}",)
    ).fetchone()
    conn.close()
    if row:
        return f"Nota '{key}': {row[0]}"
    return f"No existe ninguna nota con el nombre '{key}'."


def list_notes() -> str:
    """Lista todas las notas guardadas."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT key, value FROM facts WHERE key LIKE 'note:%'"
    ).fetchall()
    conn.close()
    if not rows:
        return "No hay notas guardadas."
    return "\n".join(f"- {r[0].replace('note:', '')}: {r[1][:60]}..." for r in rows)
