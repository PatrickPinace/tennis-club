"""
REST API views for Tournaments with full service layer integration.
Implements endpoints from turnieje.md specification.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q, Count
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime

from .models import (
    Tournament, Participant, TournamentMatch, TournamentConfig,
    TournamentManager
)
from .services import (
    TournamentCreationService,
    TournamentRegistrationService,
    TournamentBracketService,
    TournamentMatchService
)


# ============================================================================
# Tournament CRUD
# ============================================================================

@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def tournaments_list_create(request):
    """
    GET /api/tournaments/ - List tournaments
    POST /api/tournaments/ - Create tournament (managers only)

    Query params for GET:
    - status: filter by status
    - my: if true, only user's tournaments
    - limit: max results (default 50)
    """
    if request.method == 'GET':
        return _tournaments_list(request)
    elif request.method == 'POST':
        return _create_tournament(request)


def _tournaments_list(request):
    """List tournaments with filters."""
    user = request.user
    status_filter = request.GET.get('status')
    my_tournaments = request.GET.get('my', 'false').lower() == 'true'
    limit = int(request.GET.get('limit', 50))

    tournaments = Tournament.objects.all()

    if my_tournaments:
        tournaments = tournaments.filter(participants__user=user)

    if status_filter:
        tournaments = tournaments.filter(status=status_filter)

    tournaments = tournaments.order_by('-start_date')[:limit]

    tournaments_data = []
    for tournament in tournaments:
        participant_count = Participant.objects.filter(
            tournament=tournament,
            status__in=['pending', 'confirmed']
        ).count()

        is_participant = tournament.participants.filter(user=user).exists()
        is_manager = TournamentCreationService.is_tournament_manager(tournament, user)

        user_participant = None
        if is_participant:
            participant = tournament.participants.get(user=user)
            user_participant = {
                'id': participant.id,
                'status': participant.status,
                'seed': participant.seed,
                'final_position': participant.final_position
            }

        tournaments_data.append({
            'id': tournament.id,
            'name': tournament.name,
            'description': tournament.description,
            'tournament_type': tournament.tournament_type,
            'match_format': tournament.match_format,
            'status': tournament.status,
            'visibility': tournament.visibility,
            'start_date': tournament.start_date.isoformat(),
            'end_date': tournament.end_date.isoformat(),
            'registration_deadline': tournament.registration_deadline.isoformat() if tournament.registration_deadline else None,
            'min_participants': tournament.min_participants,
            'max_participants': tournament.max_participants,
            'participant_count': participant_count,
            'is_participant': is_participant,
            'is_manager': is_manager,
            'user_participant': user_participant,
            'winner': {
                'id': tournament.winner.id,
                'display_name': tournament.winner.display_name
            } if tournament.winner else None
        })

    return Response({
        'tournaments': tournaments_data,
        'count': len(tournaments_data)
    })


def _create_tournament(request):
    """Create a new tournament."""
    try:
        tournament = TournamentCreationService.create_tournament(
            data=request.data,
            actor=request.user
        )
        return Response({
            'id': tournament.id,
            'name': tournament.name,
            'status': tournament.status,
            'message': 'Turniej został utworzony.'
        }, status=status.HTTP_201_CREATED)
    except PermissionDenied as e:
        return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def tournament_detail(request, tournament_id):
    """
    Get tournament details with participants and matches.
    GET /api/tournaments/{id}/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    user = request.user

    is_participant = tournament.participants.filter(user=user).exists()
    is_manager = TournamentCreationService.is_tournament_manager(tournament, user)

    # Get participants
    participants = Participant.objects.filter(tournament=tournament).select_related('user', 'partner')
    participants_data = []
    for p in participants:
        participants_data.append({
            'id': p.id,
            'user_id': p.user.id,
            'display_name': p.display_name,
            'seed': p.seed,
            'status': p.status,
            'final_position': p.final_position,
            'points': float(p.points),
            'matches_won': p.matches_won,
            'matches_lost': p.matches_lost
        })

    # Get matches
    matches = TournamentMatch.objects.filter(tournament=tournament).select_related(
        'player1_participant', 'player2_participant', 'winner_participant', 'court'
    )
    matches_data = []
    for match in matches:
        matches_data.append({
            'id': match.id,
            'round_number': match.round_number,
            'match_number': match.match_number,
            'bracket_position': match.bracket_position,
            'status': match.status,
            'scheduled_time': match.scheduled_time.isoformat() if match.scheduled_time else None,
            'player1': {
                'id': match.player1_participant.id,
                'display_name': match.player1_participant.display_name
            } if match.player1_participant else None,
            'player2': {
                'id': match.player2_participant.id,
                'display_name': match.player2_participant.display_name
            } if match.player2_participant else None,
            'winner': {
                'id': match.winner_participant.id,
                'display_name': match.winner_participant.display_name
            } if match.winner_participant else None,
            'sets': _format_match_sets(match),
            'walkover_reason': match.walkover_reason
        })

    return Response({
        'id': tournament.id,
        'name': tournament.name,
        'description': tournament.description,
        'tournament_type': tournament.tournament_type,
        'match_format': tournament.match_format,
        'status': tournament.status,
        'visibility': tournament.visibility,
        'registration_mode': tournament.registration_mode,
        'start_date': tournament.start_date.isoformat(),
        'end_date': tournament.end_date.isoformat(),
        'registration_deadline': tournament.registration_deadline.isoformat() if tournament.registration_deadline else None,
        'min_participants': tournament.min_participants,
        'max_participants': tournament.max_participants,
        'is_participant': is_participant,
        'is_manager': is_manager,
        'participants': participants_data,
        'matches': matches_data,
        'winner': {
            'id': tournament.winner.id,
            'display_name': tournament.winner.display_name
        } if tournament.winner else None
    })


