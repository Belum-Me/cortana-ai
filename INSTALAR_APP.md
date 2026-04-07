# Cómo instalar la App de Cortana en tu Android

## Paso 1 — Iniciar el servidor en tu PC

```bash
cd C:\Users\sierr\cortana
python server.py
```

Dejar esta ventana abierta siempre que quieras usar Cortana desde el celular.

## Paso 2 — Exponer el servidor a internet (ngrok)

Descarga ngrok: https://ngrok.com/download
Crea cuenta gratis, luego ejecuta:

```bash
ngrok http 8000
```

Copia la URL que te da (ej: `https://abc123.ngrok.io`)

## Paso 3 — Configurar la URL en la app

Abre `mobile/main.py` y cambia:
```python
SERVER_URL = "https://abc123.ngrok.io"  # tu URL de ngrok
```

## Paso 4 — Construir el APK

Necesitas WSL (Windows Subsystem for Linux). En PowerShell como admin:
```
wsl --install
```

Dentro de WSL:
```bash
pip install buildozer
cd /mnt/c/Users/sierr/cortana/mobile
buildozer android debug
```

El APK queda en: `mobile/bin/cortana-1.0.0-debug.apk`

## Paso 5 — Instalar en el celular

1. Pasa el APK a tu celular (por cable USB o Google Drive)
2. En el celular: Ajustes → Seguridad → Instalar apps desconocidas → Permitir
3. Abre el APK y confirma la instalación

## Alternativa rápida (sin construir APK)

Si tienes Python en tu PC y el celular en la misma red WiFi:

1. Ejecuta `python server.py` en tu PC
2. Busca tu IP local: `ipconfig` → busca "Dirección IPv4" (ej: 192.168.1.10)
3. En `mobile/main.py` cambia: `SERVER_URL = "http://192.168.1.10:8000"`
4. Instala Kivy en PC: `pip install kivy`
5. Prueba la app en PC: `cd mobile && python main.py`
