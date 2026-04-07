"""
Inicia el servidor de Cortana.
Ejecutar: python server.py
"""
import uvicorn

if __name__ == "__main__":
    print("Iniciando servidor Cortana en http://0.0.0.0:8000")
    print("Presiona Ctrl+C para detener.\n")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
