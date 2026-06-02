import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

def send_notification_email(subject: str, message: str, recipient_list: list[str], html_message: str | None = None) -> bool:
    """
    Wysyła e-mail w sposób synchroniczny za pomocą skonfigurowanego Gmail API Backend.

    Args:
        subject (str): Temat wiadomości.
        message (str): Treść tekstowa wiadomości.
        recipient_list (list): Lista adresów e-mail odbiorców.
        html_message (str, opcjonalnie): Treść HTML wiadomości.

    Returns:
        bool: True jeśli wysyłka zakończyła się sukcesem, False w przeciwnym wypadku.
    """
    logger.info("Rozpoczęcie synchronicznej wysyłki e-maila: '%s' do %s", subject, recipient_list)
    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        if sent_count > 0:
            logger.info("E-mail '%s' został pomyślnie wysłany do %s.", subject, recipient_list)
            return True
        else:
            logger.warning("Funkcja send_mail zwróciła 0 dla e-maila '%s' do %s.", subject, recipient_list)
            return False
    except Exception as e:
        logger.exception("Błąd podczas wysyłania e-maila '%s' do %s: %s", subject, recipient_list, str(e))
        return False
