from email.message import EmailMessage
import logging
import smtplib

from app.core.config import settings


logger = logging.getLogger(__name__)


def _send_email(
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email
    message.set_content(body)

    try:
        logger.info(
            "Sending email: subject=%r recipient=%s smtp=%s:%s",
            subject,
            recipient_email,
            settings.smtp_host,
            settings.smtp_port,
        )

        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout,
        ) as server:
            server.ehlo()

            if settings.smtp_starttls:
                server.starttls()
                server.ehlo()

            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)

        logger.info("Email sent successfully: subject=%r recipient=%s", subject, recipient_email)

    except Exception:
        logger.exception(
            "Email delivery failed: subject=%r recipient=%s smtp=%s:%s",
            subject,
            recipient_email,
            settings.smtp_host,
            settings.smtp_port,
        )


def send_event_created_email(
    recipient_email: str,
    recipient_name: str,
    event_name: str,
    venue: str,
    starts_at: str,
) -> None:
    _send_email(
        recipient_email,
        f"Event Created: {event_name}",
        f"""Hi {recipient_name},

Your event has been created successfully.

Event: {event_name}
Venue: {venue}
Starts at: {starts_at}

Thanks,
{settings.app_name}
""",
    )


def send_welcome_email(
    recipient_email: str,
    recipient_name: str,
) -> None:
    _send_email(
        recipient_email,
        f"Welcome to {settings.app_name}",
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
""",
    )


def send_event_notification_email(
    recipient_email: str,
    recipient_name: str,
    action: str,
    event_name: str,
    venue: str,
    starts_at: str,
    previous_details: str = "",
) -> None:
    _send_email(
        recipient_email,
        f"Event {action}: {event_name}",
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
""",
    )


def send_notification_email(
    recipient_email: str,
    recipient_name: str,
    notification: str,
    subject: str = "TicketFlow Notification",
) -> None:
    _send_email(
        recipient_email,
        subject,
        f"""Hi {recipient_name},

{notification}

Please review your TicketFlow account for more details.

Thanks,
{settings.app_name}
""",
    )
