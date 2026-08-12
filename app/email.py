import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)


def _build_gmail_service():
    if not all([
        settings.gmail_client_id,
        settings.gmail_client_secret,
        settings.gmail_refresh_token,
    ]):
        return None

    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def _create_message(to_email: str, subject: str, html_body: str, text_body: str) -> dict:
    message = MIMEMultipart("alternative")
    message["to"] = to_email
    message["from"] = settings.gmail_sender_email
    message["subject"] = subject

    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


async def send_reset_password_email(to_email: str, token: str) -> None:
    service = _build_gmail_service()
    if service is None:
        logger.warning("Gmail API is not configured; skipping reset password email for %s", to_email)
        return

    reset_link = f"{settings.backend_url}/auth/reset-password/confirm?token={token}"
    reset_template = Path("app/templates/reset_password_email.html").read_text(encoding="utf-8")
    html_body = reset_template.replace("{{RESET_LINK}}", reset_link)

    text_body = f"""Reset Your Password

We received a request to reset your GameLog password.

Use the following link to reset your password:

{reset_link}

If the button in the email does not work, copy and paste the link into your browser.

If you did not request a password reset, simply ignore this email. Your password will remain unchanged.

GameLog
"""

    body = _create_message(to_email, "Reset your password", html_body, text_body)

    try:
        service.users().messages().send(userId="me", body=body).execute()
    except HttpError:
        logger.exception("Gmail API call failed while sending reset password email to %s", to_email)
    except Exception:
        logger.exception("Unexpected error while sending reset password email to %s", to_email)


async def send_verification_email(to_email: str, code: str) -> None:
    service = _build_gmail_service()
    if service is None:
        logger.warning("Gmail API is not configured; skipping verification email for %s", to_email)
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

    body = _create_message(to_email, "Verify your email", html_body, text_body)

    try:
        service.users().messages().send(userId="me", body=body).execute()
    except HttpError:
        logger.exception("Gmail API call failed while sending verification email to %s", to_email)
    except Exception:
        logger.exception("Unexpected error while sending verification email to %s", to_email)
