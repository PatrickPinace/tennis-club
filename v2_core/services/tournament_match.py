"""
Service layer for tournament match management and results.
Implements business logic from turnieje.md specification.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from typing import Dict, Any, Optional

from v2_core.models import (
    Tournament, Participant, TournamentMatch, TournamentEventLog, TournamentManager
)


class TournamentMatchService:
    """Service for managing tournament matches and results."""

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
    def _determine_winner(
        set1_p1: int, set1_p2: int,
        set2_p1: int, set2_p2: int,
        set3_p1: Optional[int], set3_p2: Optional[int],
        participant1: Participant, participant2: Participant
    ) -> Participant:
        """Determine match winner based on sets won."""
        p1_sets = 0
        p2_sets = 0

        if set1_p1 > set1_p2:
            p1_sets += 1
        elif set1_p2 > set1_p1:
            p2_sets += 1

        if set2_p1 > set2_p2:
            p1_sets += 1
        elif set2_p2 > set2_p1:
            p2_sets += 1

        if set3_p1 is not None and set3_p2 is not None:
            if set3_p1 > set3_p2:
                p1_sets += 1
            elif set3_p2 > set3_p1:
                p2_sets += 1

        if p1_sets > p2_sets:
            return participant1
        elif p2_sets > p1_sets:
            return participant2
        else:
            raise ValidationError('Wynik jest remisowy. Jeden z graczy musi wygrać więcej setów.')

    @staticmethod
    def _advance_winner_to_next_match(match: TournamentMatch, winner: Participant) -> None:
        """Advance winner to the next round match."""
        # Find matches where this match is a source
        next_matches = TournamentMatch.objects.filter(
            tournament=match.tournament,
            source_match_1=match
        ) | TournamentMatch.objects.filter(
            tournament=match.tournament,
            source_match_2=match
        )

        for next_match in next_matches:
            if next_match.source_match_1 == match:
                next_match.player1_participant = winner
            elif next_match.source_match_2 == match:
                next_match.player2_participant = winner

            # Update status if both players are known
            if next_match.player1_participant and next_match.player2_participant:
                next_match.status = 'ready'

            next_match.save()

    @staticmethod
    @transaction.atomic
    def report_result(
        match: TournamentMatch,
        result_data: Dict[str, Any],
        actor: User
    ) -> TournamentMatch:
        """
        Report match result and advance winner.
        Protected against race conditions with row-level locking.

        Args:
            match: TournamentMatch instance
            result_data: Dictionary with set scores
            actor: User reporting the result

        Returns:
            Updated TournamentMatch instance

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If result is invalid
        """
        tournament = match.tournament

        if not TournamentMatchService._is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą raportować wyniki.')

        # Lock match row to prevent race conditions
        match = TournamentMatch.objects.select_for_update().get(pk=match.pk)

        # Check if already completed (idempotency check)
        if match.status in ['completed', 'walkover']:
            # Already completed - return existing match without error
            return match

        if not match.player1_participant or not match.player2_participant:
            raise ValidationError('Obaj gracze muszą być znani aby raportować wynik.')

        # Extract set scores
        set1_p1 = result_data.get('set1_p1')
        set1_p2 = result_data.get('set1_p2')
        set2_p1 = result_data.get('set2_p1')
        set2_p2 = result_data.get('set2_p2')
        set3_p1 = result_data.get('set3_p1')
        set3_p2 = result_data.get('set3_p2')

        if set1_p1 is None or set1_p2 is None or set2_p1 is None or set2_p2 is None:
            raise ValidationError('Wyniki pierwszych dwóch setów są wymagane.')

        # Determine winner
        winner = TournamentMatchService._determine_winner(
            set1_p1, set1_p2, set2_p1, set2_p2, set3_p1, set3_p2,
            match.player1_participant, match.player2_participant
        )
        loser = match.player2_participant if winner == match.player1_participant else match.player1_participant

        # Update match
        match.set1_p1 = set1_p1
        match.set1_p2 = set1_p2
        match.set2_p1 = set2_p1
        match.set2_p2 = set2_p2
        match.set3_p1 = set3_p1
        match.set3_p2 = set3_p2
        match.winner_participant = winner
        match.loser_participant = loser
        match.status = 'completed'
        match.completed_at = timezone.now()
        match.save()

        # Advance winner to next match
        TournamentMatchService._advance_winner_to_next_match(match, winner)

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='match_result',
            actor=actor,
            payload={
                'match_id': match.id,
                'round': match.round_number,
                'winner_id': winner.id,
                'winner_name': winner.display_name,
                'score': f"{set1_p1}-{set1_p2}, {set2_p1}-{set2_p2}" + (
                    f", {set3_p1}-{set3_p2}" if set3_p1 is not None else ""
                )
            }
        )

        return match

    @staticmethod
    @transaction.atomic
    def handle_participant_withdrawal(
        tournament: Tournament,
        participant: Participant,
        actor: User
    ) -> None:
        """
        Handle participant withdrawal by setting walkover for their next match.

        Args:
            tournament: Tournament instance
            participant: Withdrawn Participant
            actor: User performing the action
        """
        # Find participant's next unfinished match
        next_match = TournamentMatch.objects.filter(
            tournament=tournament,
            status__in=['scheduled', 'ready'],
        ).filter(
            player1_participant=participant
        ).first() or TournamentMatch.objects.filter(
            tournament=tournament,
            status__in=['scheduled', 'ready'],
        ).filter(
            player2_participant=participant
        ).first()

        if not next_match:
            return  # No active match to walkover

        # Determine opponent
        opponent = (
            next_match.player2_participant
            if next_match.player1_participant == participant
            else next_match.player1_participant
        )

        if not opponent:
            # No opponent yet, just mark match as cancelled
            next_match.status = 'cancelled'
            next_match.walkover_reason = f'Wycofanie się uczestnika: {participant.display_name}'
            next_match.save()
            return

        # Set walkover
        next_match.status = 'walkover'
        next_match.winner_participant = opponent
        next_match.loser_participant = participant
        next_match.walkover_reason = f'Wycofanie się uczestnika: {participant.display_name}'
        next_match.completed_at = timezone.now()
        next_match.save()

        # Advance opponent to next match
        TournamentMatchService._advance_winner_to_next_match(next_match, opponent)

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='match_walkover',
            actor=actor,
            payload={
                'match_id': next_match.id,
                'withdrawn_participant': participant.display_name,
                'advanced_participant': opponent.display_name
            }
        )

    @staticmethod
    @transaction.atomic
    def finish_tournament(tournament: Tournament, actor: User) -> None:
        """
        Finish the tournament and calculate final positions.
        IDEMPOTENT: Safe to call multiple times.

        Args:
            tournament: Tournament instance
            actor: User performing the action

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If tournament cannot be finished
        """
        if not TournamentMatchService._is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą zakończyć turniej.')

        # Lock tournament row to prevent race conditions
        tournament = Tournament.objects.select_for_update().get(pk=tournament.pk)

        # Idempotency: If already finished, return success
        if tournament.status == 'finished':
            return

        if tournament.status != 'in_progress':
            raise ValidationError('Można zakończyć tylko turniej w trakcie.')

        # Check if all matches are completed
        unfinished_matches = TournamentMatch.objects.filter(
            tournament=tournament,
            status__in=['scheduled', 'ready', 'in_progress']
        ).count()

        if unfinished_matches > 0:
            raise ValidationError(
                f'Nie można zakończyć turnieju. {unfinished_matches} meczów nie zostało rozliczonych.'
            )

        # Find final match (highest round number)
        final_match = TournamentMatch.objects.filter(
            tournament=tournament
        ).order_by('-round_number', '-match_number').first()

        if not final_match or not final_match.winner_participant:
            raise ValidationError('Nie można ustalić zwycięzcy turnieju.')

        # Set winner
        winner = final_match.winner_participant
        winner.status = 'winner'
        winner.final_position = 1
        winner.save()

        tournament.winner = winner
        tournament.status = 'finished'
        tournament.finished_at = timezone.now()
        tournament.updated_by = actor
        tournament.save()

        # Calculate other positions (simplified - runner-up gets 2nd place)
        if final_match.loser_participant:
            runner_up = final_match.loser_participant
            runner_up.final_position = 2
            runner_up.save()

        # Log event (use get_or_create to avoid duplicate logs)
        TournamentEventLog.objects.get_or_create(
            tournament=tournament,
            event_type='tournament_finished',
            defaults={
                'actor': actor,
                'payload': {
                    'winner_id': winner.id,
                    'winner_name': winner.display_name,
                    'timestamp': timezone.now().isoformat()
                }
            }
        )

        # Award ranking points (will be implemented in separate service)
        # from v2_core.services.tournament_settlement import TournamentSettlementService
        # TournamentSettlementService.award_ranking_points(tournament)
