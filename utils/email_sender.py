import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_HOST     = os.getenv("EMAIL_HOST", "smtp.gmail.com")
_PORT     = int(os.getenv("EMAIL_PORT", "587"))
_USER     = os.getenv("EMAIL_USER", "")
_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
_FROM     = os.getenv("EMAIL_FROM", _USER)


def send_email(destinatario: str, asunto: str, cuerpo_html: str) -> bool:
    """
    Envía un correo HTML. Devuelve True si fue exitoso, False si falló.
    Requiere EMAIL_USER y EMAIL_PASSWORD en .env.
    """
    if not _USER or not _PASSWORD:
        logger.error("Email no configurado: faltan EMAIL_USER o EMAIL_PASSWORD en .env")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"]    = _FROM
    msg["To"]      = destinatario
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        # Puerto 465 → SSL directo; cualquier otro → STARTTLS
        if _PORT == 465:
            with smtplib.SMTP_SSL(_HOST, _PORT, timeout=10) as smtp:
                smtp.login(_USER, _PASSWORD)
                smtp.sendmail(_USER, destinatario, msg.as_string())
        else:
            with smtplib.SMTP(_HOST, _PORT, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(_USER, _PASSWORD)
                smtp.sendmail(_USER, destinatario, msg.as_string())
        logger.info("Email enviado a %s | asunto: %s", destinatario, asunto)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Email: autenticación fallida para %s — verifica EMAIL_PASSWORD en .env", _USER)
    except smtplib.SMTPRecipientsRefused:
        logger.error("Email: destinatario rechazado: %s", destinatario)
    except smtplib.SMTPException as e:
        logger.error("Email: error SMTP al enviar a %s — %s", destinatario, e)
    except OSError as e:
        logger.error("Email: no se pudo conectar a %s:%s — %s", _HOST, _PORT, e)
    return False
