import smtplib
from email.message import EmailMessage

from app.config import settings


def send_reset_password_email(to_email: str, token: str) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError("SMTP is not configured")

    reset_link = f"{settings.frontend_url}/reset-password?token={token}"

    message = EmailMessage()
    message["Subject"] = "Reset your password"
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(
        f"Use this link to reset your password:\n\n{reset_link}\n\nIf you did not request this, ignore this email."
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
