from django.core.cache import cache
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.db import DatabaseError
import logging

# Spróbuj zaimportować model, ale obsłuż błąd jeśli tabela jeszcze nie istnieje (np. przy pierwszej migracji)
try:
    from .models import BlockedPattern
except ImportError:
    BlockedPattern = None

logger = logging.getLogger(__name__)

class ActiveUserMiddleware:
    """
    Middleware do śledzenia ostatniej aktywności zalogowanych użytkowników.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Ustawia klucz w cache z czasem ostatniej aktywności na 5 minut
            cache.set(f'seen_{request.user.username}', timezone.now(), 300)
        response = self.get_response(request)
        return response


class BlockBotsMiddleware:
    """
    Middleware blokujący proste skanery podatności na podstawie ścieżki URL.
    Pobiera wzorce z bazy danych (model BlockedPattern) i cache'uje je.
    """
    CACHE_KEY = 'blocked_patterns_list'
    CACHE_TIMEOUT = 3600  # 1 godzina cache

    def __init__(self, get_response):
        self.get_response = get_response

    def get_blocked_patterns(self):
        """
        Pobiera listę zablokowanych wzorców z cache lub bazy danych.
        """
        patterns = cache.get(self.CACHE_KEY)
        
        if patterns is None:
            if BlockedPattern:
                try:
                    # Pobierz aktywne wzorce z bazy
                    patterns = list(BlockedPattern.objects.filter(is_active=True).values_list('pattern', flat=True))
                    # Zapisz w cache
                    cache.set(self.CACHE_KEY, patterns, self.CACHE_TIMEOUT)
                except (DatabaseError, Exception):
                    # W przypadku błędu bazy (np. migracje w toku), zwróć pustą listę lub fallback
                    patterns = []
            else:
                patterns = []
        
        return patterns

    def __call__(self, request):
        path = request.path.lower()
        blocked_patterns = self.get_blocked_patterns()
        
        # Sprawdź, czy ścieżka zawiera którykolwiek z zablokowanych wzorców
        if blocked_patterns and any(pattern.lower() in path for pattern in blocked_patterns):
            ip = getattr(request, 'META', {}).get('REMOTE_ADDR', '-')
            logger.warning(f"BLOCKED SUSPICIOUS REQUEST: {path} from IP: {ip}")
            return HttpResponseForbidden("Forbidden: Suspicious activity detected.")

        return self.get_response(request)


class PageViewMiddleware:
    """
    Middleware do śledzenia odsłon stron przez użytkowników i gości.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Logujemy odsłonę strony tylko dla standardowych ścieżek
        path = request.path
        # Ignorujemy pliki statyczne, media, panel admina, debug toolbar i health checki
        if not any(path.startswith(prefix) for prefix in ['/static/', '/media/', '/manage/', '/__debug__/', '/health/']):
            try:
                from .models import PageView

                # Pobranie adresu IP (obsługuje proxy)
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0].strip()
                else:
                    ip = request.META.get('REMOTE_ADDR')

                # Ignoruj ruch z IP 51.83.160.216 (wewnętrzna konfiguracja Astro / OVHCloud)
                if ip == '51.83.160.216':
                    return response

                user_agent = request.META.get('HTTP_USER_AGENT', '')
                method = request.method
                session_key = request.session.session_key if hasattr(request, 'session') else None
                user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None

                PageView.objects.create(
                    path=path,
                    ip_address=ip,
                    user_agent=user_agent,
                    method=method,
                    session_key=session_key,
                    user=user
                )
            except Exception:
                # Ciche zignorowanie błędów zapisu (np. brak zmigrowanej tabeli)
                pass

        return response