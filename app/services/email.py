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


def send_welcome_email(
    recipient_email: str,
    recipient_name: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = f"Welcome to {settings.app_name}"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email

    message.set_content(
        f"""Hi {recipient_name},

Welcome to {settings.app_name}! 🎉

Your account has been created successfully.

You can now:
- Browse available events
- Book tickets
- Order food
- Manage your bookings
- Receive important notifications

We're happy to have you with us.

Thanks,
{settings.app_name}
"""
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def send_event_notification_email(
    recipient_email: str,
    recipient_name: str,
    action: str,
    event_name: str,
    venue: str,
    starts_at: str,
    previous_details: str = "",
) -> None:
    message = EmailMessage()
    message["Subject"] = f"Event {action}: {event_name}"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email

    message.set_content(
        f"""Hi {recipient_name},

This is an update about your event.

Action: {action}
Event: {event_name}
Venue: {venue}
Starts at: {starts_at}
{previous_details}
If you did not expect this change, please review your TicketFlow account.

Thanks,
{settings.app_name}
"""
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