def _format_match_sets(match):
    """Format match sets for API response."""
    sets = []
    if match.set1_p1 is not None and match.set1_p2 is not None:
        sets.append({'p1': match.set1_p1, 'p2': match.set1_p2})
    if match.set2_p1 is not None and match.set2_p2 is not None:
        sets.append({'p1': match.set2_p1, 'p2': match.set2_p2})
    if match.set3_p1 is not None and match.set3_p2 is not None:
        sets.append({'p1': match.set3_p1, 'p2': match.set3_p2})
    return sets


# ============================================================================
# Tournament Management Actions
# ============================================================================

@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def open_registration(request, tournament_id):
    """
    Open tournament registration.
    POST /api/tournaments/{id}/open-registration/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    try:
        TournamentCreationService.open_registration(tournament, request.user)
        return Response({'message': 'Zapisy zostały otwarte.'})
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def close_registration(request, tournament_id):
    """
    Close tournament registration.
    POST /api/tournaments/{id}/close-registration/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    try:
        TournamentCreationService.close_registration(tournament, request.user)
        return Response({'message': 'Zapisy zostały zamknięte.'})
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def cancel_tournament(request, tournament_id):
    """
    Cancel tournament.
    POST /api/tournaments/{id}/cancel/

    Body:
    {
        "reason": "optional cancellation reason"
    }
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    reason = request.data.get('reason', '')
    try:
        TournamentCreationService.cancel_tournament(tournament, request.user, reason)
        return Response({'message': 'Turniej został anulowany.'})
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Participant Management
# ============================================================================

@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def join_tournament(request, tournament_id):
    """
    Join tournament as participant.
    POST /api/tournaments/{id}/join/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    try:
        participant = TournamentRegistrationService.join_tournament(tournament, request.user)
        return Response({
            'id': participant.id,
            'status': participant.status,
            'message': 'Pomyślnie zapisano do turnieju.'
        }, status=status.HTTP_201_CREATED)
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def withdraw_from_tournament(request, tournament_id):
    """
    Withdraw from tournament.
    POST /api/tournaments/{id}/withdraw/

    Body:
    {
        "reason": "optional withdrawal reason"
    }
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    reason = request.data.get('reason', '')
    try:
        TournamentRegistrationService.withdraw_from_tournament(
            tournament, request.user, request.user, reason
        )
        return Response({'message': 'Pomyślnie wypisano z turnieju.'})
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def approve_participant(request, tournament_id):
    """
    Approve or reject participant (manager only).
    POST /api/tournaments/{id}/approve-participant/

    Body:
    {
        "participant_id": 123,
        "approved": true
    }
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    participant_id = request.data.get('participant_id')
    approved = request.data.get('approved', True)

    if not participant_id:
        return Response({'error': 'participant_id jest wymagany.'}, status=status.HTTP_400_BAD_REQUEST)

    participant = get_object_or_404(Participant, id=participant_id, tournament=tournament)

    try:
        TournamentRegistrationService.approve_participant(participant, request.user, approved)
        message = 'Uczestnik został zatwierdzony.' if approved else 'Uczestnik został odrzucony.'
        return Response({'message': message})
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def confirm_participants(request, tournament_id):
    """
    Confirm final participant list (manager only).
    POST /api/tournaments/{id}/confirm-participants/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    try:
        TournamentRegistrationService.confirm_participants(tournament, request.user)
        return Response({'message': 'Skład został zatwierdzony.'})
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Bracket and Match Management
# ============================================================================

@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def generate_bracket(request, tournament_id):
    """
    Generate tournament bracket (manager only).
    POST /api/tournaments/{id}/generate-bracket/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    try:
        matches = TournamentBracketService.generate_bracket(tournament, request.user)
        return Response({
            'message': 'Drabinka została wygenerowana.',
            'num_matches': len(matches)
        })
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_bracket(request, tournament_id):
    """
    Get tournament bracket.
    GET /api/tournaments/{id}/bracket/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    matches = TournamentMatch.objects.filter(tournament=tournament).select_related(
        'player1_participant', 'player2_participant', 'winner_participant'
    ).order_by('round_number', 'match_number')

    bracket_data = []
    for match in matches:
        bracket_data.append({
            'id': match.id,
            'round': match.round_number,
            'position': match.bracket_position,
            'player1': match.player1_participant.display_name if match.player1_participant else 'TBD',
            'player2': match.player2_participant.display_name if match.player2_participant else 'TBD',
            'winner': match.winner_participant.display_name if match.winner_participant else None,
            'status': match.status,
            'sets': _format_match_sets(match)
        })

    return Response({'bracket': bracket_data})


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def start_tournament(request, tournament_id):
    """
    Start tournament (manager only).
    POST /api/tournaments/{id}/start/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    try:
        TournamentBracketService.start_tournament(tournament, request.user)
        return Response({'message': 'Turniej został rozpoczęty.'})
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def report_match_result(request, match_id):
    """
    Report match result (manager only).
    POST /api/tournament-matches/{id}/report-result/

    Body:
    {
        "set1_p1": 6, "set1_p2": 4,
        "set2_p1": 6, "set2_p2": 3,
        "set3_p1": 7, "set3_p2": 6  // optional
    }
    """
    match = get_object_or_404(TournamentMatch, id=match_id)
    try:
        updated_match = TournamentMatchService.report_result(
            match, request.data, request.user
        )
        return Response({
            'message': 'Wynik został raportowany.',
            'winner': updated_match.winner_participant.display_name
        })
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def finish_tournament(request, tournament_id):
    """
    Finish tournament and calculate positions (manager only).
    POST /api/tournaments/{id}/finish/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    try:
        TournamentMatchService.finish_tournament(tournament, request.user)
        return Response({
            'message': 'Turniej został zakończony.',
            'winner': tournament.winner.display_name if tournament.winner else None
        })
    except (PermissionDenied, ValidationError) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
