"""
Service layer for tournament participant registration and management.
Implements business logic from turnieje.md specification.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from typing import Optional

from v2_core.models import (
    Tournament, Participant, TournamentEventLog, TournamentManager
)


class TournamentRegistrationService:
    """Service for handling tournament participant registration."""

    @staticmethod
    def _is_tournament_manager(tournament: Tournament, user: User) -> bool:
        """Check if user is a manager of the tournament."""
        if user.is_superuser:
            return True
        return TournamentManager.objects.filter(
            tournament=tournament,
            user=user
        ).exists()

    @staticmethod
    @transaction.atomic
    def join_tournament(tournament: Tournament, user: User) -> Participant:
        """
        Register a user for a tournament.
        Protected against race conditions and double registration.

        Args:
            tournament: Tournament instance
            user: User joining the tournament

        Returns:
            Created Participant instance (or existing if already registered)

        Raises:
            ValidationError: If registration conditions are not met
        """
        # Lock tournament row to prevent race conditions when checking participant count
        tournament = Tournament.objects.select_for_update().get(pk=tournament.pk)

        # Check if registration is open
        if tournament.status != 'registration_open':
            raise ValidationError('Zapisy do turnieju nie są otwarte.')

        # Check deadline
        if tournament.registration_deadline and timezone.now() > tournament.registration_deadline:
            raise ValidationError('Minął termin zapisów do turnieju.')

        # Check if user is already registered (idempotency)
        existing = Participant.objects.filter(tournament=tournament, user=user).first()
        if existing:
            # Already registered - return existing participant
            return existing

        # Check participant limit
        current_count = Participant.objects.filter(
            tournament=tournament,
            status__in=['pending', 'confirmed']
        ).count()

        if current_count >= tournament.max_participants:
            raise ValidationError('Osiągnięto maksymalną liczbę uczestników.')

        # Determine initial status based on registration mode
        if tournament.registration_mode == 'auto':
            initial_status = 'confirmed'
            approved_at = timezone.now()
        else:  # approval_required
            initial_status = 'pending'
            approved_at = None

        # Create participant
        participant = Participant.objects.create(
            tournament=tournament,
            user=user,
            display_name=user.get_full_name() or user.username,
            status=initial_status,
            joined_at=timezone.now(),
            approved_at=approved_at
        )

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='participant_joined',
            actor=user,
            payload={
                'participant_id': participant.id,
                'user_id': user.id,
                'username': user.username,
                'status': initial_status
            }
        )

        return participant

    @staticmethod
    @transaction.atomic
    def withdraw_from_tournament(tournament: Tournament, user: User, actor: User, reason: str = '') -> None:
        """
        Withdraw a user from a tournament.

        Args:
            tournament: Tournament instance
            user: User withdrawing (can be different from actor if manager)
            actor: User performing the action
            reason: Withdrawal reason

        Raises:
            ValidationError: If withdrawal conditions are not met
            PermissionDenied: If user doesn't have permission
        """
        try:
            participant = Participant.objects.get(tournament=tournament, user=user)
        except Participant.DoesNotExist:
            raise ValidationError('Nie jesteś zapisany do tego turnieju.')

        # Permission check
        is_manager = TournamentRegistrationService._is_tournament_manager(tournament, actor)
        is_self = user == actor

        # Users can withdraw themselves only before participants_confirmed
        if is_self and not is_manager:
            if tournament.status in ['participants_confirmed', 'bracket_ready', 'in_progress', 'finished']:
                raise PermissionDenied(
                    'Nie możesz sam się wypisać po zatwierdzeniu składu. Skontaktuj się z organizatorem.'
                )

        # Only managers can withdraw participants after participants_confirmed
        if not is_self and not is_manager:
            raise PermissionDenied('Tylko managerowie turnieju mogą wypisać innych uczestników.')

        # Cannot withdraw from finished tournament
        if tournament.status == 'finished':
            raise ValidationError('Nie można wypisać się z zakończonego turnieju.')

        # Update participant status
        participant.status = 'withdrawn'
        participant.withdrawn_at = timezone.now()
        participant.withdrawal_reason = reason
        participant.save()

        # If tournament has bracket, handle walkover
        if tournament.status in ['bracket_ready', 'in_progress']:
            from v2_core.services.tournament_match import TournamentMatchService
            TournamentMatchService.handle_participant_withdrawal(tournament, participant, actor)

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='participant_withdrawn',
            actor=actor,
            payload={
                'participant_id': participant.id,
                'user_id': user.id,
                'username': user.username,
                'reason': reason,
                'withdrawn_by': 'self' if is_self else 'manager'
            }
        )

    @staticmethod
    @transaction.atomic
    def approve_participant(participant: Participant, actor: User, approved: bool = True) -> None:
        """
        Approve or reject a participant (for approval_required mode).

        Args:
            participant: Participant instance
            actor: User performing the action
            approved: True to approve, False to reject

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If participant cannot be approved
        """
        tournament = participant.tournament

        if not TournamentRegistrationService._is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą zatwierdzać uczestników.')

        if participant.status != 'pending':
            raise ValidationError('Można zatwierdzić tylko uczestników w statusie pending.')

        if tournament.status not in ['registration_open', 'registration_closed']:
            raise ValidationError('Można zatwierdzać uczestników tylko podczas zapisów.')

        if approved:
            participant.status = 'confirmed'
            participant.approved_at = timezone.now()
            event_type = 'participant_approved'
        else:
            participant.status = 'rejected'
            event_type = 'participant_rejected'

        participant.save()

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type=event_type,
            actor=actor,
            payload={
                'participant_id': participant.id,
                'user_id': participant.user.id,
                'username': participant.user.username
            }
        )

    @staticmethod
    @transaction.atomic
    def confirm_participants(tournament: Tournament, actor: User) -> None:
        """
        Confirm the final participant list.
        IDEMPOTENT: Safe to call multiple times.

        Args:
            tournament: Tournament instance
            actor: User performing the action

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If conditions are not met
        """
        if not TournamentRegistrationService._is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą zatwierdzić skład.')

        # Lock tournament row to prevent race conditions
        tournament = Tournament.objects.select_for_update().get(pk=tournament.pk)

        # Idempotency: If already confirmed, return success
        if tournament.status == 'participants_confirmed':
            return

        if tournament.status != 'registration_closed':
            raise ValidationError('Można zatwierdzić skład tylko po zamknięciu zapisów.')

        # Count confirmed participants
        confirmed_count = Participant.objects.filter(
            tournament=tournament,
            status='confirmed'
        ).count()

        if confirmed_count < tournament.min_participants:
            raise ValidationError(
                f'Zbyt mała liczba uczestników. Minimum: {tournament.min_participants}, obecnie: {confirmed_count}.'
            )

        tournament.status = 'participants_confirmed'
        tournament.updated_by = actor
        tournament.save()

        # Log event (use get_or_create to avoid duplicate logs)
        TournamentEventLog.objects.get_or_create(
            tournament=tournament,
            event_type='participants_confirmed',
            defaults={
                'actor': actor,
                'payload': {
                    'confirmed_count': confirmed_count,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )
