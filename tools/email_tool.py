import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SMTP = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))


def send_email(to: str, subject: str, body: str) -> str:
    """Envia un correo electronico."""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        return "Error: No hay credenciales de email configuradas en .env (EMAIL_USER, EMAIL_PASSWORD)."

    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(EMAIL_SMTP, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)

        return f"Correo enviado exitosamente a {to}."
    except Exception as e:
        return f"Error al enviar correo: {e}"
