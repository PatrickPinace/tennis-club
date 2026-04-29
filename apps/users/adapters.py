from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class CustomAccountAdapter(DefaultAccountAdapter):

    def is_open_for_signup(self, request):
        # Disable registration via the allauth registration form
        return False

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Wywoływane tuż przed zakończeniem procesu logowania społecznościowego.

        Możesz tutaj sprawdzić, czy adres e-mail z sociallogin już istnieje
        w bazie danych i odpowiednio zareagować.
        """

        # Sprawdź, czy użytkownik jest zalogowany
        if request.user.is_authenticated:
            return  # Jeśli użytkownik jest zalogowany, pozwól na normalny przepływ

        # Pobierz adres e-mail z sociallogin
        email = sociallogin.account.extra_data.get('email')

        # Sprawdź, czy istnieje już użytkownik z tym adresem e-mail
        if email:
            try:
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)
                logger.info(f"Połączono konto social dla {email} z istniejącym użytkownikiem {user.username}.")
                messages.success(request, "Konto społecznościowe zostało połączone z istniejącym kontem.")
                return redirect('/')  # Przekierowanie na stronę główną lub inną pożądaną stronę
            except User.DoesNotExist:
                # Użytkownik nie istnieje, pozwól na kontynuację do formularza rejestracji allauth
                pass