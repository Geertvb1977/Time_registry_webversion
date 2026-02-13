from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_reset_code_email(email, code):
    """
    Verstuurt de email asynchroon via Celery.
    """
    logger.info(f"[EMAIL] Sending reset code to {email}")
    logger.info(f"[EMAIL] DEBUG mode: {settings.DEBUG}")
    logger.info(f"[EMAIL] Email host: {settings.EMAIL_HOST}")
    logger.info(f"[EMAIL] Email port: {settings.EMAIL_PORT}")
    logger.info(f"[EMAIL] Email user: {settings.EMAIL_HOST_USER}")
    
    subject = 'Wachtwoord herstel code - Eventaflow'
    message = f'Je herstelcode is: {code}\n\nDeze code is 15 minuten geldig.'
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False, # Zet op False om fouten in Celery logs te zien
        )
        logger.info(f"[EMAIL] Code successfully sent to {email}")
        return f"Code verzonden naar {email}"
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send email: {e}")
        raise
