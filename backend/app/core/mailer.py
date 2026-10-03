"""
Transactional email (password reset) over plain SMTP — works with any provider, including
a Gmail account with an app password (free, ~500 mails/day). Optional: with SMTP_HOST
unset, features that need email say so instead of pretending to send.
"""
import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import settings


def mail_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def _send(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_mail(to: str, subject: str, body: str) -> None:
    await asyncio.to_thread(_send, to, subject, body)
