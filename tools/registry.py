from tools.search import web_search, format_results
from tools.weather import get_weather_detailed
from tools.email_tool import send_email
from tools.datetime_tool import get_current_datetime
from tools.calculator import calculate
from tools.notes import save_note, get_note, list_notes
from tools.telegram_bot import send_message_sync as telegram_send
from voice.ambient import transcribe_ambient, get_ambient_level
from tools.computer import (
    open_browser, open_youtube, open_app, take_screenshot, take_photo,
    type_text, press_key, hotkey, click_at, scroll,
    copy_to_clipboard, read_clipboard, lock_screen,
    list_windows, get_system_info, open_file, create_file
)

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
    },
    {
        "name": "open_browser",
        "description": "Abre el navegador con una URL o hace una busqueda en Google.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url_or_query": {"type": "string", "description": "URL completa o termino de busqueda"}
            },
            "required": ["url_or_query"]
        }
    },
    {
        "name": "open_youtube",
        "description": "Busca y abre un video en YouTube.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termino a buscar en YouTube"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "open_app",
        "description": "Abre una aplicacion del sistema como Chrome, Spotify, calculadora, bloc de notas, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Nombre de la aplicacion a abrir"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Toma una captura de pantalla del computador.",
        "input_schema": {
            "type": "object",
            "properties": {
                "save_path": {"type": "string", "description": "Ruta donde guardar (opcional)"}
            }
        }
    },
    {
        "name": "take_photo",
        "description": "Toma una foto con la webcam del computador.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "type_text",
        "description": "Escribe texto como si fuera el teclado del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto a escribir"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "press_key",
        "description": "Presiona una tecla especial (enter, escape, tab, f5, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Nombre de la tecla"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "hotkey",
        "description": "Ejecuta un atajo de teclado como ctrl+c, alt+tab, win+d, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keys": {"type": "array", "items": {"type": "string"}, "description": "Lista de teclas del atajo"}
            },
            "required": ["keys"]
        }
    },
    {
        "name": "scroll_page",
        "description": "Hace scroll en la pagina actual hacia arriba o abajo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"]},
                "amount": {"type": "integer", "description": "Cantidad de scroll (default 3)"}
            },
            "required": ["direction"]
        }
    },
    {
        "name": "read_clipboard",
        "description": "Lee el contenido actual del portapapeles.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "copy_to_clipboard",
        "description": "Copia texto al portapapeles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto a copiar"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "lock_screen",
        "description": "Bloquea la pantalla del computador.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "list_windows",
        "description": "Lista las ventanas y aplicaciones abiertas actualmente.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_system_info",
        "description": "Obtiene informacion del sistema: CPU, RAM, disco.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "open_file",
        "description": "Abre un archivo con su aplicacion predeterminada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta completa del archivo"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "create_file",
        "description": "Crea un archivo con contenido en la ruta indicada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Ruta del archivo a crear"},
                "content": {"type": "string", "description": "Contenido del archivo"}
            },
            "required": ["path"]
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
        elif name == "open_browser":
            return open_browser(inputs["url_or_query"])
        elif name == "open_youtube":
            return open_youtube(inputs["query"])
        elif name == "open_app":
            return open_app(inputs["app_name"])
        elif name == "take_screenshot":
            return take_screenshot(inputs.get("save_path"))
        elif name == "take_photo":
            return take_photo()
        elif name == "type_text":
            return type_text(inputs["text"])
        elif name == "press_key":
            return press_key(inputs["key"])
        elif name == "hotkey":
            return hotkey(*inputs["keys"])
        elif name == "scroll_page":
            return scroll(inputs["direction"], inputs.get("amount", 3))
        elif name == "read_clipboard":
            return read_clipboard()
        elif name == "copy_to_clipboard":
            return copy_to_clipboard(inputs["text"])
        elif name == "lock_screen":
            return lock_screen()
        elif name == "list_windows":
            return list_windows()
        elif name == "get_system_info":
            return get_system_info()
        elif name == "open_file":
            return open_file(inputs["path"])
        elif name == "create_file":
            return create_file(inputs["path"], inputs.get("content", ""))
        else:
            return f"Herramienta desconocida: {name}"
    except Exception as e:
        return f"Error ejecutando {name}: {e}"
