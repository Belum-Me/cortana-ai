import httpx


def get_weather(city: str) -> str:
    """Obtiene el clima actual de una ciudad usando wttr.in."""
    try:
        url = f"https://wttr.in/{city}?format=3&lang=es"
        response = httpx.get(url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        return f"No se pudo obtener el clima para '{city}'."
    except Exception as e:
        return f"Error al consultar el clima: {e}"


def get_weather_detailed(city: str) -> str:
    """Obtiene clima detallado en formato JSON."""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        response = httpx.get(url, timeout=10)
        data = response.json()
        current = data["current_condition"][0]
        return (
            f"Ciudad: {city}\n"
            f"Temperatura: {current['temp_C']}°C (sensacion: {current['FeelsLikeC']}°C)\n"
            f"Condicion: {current['weatherDesc'][0]['value']}\n"
            f"Humedad: {current['humidity']}%\n"
            f"Viento: {current['windspeedKmph']} km/h"
        )
    except Exception as e:
        return get_weather(city)
