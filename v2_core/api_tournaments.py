"""
REST API views for Tournaments (Sprint 4)
"""
from django.contrib.auth.models import User
from django.db.models import Q, Count
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime

from .models import Tournament, Participant, TournamentMatch, TournamentConfig


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def tournaments_list(request):
    """
    Get tournaments list
    GET /api/tournaments/?status=active&my=true

    Query params:
    - status: filter by status (draft, registration, scheduled, active, finished, cancelled)
    - my: if true, only tournaments where user is participant
    - limit: max results (default 50)
    """
    user = request.user

    # Get query params
    status_filter = request.GET.get('status', None)
    my_tournaments = request.GET.get('my', 'false').lower() == 'true'
    limit = int(request.GET.get('limit', 50))

    # Base query
    tournaments = Tournament.objects.all()

    # Filter by user participation
    if my_tournaments:
        tournaments = tournaments.filter(participants__user=user)

    # Filter by status
    if status_filter:
        tournaments = tournaments.filter(status=status_filter)

    # Order by start_date descending and limit
    tournaments = tournaments.order_by('-start_date')[:limit]

    # Serialize tournaments
    tournaments_data = []
    for tournament in tournaments:
        # Get participant count
        participant_count = tournament.participants.count()

        # Check if user is participant
        is_participant = tournament.participants.filter(user=user).exists()
        user_participant = None
        if is_participant:
            participant = tournament.participants.get(user=user)
            user_participant = {
                'id': participant.id,
                'status': participant.status,
                'seed': participant.seed,
                'points': float(participant.points),
                'matches_won': participant.matches_won,
                'matches_lost': participant.matches_lost
            }

        tournaments_data.append({
            'id': tournament.id,
            'name': tournament.name,
            'description': tournament.description,
            'tournament_type': tournament.tournament_type,
            'match_format': tournament.match_format,
            'status': tournament.status,
            'start_date': tournament.start_date.isoformat(),
            'end_date': tournament.end_date.isoformat(),
            'registration_deadline': tournament.registration_deadline.isoformat() if tournament.registration_deadline else None,
            'facility': {
                'id': tournament.facility.id,
                'name': tournament.facility.name
            } if tournament.facility else None,
            'rank': tournament.rank,
            'max_participants': tournament.max_participants,
            'participant_count': participant_count,
            'is_participant': is_participant,
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


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def tournament_detail(request, tournament_id):
    """
    Get tournament details including participants and matches
    GET /api/tournaments/<id>/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    user = request.user

    # Check if user is participant
    is_participant = tournament.participants.filter(user=user).exists()
    user_participant = None
    if is_participant:
        participant = tournament.participants.get(user=user)
        user_participant = {
            'id': participant.id,
            'status': participant.status,
            'seed': participant.seed,
            'points': float(participant.points),
            'matches_won': participant.matches_won,
            'matches_lost': participant.matches_lost,
            'sets_won': participant.sets_won,
            'sets_lost': participant.sets_lost
        }

    # Get participants
    participants = tournament.participants.all()
    participants_data = []
    for p in participants:
        participants_data.append({
            'id': p.id,
            'user_id': p.user.id,
            'display_name': p.display_name,
            'seed': p.seed,
            'status': p.status,
            'points': float(p.points),
            'matches_won': p.matches_won,
            'matches_lost': p.matches_lost,
            'sets_won': p.sets_won,
            'sets_lost': p.sets_lost,
            'partner': {
                'id': p.partner.id,
                'username': p.partner.username,
                'full_name': f"{p.partner.first_name} {p.partner.last_name}" if p.partner.first_name else p.partner.username
            } if p.partner else None
        })

    # Get tournament matches
    matches = tournament.tournament_matches.all()
    matches_data = []
    for match in matches:
        sets = []
        if match.set1_p1 is not None:
            sets.append({'p1': match.set1_p1, 'p2': match.set1_p2})
        if match.set2_p1 is not None:
            sets.append({'p1': match.set2_p1, 'p2': match.set2_p2})
        if match.set3_p1 is not None:
            sets.append({'p1': match.set3_p1, 'p2': match.set3_p2})

        matches_data.append({
            'id': match.id,
            'round_number': match.round_number,
            'match_number': match.match_number,
            'status': match.status,
            'scheduled_time': match.scheduled_time.isoformat() if match.scheduled_time else None,
            'participant1': {
                'id': match.participant1.id,
                'display_name': match.participant1.display_name
            } if match.participant1 else None,
            'participant2': {
                'id': match.participant2.id,
                'display_name': match.participant2.display_name
            } if match.participant2 else None,
            'sets': sets,
            'winner': {
                'id': match.winner.id,
                'display_name': match.winner.display_name
            } if match.winner else None,
            'court': {
                'id': match.court.id,
                'name': f"Kort {match.court.number}",
                'surface': match.court.get_surface_display()
            } if match.court else None
        })

    # Get tournament config
    config_data = None
    if hasattr(tournament, 'config'):
        config = tournament.config
        config_data = {
            'sets_to_win': config.sets_to_win,
            'games_per_set': config.games_per_set,
            'points_for_match_win': float(config.points_for_match_win),
            'points_for_match_loss': float(config.points_for_match_loss),
            'points_for_set_win': float(config.points_for_set_win),
            'use_seeding': config.use_seeding,
            'third_place_match': config.third_place_match
        }

    return Response({
        'id': tournament.id,
        'name': tournament.name,
        'description': tournament.description,
        'tournament_type': tournament.tournament_type,
        'match_format': tournament.match_format,
        'status': tournament.status,
        'start_date': tournament.start_date.isoformat(),
        'end_date': tournament.end_date.isoformat(),
        'registration_deadline': tournament.registration_deadline.isoformat() if tournament.registration_deadline else None,
        'facility': {
            'id': tournament.facility.id,
            'name': tournament.facility.name
        } if tournament.facility else None,
        'rank': tournament.rank,
        'max_participants': tournament.max_participants,
        'participant_count': len(participants_data),
        'is_participant': is_participant,
        'user_participant': user_participant,
        'winner': {
            'id': tournament.winner.id,
            'display_name': tournament.winner.display_name
        } if tournament.winner else None,
        'participants': participants_data,
        'matches': matches_data,
        'config': config_data,
        'created_by': {
            'id': tournament.created_by.id,
            'username': tournament.created_by.username
        }
    })


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def register_for_tournament(request, tournament_id):
    """
    Register user for a tournament
    POST /api/tournaments/<id>/register/

    Body (for doubles):
    {
        "partner_id": 2  // optional, only for doubles tournaments
    }
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    user = request.user
    data = request.data

    # Check if registration is open
    if tournament.status not in ['registration', 'scheduled']:
        return Response({
            'error': 'Registration is not open for this tournament'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check registration deadline
    if tournament.registration_deadline and timezone.now() > tournament.registration_deadline:
        return Response({
            'error': 'Registration deadline has passed'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if tournament is full
    if tournament.participants.count() >= tournament.max_participants:
        return Response({
            'error': 'Tournament is full'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if already registered
    if tournament.participants.filter(user=user).exists():
        return Response({
            'error': 'You are already registered for this tournament'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get partner for doubles
    partner = None
    if tournament.match_format == 'doubles':
        if 'partner_id' not in data:
            return Response({
                'error': 'Partner is required for doubles tournaments'
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            partner = User.objects.get(id=data['partner_id'])
        except User.DoesNotExist:
            return Response({
                'error': 'Partner not found'
            }, status=status.HTTP_404_NOT_FOUND)

    # Create display name
    if partner:
        display_name = f"{user.username}/{partner.username}"
    else:
        display_name = f"{user.first_name} {user.last_name}" if user.first_name else user.username

    # Create participant
    participant = Participant.objects.create(
        tournament=tournament,
        user=user,
        partner=partner,
        display_name=display_name,
        status='registered'
    )

    return Response({
        'id': participant.id,
        'message': 'Successfully registered for tournament'
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def withdraw_from_tournament(request, tournament_id):
    """
    Withdraw from a tournament
    DELETE /api/tournaments/<id>/register/
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    user = request.user

    # Check if user is participant
    try:
        participant = tournament.participants.get(user=user)
    except Participant.DoesNotExist:
        return Response({
            'error': 'You are not registered for this tournament'
        }, status=status.HTTP_404_NOT_FOUND)

    # Check if withdrawal is allowed (only before tournament becomes active)
    if tournament.status not in ['registration', 'scheduled']:
        return Response({
            'error': 'Cannot withdraw from an active or finished tournament'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Update status to withdrawn instead of deleting
    participant.status = 'withdrawn'
    participant.save()

    return Response({
        'message': 'Successfully withdrawn from tournament'
    }, status=status.HTTP_200_OK)
