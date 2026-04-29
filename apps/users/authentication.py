"""
Custom authentication class for Astro frontend API
SessionAuthentication without CSRF enforcement
"""
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication without CSRF check
    Use only for specific API endpoints that handle CORS properly
    """
    def enforce_csrf(self, request):
        return  # Skip CSRF check
