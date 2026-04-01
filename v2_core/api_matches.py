"""
REST API views for Matches (Sprint 4)
"""
from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from django.shortcuts import get_object_or_404
from datetime import datetime

from .models import Match, Court


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def matches_list(request):
    """
    Get matches for authenticated user
    GET /api/matches/?status=completed&limit=20

    Query params:
    - status: filter by status (scheduled, in_progress, completed, cancelled)
    - limit: max results (default 50)
    """
    user = request.user

    # Get query params
    status_filter = request.GET.get('status', None)
    limit = int(request.GET.get('limit', 50))

    # Get matches where user is any of the players
    matches = Match.objects.filter(
        Q(player1=user) | Q(player2=user) | Q(player3=user) | Q(player4=user)
    )

    # Apply status filter
    if status_filter:
        matches = matches.filter(status=status_filter)

    # Order by match_date descending and limit
    matches = matches.order_by('-match_date')[:limit]

    # Serialize matches
    matches_data = []
    for match in matches:
        # Determine if user won
        user_won = None
        if match.status == Match.Status.COMPLETED and match.winner_side:
            user_won = (
                (match.winner_side == 'p1' and (match.player1 == user or match.player3 == user)) or
                (match.winner_side == 'p2' and (match.player2 == user or match.player4 == user))
            )

        # Get opponent info
        if match.is_doubles:
            if match.player1 == user or match.player3 == user:
                opponents = [match.player2, match.player4]
            else:
                opponents = [match.player1, match.player3]
            opponent_names = ' / '.join([
                f"{p.first_name} {p.last_name}" if p and p.first_name else (p.username if p else "?")
                for p in opponents
            ])
        else:
            opponent = match.player2 if match.player1 == user else match.player1
            opponent_names = f"{opponent.first_name} {opponent.last_name}" if opponent.first_name else opponent.username

        # Get score
        sets = []
        if match.set1_p1 is not None:
            sets.append({'p1': match.set1_p1, 'p2': match.set1_p2})
        if match.set2_p1 is not None:
            sets.append({'p1': match.set2_p1, 'p2': match.set2_p2})
        if match.set3_p1 is not None:
            sets.append({'p1': match.set3_p1, 'p2': match.set3_p2})

        matches_data.append({
            'id': match.id,
            'date': match.match_date.strftime('%Y-%m-%d'),
            'status': match.status,
            'is_doubles': match.is_doubles,
            'opponent': opponent_names,
            'result': 'won' if user_won is True else ('lost' if user_won is False else None),
            'sets': sets,
            'court': {
                'id': match.court.id,
                'name': f"Kort {match.court.number}",
                'surface': match.court.get_surface_display(),
                'facility': match.court.facility.name
            } if match.court else None,
            'description': match.description
        })

    return Response({
        'matches': matches_data,
        'count': len(matches_data)
    })


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def match_detail(request, match_id):
    """
    Get match details
    GET /api/matches/<id>/
    """
    match = get_object_or_404(Match, id=match_id)
    user = request.user

    # Check if user is participant
    if user not in match.get_all_players():
        return Response({
            'error': 'You are not a participant in this match'
        }, status=status.HTTP_403_FORBIDDEN)

    # Determine if user won
    user_won = None
    if match.status == Match.Status.COMPLETED and match.winner_side:
        user_won = (
            (match.winner_side == 'p1' and (match.player1 == user or match.player3 == user)) or
            (match.winner_side == 'p2' and (match.player2 == user or match.player4 == user))
        )

    # Serialize players
    players = {
        'player1': {
            'id': match.player1.id,
            'username': match.player1.username,
            'full_name': f"{match.player1.first_name} {match.player1.last_name}" if match.player1.first_name else match.player1.username
        },
        'player2': {
            'id': match.player2.id,
            'username': match.player2.username,
            'full_name': f"{match.player2.first_name} {match.player2.last_name}" if match.player2.first_name else match.player2.username
        }
    }

    if match.is_doubles:
        players['player3'] = {
            'id': match.player3.id,
            'username': match.player3.username,
            'full_name': f"{match.player3.first_name} {match.player3.last_name}" if match.player3.first_name else match.player3.username
        } if match.player3 else None
        players['player4'] = {
            'id': match.player4.id,
            'username': match.player4.username,
            'full_name': f"{match.player4.first_name} {match.player4.last_name}" if match.player4.first_name else match.player4.username
        } if match.player4 else None

    # Get score
    sets = []
    if match.set1_p1 is not None:
        sets.append({'p1': match.set1_p1, 'p2': match.set1_p2})
    if match.set2_p1 is not None:
        sets.append({'p1': match.set2_p1, 'p2': match.set2_p2})
    if match.set3_p1 is not None:
        sets.append({'p1': match.set3_p1, 'p2': match.set3_p2})

    return Response({
        'id': match.id,
        'date': match.match_date.strftime('%Y-%m-%d'),
        'status': match.status,
        'is_doubles': match.is_doubles,
        'players': players,
        'result': 'won' if user_won is True else ('lost' if user_won is False else None),
        'winner_side': match.winner_side,
        'sets': sets,
        'court': {
            'id': match.court.id,
            'name': f"Kort {match.court.number}",
            'surface': match.court.get_surface_display(),
            'facility': match.court.facility.name
        } if match.court else None,
        'description': match.description,
        'created_at': match.created_at.isoformat(),
        'updated_at': match.updated_at.isoformat()
    })


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_match(request):
    """
    Create a new match
    POST /api/matches/

    Body:
    {
        "player2_id": 2,
        "player3_id": 3,  // optional, for doubles
        "player4_id": 4,  // optional, for doubles
        "match_date": "2026-04-15",
        "court_id": 1,  // optional
        "description": "Mecz towarzyski"
    }
    """
    user = request.user
    data = request.data

    # Validate required fields
    if 'player2_id' not in data or 'match_date' not in data:
        return Response({
            'error': 'player2_id and match_date are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get players
    try:
        player2 = User.objects.get(id=data['player2_id'])
    except User.DoesNotExist:
        return Response({
            'error': 'Player 2 not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Check if doubles
    is_doubles = 'player3_id' in data and 'player4_id' in data
    player3 = None
    player4 = None

    if is_doubles:
        try:
            player3 = User.objects.get(id=data['player3_id'])
            player4 = User.objects.get(id=data['player4_id'])
        except User.DoesNotExist:
            return Response({
                'error': 'Player 3 or Player 4 not found'
            }, status=status.HTTP_404_NOT_FOUND)

    # Get court if provided
    court = None
    if 'court_id' in data:
        try:
            court = Court.objects.get(id=data['court_id'])
        except Court.DoesNotExist:
            return Response({
                'error': 'Court not found'
            }, status=status.HTTP_404_NOT_FOUND)

    # Parse date
    try:
        match_date = datetime.strptime(data['match_date'], '%Y-%m-%d').date()
    except ValueError:
        return Response({
            'error': 'Invalid date format. Use YYYY-MM-DD'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Create match
    try:
        match = Match.objects.create(
            player1=user,
            player2=player2,
            player3=player3,
            player4=player4,
            is_doubles=is_doubles,
            match_date=match_date,
            court=court,
            description=data.get('description', 'Mecz towarzyski'),
            status=Match.Status.SCHEDULED
        )
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'id': match.id,
        'message': 'Match created successfully'
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def update_match_result(request, match_id):
    """
    Update match result (sets and status)
    PATCH /api/matches/<id>/

    Body:
    {
        "status": "completed",
        "set1_p1": 6,
        "set1_p2": 4,
        "set2_p1": 6,
        "set2_p2": 3,
        "set3_p1": null,
        "set3_p2": null
    }
    """
    match = get_object_or_404(Match, id=match_id)
    user = request.user
    data = request.data

    # Check if user is participant
    if user not in match.get_all_players():
        return Response({
            'error': 'You are not a participant in this match'
        }, status=status.HTTP_403_FORBIDDEN)

    # Update status if provided
    if 'status' in data:
        if data['status'] not in [choice[0] for choice in Match.Status.choices]:
            return Response({
                'error': f"Invalid status. Must be one of: {[choice[0] for choice in Match.Status.choices]}"
            }, status=status.HTTP_400_BAD_REQUEST)
        match.status = data['status']

    # Update sets if provided
    if 'set1_p1' in data:
        match.set1_p1 = data['set1_p1']
    if 'set1_p2' in data:
        match.set1_p2 = data['set1_p2']
    if 'set2_p1' in data:
        match.set2_p1 = data['set2_p1']
    if 'set2_p2' in data:
        match.set2_p2 = data['set2_p2']
    if 'set3_p1' in data:
        match.set3_p1 = data['set3_p1']
    if 'set3_p2' in data:
        match.set3_p2 = data['set3_p2']

    # Save and let model compute winner
    try:
        match.save()
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'id': match.id,
        'message': 'Match updated successfully',
        'winner_side': match.winner_side
    })


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def cancel_match(request, match_id):
    """
    Cancel a match (set status to cancelled)
    DELETE /api/matches/<id>/
    """
    match = get_object_or_404(Match, id=match_id)
    user = request.user

    # Check if user is participant
    if user not in match.get_all_players():
        return Response({
            'error': 'You are not a participant in this match'
        }, status=status.HTTP_403_FORBIDDEN)

    # Can only cancel scheduled or in_progress matches
    if match.status not in [Match.Status.SCHEDULED, Match.Status.IN_PROGRESS]:
        return Response({
            'error': 'Can only cancel scheduled or in-progress matches'
        }, status=status.HTTP_400_BAD_REQUEST)

    match.status = Match.Status.CANCELLED
    match.save()

    return Response({
        'message': 'Match cancelled successfully'
    }, status=status.HTTP_200_OK)
