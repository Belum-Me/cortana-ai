from datetime import datetime
import locale


def get_current_datetime() -> str:
    """Retorna fecha y hora actual."""
    now = datetime.now()
    return (
        f"Fecha: {now.strftime('%A %d de %B de %Y')}\n"
        f"Hora: {now.strftime('%H:%M:%S')}\n"
        f"Timestamp: {now.isoformat()}"
    )


def get_date() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def get_time() -> str:
    return datetime.now().strftime("%H:%M:%S")
