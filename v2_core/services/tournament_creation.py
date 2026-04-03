"""
Service layer for tournament creation and management.
Implements business logic from turnieje.md specification.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from typing import Dict, Any

from v2_core.models import (
    Tournament, TournamentConfig, TournamentManager, TournamentEventLog
)


class TournamentCreationService:
    """Service for creating and managing tournaments."""

    @staticmethod
    def _parse_datetime(date_str):
        """
        Parse datetime string and convert to naive datetime.
        Handles ISO format with timezone info (e.g., "2026-04-02T10:00:00.000Z").
        """
        if isinstance(date_str, datetime):
            # If already a datetime object, make it naive
            if timezone.is_aware(date_str):
                return timezone.make_naive(date_str)
            return date_str

        if isinstance(date_str, str):
            # Parse ISO format datetime string
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Make it naive (remove timezone info)
                if timezone.is_aware(dt):
                    return timezone.make_naive(dt)
                return dt
            except ValueError:
                raise ValidationError(f'Nieprawidłowy format daty: {date_str}')

        return date_str

    @staticmethod
    def can_create_tournament(user: User) -> bool:
        """
        Check if user has permission to create tournaments.
        Only admin and club_manager (staff) can create tournaments.
        """
        return user.is_staff or user.is_superuser

    @staticmethod
    @transaction.atomic
    def create_tournament(data: Dict[str, Any], actor: User) -> Tournament:
        """
        Create a new tournament with config and assign creator as owner.

        Args:
            data: Tournament data dictionary
            actor: User creating the tournament

        Returns:
            Created Tournament instance

        Raises:
            PermissionDenied: If user doesn't have permission
            ValidationError: If data validation fails
        """
        # Permission check
        if not TournamentCreationService.can_create_tournament(actor):
            raise PermissionDenied('Tylko administratorzy i managerowie klubu mogą tworzyć turnieje.')

        # Extract and validate data
        name = data.get('name')
        if not name:
            raise ValidationError('Nazwa turnieju jest wymagana.')

        # Parse and convert datetimes to naive (required for SQLite with USE_TZ=False)
        start_date = TournamentCreationService._parse_datetime(data.get('start_date'))
        end_date = TournamentCreationService._parse_datetime(data.get('end_date'))
        if not start_date or not end_date:
            raise ValidationError('Daty rozpoczęcia i zakończenia są wymagane.')

        if end_date <= start_date:
            raise ValidationError('Data zakończenia musi być późniejsza niż data rozpoczęcia.')

        min_participants = data.get('min_participants', 2)
        max_participants = data.get('max_participants', 16)

        if min_participants < 2:
            raise ValidationError('Minimalna liczba uczestników musi wynosić co najmniej 2.')

        if max_participants < min_participants:
            raise ValidationError('Maksymalna liczba uczestników musi być >= minimalnej liczby.')

        registration_deadline = data.get('registration_deadline')
        if registration_deadline:
            registration_deadline = TournamentCreationService._parse_datetime(registration_deadline)
            if registration_deadline > start_date:
                raise ValidationError('Termin zamknięcia rejestracji musi być przed datą rozpoczęcia turnieju.')

        # Parse registration_open_at if provided
        registration_open_at = data.get('registration_open_at')
        if registration_open_at:
            registration_open_at = TournamentCreationService._parse_datetime(registration_open_at)

        # Create tournament
        tournament = Tournament.objects.create(
            name=name,
            description=data.get('description', ''),
            tournament_type=data.get('tournament_type', 'single_elimination'),
            match_format=data.get('match_format', 'singles'),
            visibility=data.get('visibility', 'public'),
            registration_mode=data.get('registration_mode', 'auto'),
            registration_open_at=registration_open_at,
            registration_deadline=registration_deadline,
            start_date=start_date,
            end_date=end_date,
            status='draft',
            facility_id=data.get('facility_id'),
            rank=data.get('rank', 1),
            min_participants=min_participants,
            max_participants=max_participants,
            created_by=actor,
            updated_by=actor
        )

        # Create tournament config
        TournamentConfig.objects.create(
            tournament=tournament,
            sets_to_win=data.get('sets_to_win', 2),
            games_per_set=data.get('games_per_set', 6),
            use_seeding=data.get('use_seeding', True),
            third_place_match=data.get('third_place_match', True),
            # Liga scoring (Round Robin)
            points_for_match_win=data.get('points_for_match_win', 2.0),
            points_for_match_loss=data.get('points_for_match_loss', 1.0),
            points_for_set_win=data.get('points_for_set_win', 0.5),
            points_for_set_loss=data.get('points_for_set_loss', 0.0),
            points_for_game_win=data.get('points_for_game_win', 0.1),
            points_for_game_loss=data.get('points_for_game_loss', -0.1),
            points_for_tiebreak_point_win=data.get('points_for_tiebreak_point_win', 0.05),
            points_for_tiebreak_point_loss=data.get('points_for_tiebreak_point_loss', -0.05),
            # Tiebreaker criteria
            tiebreaker_criteria=data.get('tiebreaker_criteria', 'head_to_head')
        )

        # Add creator as owner
        TournamentManager.objects.create(
            tournament=tournament,
            user=actor,
            role='owner'
        )

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='created',
            actor=actor,
            payload={
                'tournament_id': tournament.id,
                'name': tournament.name,
                'tournament_type': tournament.tournament_type,
                'max_participants': tournament.max_participants
            }
        )

        return tournament

    @staticmethod
    def is_tournament_manager(tournament: Tournament, user: User) -> bool:
        """Check if user is a manager of the tournament."""
        if user.is_superuser:
            return True
        return TournamentManager.objects.filter(
            tournament=tournament,
            user=user
        ).exists()

    @staticmethod
    @transaction.atomic
    def open_registration(tournament: Tournament, actor: User) -> None:
        """
        Open tournament registration.

        Args:
            tournament: Tournament instance
            actor: User performing the action

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If tournament is not in draft status
        """
        if not TournamentCreationService.is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą otworzyć zapisy.')

        if tournament.status != 'draft':
            raise ValidationError('Zapisy można otworzyć tylko dla turnieju w statusie draft.')

        tournament.status = 'registration_open'
        tournament.updated_by = actor
        if not tournament.registration_open_at:
            tournament.registration_open_at = timezone.now()
        tournament.save()

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='registration_opened',
            actor=actor,
            payload={'timestamp': timezone.now().isoformat()}
        )

    @staticmethod
    @transaction.atomic
    def close_registration(tournament: Tournament, actor: User) -> None:
        """
        Close tournament registration.

        Args:
            tournament: Tournament instance
            actor: User performing the action

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If tournament is not in registration_open status
        """
        if not TournamentCreationService.is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą zamknąć zapisy.')

        if tournament.status != 'registration_open':
            raise ValidationError('Można zamknąć tylko otwarte zapisy.')

        tournament.status = 'registration_closed'
        tournament.updated_by = actor
        tournament.save()

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='registration_closed',
            actor=actor,
            payload={'timestamp': timezone.now().isoformat()}
        )

    @staticmethod
    @transaction.atomic
    def cancel_tournament(tournament: Tournament, actor: User, reason: str = '') -> None:
        """
        Cancel a tournament.

        Args:
            tournament: Tournament instance
            actor: User performing the action
            reason: Cancellation reason

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If tournament cannot be cancelled
        """
        if not TournamentCreationService.is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą anulować turniej.')

        if tournament.status == 'finished':
            raise ValidationError('Nie można anulować zakończonego turnieju.')

        tournament.status = 'cancelled'
        tournament.cancelled_at = timezone.now()
        tournament.updated_by = actor
        tournament.save()

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='tournament_cancelled',
            actor=actor,
            payload={
                'timestamp': timezone.now().isoformat(),
                'reason': reason
            }
        )
