"""
Control total del computador para Cortana.
"""

import os
import subprocess
import webbrowser
import pyautogui
import pyperclip
import tempfile
from datetime import datetime

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


# ── Navegador ─────────────────────────────────────────────────────────────────

def open_browser(url_or_query: str) -> str:
    if url_or_query.startswith("http"):
        webbrowser.open(url_or_query)
        return f"Abriendo {url_or_query}"
    else:
        query = url_or_query.replace(" ", "+")
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return f"Buscando en Google: {url_or_query}"


def open_youtube(query: str) -> str:
    q = query.replace(" ", "+")
    webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
    return f"Buscando en YouTube: {query}"


# ── Aplicaciones ──────────────────────────────────────────────────────────────

APP_MAP = {
    "bloc de notas": "notepad",
    "notepad": "notepad",
    "calculadora": "calc",
    "calculator": "calc",
    "explorador": "explorer",
    "explorer": "explorer",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "spotify": "spotify",
    "chrome": "chrome",
    "edge": "msedge",
    "firefox": "firefox",
    "discord": "discord",
    "teams": "teams",
    "zoom": "zoom",
    "cmd": "cmd",
    "terminal": "cmd",
    "task manager": "taskmgr",
    "administrador de tareas": "taskmgr",
    "configuracion": "ms-settings:",
    "settings": "ms-settings:",
}

def open_app(app_name: str) -> str:
    name = app_name.lower().strip()
    cmd = APP_MAP.get(name, name)
    try:
        if cmd.startswith("ms-"):
            os.startfile(cmd)
        else:
            subprocess.Popen(cmd, shell=True)
        return f"Abriendo {app_name}."
    except Exception as e:
        return f"No pude abrir {app_name}: {e}"


# ── Captura ───────────────────────────────────────────────────────────────────

def take_screenshot(save_path: str = None) -> str:
    if not save_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(os.path.expanduser("~"), "Pictures", f"cortana_{ts}.png")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    screenshot = pyautogui.screenshot()
    screenshot.save(save_path)
    return f"Captura guardada en {save_path}"


def take_photo(save_path: str = None) -> str:
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "No encontré webcam disponible."
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "No pude capturar la foto."
        if not save_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(os.path.expanduser("~"), "Pictures", f"cortana_foto_{ts}.jpg")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, frame)
        return f"Foto guardada en {save_path}"
    except Exception as e:
        return f"Error al tomar foto: {e}"


# ── Teclado y mouse ───────────────────────────────────────────────────────────

def type_text(text: str) -> str:
    pyautogui.typewrite(text, interval=0.04)
    return f"Escribí: {text}"


def press_key(key: str) -> str:
    pyautogui.press(key)
    return f"Tecla presionada: {key}"


def hotkey(*keys) -> str:
    pyautogui.hotkey(*keys)
    return f"Atajo ejecutado: {'+'.join(keys)}"


def click_at(x: int, y: int) -> str:
    pyautogui.click(x, y)
    return f"Clic en ({x}, {y})"


def scroll(direction: str = "down", amount: int = 3) -> str:
    clicks = -amount if direction == "down" else amount
    pyautogui.scroll(clicks)
    return f"Scroll {direction} x{amount}"


# ── Portapapeles ──────────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> str:
    pyperclip.copy(text)
    return "Copiado al portapapeles."


def read_clipboard() -> str:
    content = pyperclip.paste()
    return f"Portapapeles: {content}" if content else "El portapapeles está vacío."


# ── Sistema ───────────────────────────────────────────────────────────────────

def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100, None)
        return f"Volumen ajustado a {level}%"
    except Exception:
        # Fallback usando teclas multimedia
        if level == 0:
            pyautogui.press("volumemute")
            return "Volumen silenciado."
        return f"No pude ajustar el volumen a {level}% automáticamente."


def lock_screen() -> str:
    subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
    return "Pantalla bloqueada."


def list_windows() -> str:
    try:
        import pygetwindow as gw
        wins = [w.title for w in gw.getAllWindows() if w.title.strip()]
        return "Ventanas abiertas:\n" + "\n".join(f"- {w}" for w in wins[:15])
    except Exception as e:
        return f"Error: {e}"


def get_system_info() -> str:
    import platform, psutil
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return (
        f"Sistema: {platform.system()} {platform.release()}\n"
        f"CPU: {cpu}%\n"
        f"RAM: {ram.percent}% usada ({ram.used // 1024**3}GB / {ram.total // 1024**3}GB)\n"
        f"Disco: {disk.percent}% usado"
    )


def open_file(path: str) -> str:
    try:
        os.startfile(path)
        return f"Abriendo {path}"
    except Exception as e:
        return f"No pude abrir {path}: {e}"


def create_file(path: str, content: str = "") -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Archivo creado: {path}"
    except Exception as e:
        return f"Error: {e}"
