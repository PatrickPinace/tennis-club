"""
REST API views for authentication
Used by Astro frontend
"""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import logging

from apps.users.models import Profile
from .authentication import CsrfExemptSessionAuthentication

logger = logging.getLogger(__name__)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])  # Allow unauthenticated access
def api_login(request):
    """
    Login endpoint for Astro frontend
    POST /api/auth/login/
    Body: { "username": "...", "password": "..." }
    Returns: { "success": true, "user": {...} }
    Sets sessionid cookie
    """
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({
            'success': False,
            'error': 'Username and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Try to find user by username or email
    user_candidate = None
    try:
        user_candidate = User.objects.get(username=username)
    except User.DoesNotExist:
        try:
            user_candidate = User.objects.get(email=username)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Użytkownik o podanym loginie/e-mailu nie istnieje.'
            }, status=status.HTTP_400_BAD_REQUEST)

    if user_candidate:
        # Authenticate with password
        user_auth = authenticate(
            request,
            username=user_candidate.username,
            password=password,
            backend='django.contrib.auth.backends.ModelBackend'
        )

        if user_auth is not None:
            # Check if user has a profile, create if not
            try:
                user_auth.profile
            except Profile.DoesNotExist:
                Profile.objects.create(user=user_auth)
                logger.info(f"Created profile for user {user_auth.username}")

            # Login user (creates session)
            login(request, user_auth, backend='django.contrib.auth.backends.ModelBackend')
            logger.info(f"API login successful for user {user_auth.username}")

            return Response({
                'success': True,
                'user': {
                    'id': user_auth.id,
                    'username': user_auth.username,
                    'email': user_auth.email,
                    'first_name': user_auth.first_name,
                    'last_name': user_auth.last_name,
                    'is_staff': user_auth.is_staff,
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'Nieprawidłowe hasło.'
            }, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'success': False,
        'error': 'Login failed'
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_logout(request):
    """
    Logout endpoint for Astro frontend
    POST /api/auth/logout/
    Destroys session
    """
    if request.user.is_authenticated:
        logger.info(f"API logout for user {request.user.username}")
        logout(request)

    return Response({
        'success': True,
        'message': 'Logged out successfully'
    })


@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_current_user(request):
    """
    Get current authenticated user
    GET /api/auth/me/
    Returns: { "authenticated": true, "user": {...} }
    Used by Astro middleware to verify session
    """
    if not request.user.is_authenticated:
        return Response({
            'authenticated': False
        }, status=status.HTTP_401_UNAUTHORIZED)

    return Response({
        'authenticated': True,
        'user': {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'is_staff': request.user.is_staff,
        }
    })


@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_user_profile(request):
    """
    Profil aktualnie zalogowanego użytkownika — dane dla Astro /profile.
    GET /api/auth/profile/

    Zwraca:
      - dane User (username, email, first_name, last_name, is_staff, date_joined)
      - dane Profile (city, birth_date, start_date / member since)
      - ranking SNG (pozycja, punkty, mecze, win_rate)
      - DBL ranking (pozycja, punkty)

    Auth: sesja Django. Gdy niezalogowany → 401.
    """
    if not request.user.is_authenticated:
        return Response({'authenticated': False}, status=status.HTTP_401_UNAUTHORIZED)

    user = request.user

    # ── Profil ────────────────────────────────────────────────────────────────
    try:
        profile = user.profile
        city = profile.city
        birth_date = profile.birth_date.isoformat() if profile.birth_date else None
        member_since = profile.start_date.isoformat() if profile.start_date else None
    except Profile.DoesNotExist:
        city = None
        birth_date = None
        member_since = None

    # Fallback member_since → data rejestracji konta Django
    if not member_since:
        member_since = user.date_joined.date().isoformat()

    # ── Ranking SNG ───────────────────────────────────────────────────────────
    try:
        from apps.rankings.models import PlayerRanking
        sng = PlayerRanking.objects.filter(user=user, match_type='SNG').first()
        ranking_sng = {
            'position': sng.position if sng else None,
            'points': float(sng.points) if sng else None,
            'matches_played': sng.matches_played if sng else None,
            'matches_won': sng.matches_won if sng else None,
            'matches_lost': sng.matches_lost if sng else None,
            'sets_won': sng.sets_won if sng else None,
            'sets_lost': sng.sets_lost if sng else None,
            'win_rate': round(sng.matches_won / sng.matches_played * 100)
                        if sng and sng.matches_played else None,
        } if sng else None
    except Exception:
        ranking_sng = None

    # ── Ranking DBL ───────────────────────────────────────────────────────────
    try:
        dbl = PlayerRanking.objects.filter(user=user, match_type='DBL').first()
        ranking_dbl = {
            'position': dbl.position if dbl else None,
            'points': float(dbl.points) if dbl else None,
            'matches_played': dbl.matches_played if dbl else None,
            'matches_won': dbl.matches_won if dbl else None,
            'matches_lost': dbl.matches_lost if dbl else None,
            'win_rate': round(dbl.matches_won / dbl.matches_played * 100)
                        if dbl and dbl.matches_played else None,
        } if dbl else None
    except Exception:
        ranking_dbl = None

    return Response({
        'authenticated': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined.date().isoformat(),
            'city': city,
            'birth_date': birth_date,
            'member_since': member_since,
        },
        'ranking_sng': ranking_sng,
        'ranking_dbl': ranking_dbl,
    })


@api_view(['GET'])
@ensure_csrf_cookie
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def get_csrf_token(request):
    """
    Get CSRF token
    GET /api/auth/csrf/
    Returns: { "detail": "CSRF cookie set" }
    Sets the csrftoken cookie for subsequent POST requests
    """
    return Response({
        'detail': 'CSRF cookie set'
    })
