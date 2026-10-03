from email.message import EmailMessage
import smtplib

from app.core.config import settings


def send_event_created_email(
    recipient_email: str,
    recipient_name: str,
    event_name: str,
    venue: str,
    starts_at: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = f"Event Created: {event_name}"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email

    message.set_content(
        f"""Hi {recipient_name},

Your event has been created successfully.

Event: {event_name}
Venue: {venue}
Starts at: {starts_at}

Thanks,
{settings.app_name}
"""
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
