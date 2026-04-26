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
from apps.users.forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
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

    # ── Statystyki turniejowe ─────────────────────────────────────────────────
    try:
        from apps.tournaments.models import Participant, TournamentsMatch
        from django.db.models import Q

        participations = Participant.objects.filter(user=user).select_related('tournament')
        participant_ids = list(participations.values_list('id', flat=True))

        tournaments_all      = {p.tournament_id for p in participations}
        tournaments_finished = {p.tournament_id for p in participations if p.tournament.status == 'FIN'}
        tournaments_active   = {p.tournament_id for p in participations if p.tournament.status == 'ACT'}

        t_matches = TournamentsMatch.objects.filter(
            Q(participant1_id__in=participant_ids) | Q(participant2_id__in=participant_ids),
            status__in=['CMP', 'WDR'],
        )
        t_matches_played = t_matches.count()
        t_matches_won    = t_matches.filter(winner_id__in=participant_ids).count()
        t_win_rate       = round(t_matches_won / t_matches_played * 100) if t_matches_played else None

        tournament_stats = {
            'tournaments_played':   len(tournaments_all),
            'tournaments_finished': len(tournaments_finished),
            'tournaments_active':   len(tournaments_active),
            'matches_played':       t_matches_played,
            'matches_won':          t_matches_won,
            'win_rate':             t_win_rate,
        }
    except Exception:
        tournament_stats = None

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
        'tournament_stats': tournament_stats,
    })


@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_register(request):
    """
    Registration endpoint for Astro frontend.
    POST /api/auth/register/
    Body: { "login", "first_name", "last_name", "email", "password_1", "password_2", "data_processing_consent" }
    Returns: { "success": true, "user": {...} }  on success
             { "success": false, "errors": { field: [msg, ...] } }  on validation failure
    Sets sessionid cookie (auto-login after registration).
    """
    # Przekaż dane z JSON do formularza Django (QueryDict-like via dict)
    data = request.data
    form_data = {
        'login': data.get('login', ''),
        'first_name': data.get('first_name', ''),
        'last_name': data.get('last_name', ''),
        'email': data.get('email', ''),
        'password_1': data.get('password_1', ''),
        'password_2': data.get('password_2', ''),
        'data_processing_consent': data.get('data_processing_consent', False),
    }

    form = UserRegisterForm(form_data)

    if not form.is_valid():
        # Zwróć błędy per-field w formacie { field: ["komunikat", ...] }
        errors = {field: list(errs) for field, errs in form.errors.items()}
        return Response({
            'success': False,
            'errors': errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    cleaned = form.cleaned_data
    try:
        user = User.objects.create_user(
            username=cleaned['login'],
            password=cleaned['password_1'],
            first_name=cleaned['first_name'],
            last_name=cleaned['last_name'],
            email=cleaned['email'],
        )
    except Exception as e:
        logger.error(f"api_register: create_user failed: {e}")
        return Response({
            'success': False,
            'errors': {'__all__': ['Błąd podczas tworzenia konta. Spróbuj ponownie.']},
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Auto-login — tworzy sesję (sessionid cookie)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    logger.info(f"api_register: user {user.username} registered and logged in")

    return Response({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def api_update_profile(request):
    """
    Aktualizacja danych profilu zalogowanego użytkownika.
    PATCH /api/auth/profile/update/
    Body (wszystkie pola opcjonalne):
      { "first_name", "last_name", "email", "city", "birth_date" }
    Returns: { "success": true }  |  { "success": false, "errors": {field: [msg]} }
    Auth: sesja Django. Gdy niezalogowany → 401.
    """
    if not request.user.is_authenticated:
        return Response({'success': False, 'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)

    data = request.data

    # Pola User — budujemy dane formularza z aktualnych wartości + patch
    user_data = {
        'first_name': data.get('first_name', user.first_name),
        'last_name':  data.get('last_name',  user.last_name),
        'email':      data.get('email',       user.email),
    }

    # Pola Profile
    profile_data = {
        'city':       data.get('city',       profile.city       or ''),
        'birth_date': data.get('birth_date', profile.birth_date or ''),
        'start_date': profile.start_date or '',  # nie edytowalne przez user — zachowaj
    }

    user_form    = UserUpdateForm(user_data, instance=user)
    profile_form = ProfileUpdateForm(profile_data, instance=profile)

    user_valid    = user_form.is_valid()
    profile_valid = profile_form.is_valid()

    if not user_valid or not profile_valid:
        errors = {}
        errors.update({f: list(v) for f, v in user_form.errors.items()})
        errors.update({f: list(v) for f, v in profile_form.errors.items()})
        return Response({'success': False, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    user_form.save()
    profile_form.save()
    logger.info(f"api_update_profile: user {user.username} updated profile")

    return Response({'success': True})


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
