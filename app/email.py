from pathlib import Path
import logging

from pydantic import NameEmail
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors

from app.config import settings


logger = logging.getLogger(__name__)


def _build_mail_client() -> FastMail | None:
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        return None

    conf = ConnectionConfig(
        MAIL_USERNAME=settings.smtp_username,
        MAIL_PASSWORD=settings.smtp_password,
        MAIL_FROM=settings.smtp_username,
        MAIL_SERVER=settings.smtp_host,
        MAIL_PORT=settings.smtp_port,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
        TEMPLATE_FOLDER=Path("app/templates"),
    )
    return FastMail(conf)


async def send_reset_password_email(to_email: str, token: str) -> None:
    fm = _build_mail_client()
    if fm is None:
        logger.warning("SMTP is not configured; skipping reset password email for %s", to_email)
        return

    reset_link = (
        f"{settings.backend_url}/auth/reset-password/confirm?token={token}"
    )
    reset_template = Path("app/templates/reset_password_email.html").read_text(
        encoding="utf-8"
    )

    html_body = reset_template.replace("{{RESET_LINK}}", reset_link)

    text_body = f"""Reset Your Password

We received a request to reset your GameLog password.

Use the following link to reset your password:

{reset_link}

If the button in the email does not work, copy and paste the link into your browser.

If you did not request a password reset, simply ignore this email. Your password will remain unchanged.

GameLog
"""

    message = MessageSchema(
        subject="Reset your password",
        recipients=[NameEmail(name="",email=to_email)],
        body=html_body,
        subtype=MessageType.html,
        alternative_body=text_body,  # Plain-text fallback
    )

    try:
        await fm.send_message(message)
    except ConnectionErrors:
        logger.exception("SMTP connection failed while sending reset password email to %s", to_email)
    except Exception:
        logger.exception("Unexpected error while sending reset password email to %s", to_email)

async def send_verification_email(to_email: str, code: str) -> None:
    fm = _build_mail_client()
    if fm is None:
        logger.warning("SMTP is not configured; skipping verification email for %s", to_email)
        return

    reset_template = Path("app/templates/verification_email.html").read_text(encoding="utf-8")

    html_body = reset_template.replace("{{CODE}}", code)

    text_body = f"""Verify Your Email

    Welcome to GameLog!

    Use the following One-Time Password (OTP) to verify your email address:

    {code}

    This code expires in 10 minutes.

    If you did not create a GameLog account, you can safely ignore this email.

    GameLog
    """

    message = MessageSchema(
        subject="Verify your email",
        recipients=[NameEmail(name="", email=to_email)],
        body=html_body,
        subtype=MessageType.html,
        alternative_body=text_body,  # Plain-text fallback
    )

    try:
        await fm.send_message(message)
    except ConnectionErrors:
        logger.exception("SMTP connection failed while sending verification email to %s", to_email)
    except Exception:
        logger.exception("Unexpected error while sending verification email to %s", to_email)
