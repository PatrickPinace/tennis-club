"""
REST API views for Tennis Club v2
Dashboard and statistics endpoints
"""
from django.contrib.auth.models import User
from django.db.models import Q, Count, Sum
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from datetime import datetime, timedelta
from django.utils import timezone

from .models import (
    Profile, Match, Tournament, Reservation,
    Participant, RankingHistory, Notification
)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """
    Get dashboard statistics for authenticated user
    GET /api/dashboard/stats/

    Returns:
    - user_stats: total matches, wins, losses, win_rate
    - ranking: position, elo_rating, ranking_points
    - next_reservation: upcoming reservation details
    - last_match: most recent match result
    - upcoming_tournament: next tournament user is registered for
    - recent_activity: list of recent notifications/activities
    """
    user = request.user

    # Get user profile
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        return Response({
            'error': 'User profile not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # === USER STATS ===
    # Count matches where user is any of the players
    total_matches = Match.objects.filter(
        Q(player1=user) | Q(player2=user) | Q(player3=user) | Q(player4=user),
        status='completed'
    ).count()

    # Count wins (where user's side won)
    wins = Match.objects.filter(
        (Q(player1=user) | Q(player3=user)) & Q(winner_side='p1') |
        (Q(player2=user) | Q(player4=user)) & Q(winner_side='p2'),
        status='completed'
    ).count()

    losses = total_matches - wins
    win_rate = round((wins / total_matches * 100) if total_matches > 0 else 0, 1)

    # === RANKING ===
    # Get club ranking position (based on elo_rating)
    ranking_position = Profile.objects.filter(
        elo_rating__gt=profile.elo_rating
    ).count() + 1

    total_players = Profile.objects.count()
    top_percentage = round((ranking_position / total_players * 100) if total_players > 0 else 0, 1)

    # === NEXT RESERVATION ===
    next_reservation = Reservation.objects.filter(
        user=user,
        start_time__gte=timezone.now(),
        status__in=['pending', 'confirmed']
    ).order_by('start_time').first()

    next_reservation_data = None
    if next_reservation:
        next_reservation_data = {
            'id': next_reservation.id,
            'date': next_reservation.start_time.strftime('%d %b'),
            'time': f"{next_reservation.start_time.strftime('%H:%M')}-{next_reservation.end_time.strftime('%H:%M')}",
            'court': {
                'number': next_reservation.court.number,
                'surface': next_reservation.court.get_surface_display(),
                'facility': next_reservation.court.facility.name
            },
            'status': next_reservation.status
        }

    # === LAST MATCH ===
    last_match = Match.objects.filter(
        Q(player1=user) | Q(player2=user) | Q(player3=user) | Q(player4=user),
        status='completed'
    ).order_by('-match_date').first()

    last_match_data = None
    if last_match:
        # Determine if user won
        user_won = (
            (last_match.winner_side == 'p1' and (last_match.player1 == user or last_match.player3 == user)) or
            (last_match.winner_side == 'p2' and (last_match.player2 == user or last_match.player4 == user))
        )

        # Get opponent name
        if last_match.player1 == user:
            opponent = last_match.player2
        elif last_match.player2 == user:
            opponent = last_match.player1
        else:
            opponent = last_match.player1  # For doubles, simplify

        # Get score
        sets = []
        if last_match.set1_p1 is not None:
            sets.append(f"{last_match.set1_p1}:{last_match.set1_p2}")
        if last_match.set2_p1 is not None:
            sets.append(f"{last_match.set2_p1}:{last_match.set2_p2}")
        if last_match.set3_p1 is not None:
            sets.append(f"{last_match.set3_p1}:{last_match.set3_p2}")

        last_match_data = {
            'id': last_match.id,
            'date': last_match.match_date.strftime('%d %b'),
            'opponent': f"{opponent.first_name} {opponent.last_name}" if opponent.first_name else opponent.username,
            'result': 'won' if user_won else 'lost',
            'score': ' '.join(sets),
            'location': last_match.court.facility.name if last_match.court else 'Unknown'
        }

    # === UPCOMING TOURNAMENT ===
    upcoming_tournament = Tournament.objects.filter(
        participants__user=user,
        start_date__gte=timezone.now(),
        status__in=['registration', 'scheduled']
    ).order_by('start_date').first()

    upcoming_tournament_data = None
    if upcoming_tournament:
        participant = Participant.objects.get(tournament=upcoming_tournament, user=user)
        upcoming_tournament_data = {
            'id': upcoming_tournament.id,
            'name': upcoming_tournament.name,
            'date_range': f"{upcoming_tournament.start_date.strftime('%d-%d %b')}" if upcoming_tournament.start_date.month == upcoming_tournament.end_date.month else f"{upcoming_tournament.start_date.strftime('%d %b')}-{upcoming_tournament.end_date.strftime('%d %b')}",
            'status': upcoming_tournament.get_status_display(),
            'participant_status': participant.get_status_display()
        }

    # === RECENT ACTIVITY ===
    recent_activity = Notification.objects.filter(
        user=user
    ).order_by('-created_at')[:5]

    recent_activity_data = [
        {
            'id': notif.id,
            'type': notif.notification_type,
            'title': notif.title,
            'message': notif.message,
            'is_read': notif.is_read,
            'created_at': notif.created_at.strftime('%d %b %Y, %H:%M')
        }
        for notif in recent_activity
    ]

    return Response({
        'user_stats': {
            'total_matches': total_matches,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate
        },
        'ranking': {
            'position': ranking_position,
            'elo_rating': profile.elo_rating,
            'ranking_points': float(profile.ranking_points),
            'top_percentage': top_percentage
        },
        'next_reservation': next_reservation_data,
        'last_match': last_match_data,
        'upcoming_tournament': upcoming_tournament_data,
        'recent_activity': recent_activity_data
    })
