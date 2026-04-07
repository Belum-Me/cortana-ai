from tools.search import web_search, format_results
from tools.weather import get_weather_detailed
from tools.email_tool import send_email
from tools.datetime_tool import get_current_datetime
from tools.calculator import calculate
from tools.notes import save_note, get_note, list_notes
from tools.telegram_bot import send_message_sync as telegram_send
from voice.ambient import transcribe_ambient, get_ambient_level

# Definicion de herramientas para Claude tool-use
TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Busca informacion actualizada en internet. Usala cuando necesites datos recientes, noticias, o informacion que pueda haber cambiado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "La busqueda a realizar"},
                "max_results": {"type": "integer", "description": "Numero de resultados (default 5)", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": "Obtiene el clima actual de cualquier ciudad del mundo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Nombre de la ciudad"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_email",
        "description": "Envia un correo electronico en nombre del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Direccion de email del destinatario"},
                "subject": {"type": "string", "description": "Asunto del correo"},
                "body": {"type": "string", "description": "Cuerpo del correo"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "get_datetime",
        "description": "Obtiene la fecha y hora actual del sistema.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "calculate",
        "description": "Evalua expresiones matematicas de forma segura.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "La expresion matematica a calcular"}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "save_note",
        "description": "Guarda una nota o informacion importante en la memoria persistente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Nombre identificador de la nota"},
                "content": {"type": "string", "description": "Contenido de la nota"}
            },
            "required": ["key", "content"]
        }
    },
    {
        "name": "get_note",
        "description": "Recupera una nota guardada previamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Nombre de la nota a recuperar"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "list_notes",
        "description": "Lista todas las notas guardadas en memoria.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "send_telegram",
        "description": "Envia un mensaje al usuario en su celular via Telegram. Usalo para notificaciones proactivas o alertas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "El mensaje a enviar al celular del usuario"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "listen_environment",
        "description": "Escucha el entorno por el microfono durante unos segundos y transcribe lo que oye.",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration": {"type": "integer", "description": "Segundos de grabacion (default 10)", "default": 10}
            }
        }
    },
    {
        "name": "get_ambient_level",
        "description": "Mide el nivel de ruido ambiental actual (silencioso, moderado, ruidoso).",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]


def execute_tool(name: str, inputs: dict) -> str:
    """Ejecuta una herramienta por nombre y retorna el resultado."""
    try:
        if name == "web_search":
            results = web_search(inputs["query"], inputs.get("max_results", 5))
            return format_results(results)
        elif name == "get_weather":
            return get_weather_detailed(inputs["city"])
        elif name == "send_email":
            return send_email(inputs["to"], inputs["subject"], inputs["body"])
        elif name == "get_datetime":
            return get_current_datetime()
        elif name == "calculate":
            return calculate(inputs["expression"])
        elif name == "save_note":
            return save_note(inputs["key"], inputs["content"])
        elif name == "get_note":
            return get_note(inputs["key"])
        elif name == "list_notes":
            return list_notes()
        elif name == "send_telegram":
            telegram_send(inputs["message"])
            return "Mensaje enviado al celular via Telegram."
        elif name == "listen_environment":
            return transcribe_ambient(inputs.get("duration", 10))
        elif name == "get_ambient_level":
            result = get_ambient_level()
            return f"Nivel de ruido: {result['level']} ({result['db']} dB)"
        else:
            return f"Herramienta desconocida: {name}"
    except Exception as e:
        return f"Error ejecutando {name}: {e}"
