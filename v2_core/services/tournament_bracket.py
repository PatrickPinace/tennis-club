"""
Service layer for tournament bracket generation (single elimination & round robin).
Implements business logic from turnieje.md specification.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from typing import List
from itertools import combinations
import math

from v2_core.models import (
    Tournament, Participant, TournamentMatch, TournamentEventLog, TournamentManager
)


class TournamentBracketService:
    """Service for generating and managing tournament brackets."""

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
    def _get_next_power_of_two(n: int) -> int:
        """Get the next power of 2 greater than or equal to n."""
        return 2 ** math.ceil(math.log2(n))

    @staticmethod
    def _apply_seeding(participants: List[Participant]) -> List[Participant]:
        """
        Apply seeding to participants for bracket generation.
        Uses standard seeding pattern for single elimination.
        """
        seeded = []
        unseeded = []

        for p in participants:
            if p.seed:
                seeded.append(p)
            else:
                unseeded.append(p)

        # Sort seeded by seed number
        seeded.sort(key=lambda x: x.seed)

        # Combine: seeded first, then unseeded
        return seeded + unseeded

    @staticmethod
    @transaction.atomic
    def generate_bracket(tournament: Tournament, actor: User) -> List[TournamentMatch]:
        """
        Generate single elimination bracket for the tournament.
        IDEMPOTENT: Safe to call multiple times (returns existing bracket if already generated).

        Args:
            tournament: Tournament instance
            actor: User performing the action

        Returns:
            List of created TournamentMatch instances

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If bracket cannot be generated
        """
        if not TournamentBracketService._is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą wygenerować drabinkę.')

        # Lock tournament row to prevent race conditions
        tournament = Tournament.objects.select_for_update().get(pk=tournament.pk)

        # Idempotency: If bracket already exists, return existing matches
        existing_matches = list(TournamentMatch.objects.filter(tournament=tournament).order_by('round_number', 'match_number'))
        if existing_matches:
            # Already generated, return existing
            if tournament.status != 'bracket_ready':
                tournament.status = 'bracket_ready'
                tournament.updated_by = actor
                tournament.save()
            return existing_matches

        if tournament.status != 'participants_confirmed':
            raise ValidationError('Drabinkę można wygenerować tylko po zatwierdzeniu składu.')

        if tournament.tournament_type not in ['single_elimination', 'round_robin']:
            raise ValidationError('Obsługiwane typy: Single Elimination i Round Robin.')

        # Get confirmed participants
        participants = list(
            Participant.objects.filter(
                tournament=tournament,
                status='confirmed'
            ).select_related('user')
        )

        if len(participants) < tournament.min_participants:
            raise ValidationError(
                f'Zbyt mało uczestników. Minimum: {tournament.min_participants}, obecnie: {len(participants)}.'
            )

        matches = []

        # ROUND ROBIN (Liga - każdy z każdym)
        if tournament.tournament_type == 'round_robin':
            # Wygeneruj wszystkie możliwe pary
            match_number = 1
            for player1, player2 in combinations(participants, 2):
                match = TournamentMatch.objects.create(
                    tournament=tournament,
                    round_number=1,  # Wszystkie mecze w rundzie 1
                    match_number=match_number,
                    bracket_position=match_number,
                    player1_participant=player1,
                    player2_participant=player2,
                    status='scheduled',
                    source_match_1=None,
                    source_match_2=None
                )
                matches.append(match)
                match_number += 1

            # Update tournament status
            tournament.status = 'bracket_ready'
            tournament.updated_by = actor
            tournament.save()

            # Log event
            TournamentEventLog.objects.create(
                tournament=tournament,
                event_type='bracket_generated',
                actor=actor,
                payload={
                    'tournament_type': 'round_robin',
                    'num_participants': len(participants),
                    'num_matches': len(matches),
                    'timestamp': timezone.now().isoformat()
                }
            )

        # SINGLE ELIMINATION (Puchar)
        else:
            # Apply seeding if enabled
            if tournament.config.use_seeding:
                participants = TournamentBracketService._apply_seeding(participants)

            # Calculate bracket size (next power of 2)
            bracket_size = TournamentBracketService._get_next_power_of_two(len(participants))
            num_rounds = int(math.log2(bracket_size))

            bracket_position = 1

            # Round 1 - seed participants
            round_1_matches = bracket_size // 2
            for i in range(round_1_matches):
                p1 = participants[i] if i < len(participants) else None
                p2 = participants[bracket_size - 1 - i] if (bracket_size - 1 - i) < len(participants) else None

                match = TournamentMatch.objects.create(
                    tournament=tournament,
                    round_number=1,
                    match_number=i + 1,
                    bracket_position=bracket_position,
                    player1_participant=p1,
                    player2_participant=p2,
                    status='scheduled' if (p1 and p2) else 'ready',
                    source_match_1=None,
                    source_match_2=None
                )
                matches.append(match)
                bracket_position += 1

            # Create subsequent rounds (initially without participants)
            for round_num in range(2, num_rounds + 1):
                num_matches = bracket_size // (2 ** round_num)
                for match_num in range(num_matches):
                    source_1_idx = match_num * 2
                    source_2_idx = match_num * 2 + 1

                    # Find source matches from previous round
                    prev_round_matches = [m for m in matches if m.round_number == round_num - 1]
                    source_match_1 = prev_round_matches[source_1_idx] if source_1_idx < len(prev_round_matches) else None
                    source_match_2 = prev_round_matches[source_2_idx] if source_2_idx < len(prev_round_matches) else None

                    match = TournamentMatch.objects.create(
                        tournament=tournament,
                        round_number=round_num,
                        match_number=match_num + 1,
                        bracket_position=bracket_position,
                        player1_participant=None,
                        player2_participant=None,
                        status='scheduled',
                        source_match_1=source_match_1,
                        source_match_2=source_match_2
                    )
                    matches.append(match)
                    bracket_position += 1

            # Update tournament status
            tournament.status = 'bracket_ready'
            tournament.updated_by = actor
            tournament.save()

            # Log event
            TournamentEventLog.objects.create(
                tournament=tournament,
                event_type='bracket_generated',
                actor=actor,
                payload={
                    'tournament_type': 'single_elimination',
                    'num_participants': len(participants),
                    'bracket_size': bracket_size,
                    'num_rounds': num_rounds,
                    'num_matches': len(matches),
                    'timestamp': timezone.now().isoformat()
                }
            )

        return matches

    @staticmethod
    @transaction.atomic
    def start_tournament(tournament: Tournament, actor: User) -> None:
        """
        Start the tournament (change status to in_progress).

        Args:
            tournament: Tournament instance
            actor: User performing the action

        Raises:
            PermissionDenied: If user is not a manager
            ValidationError: If tournament cannot be started
        """
        if not TournamentBracketService._is_tournament_manager(tournament, actor):
            raise PermissionDenied('Tylko managerowie turnieju mogą rozpocząć turniej.')

        if tournament.status != 'bracket_ready':
            raise ValidationError('Turniej można rozpocząć tylko gdy drabinka jest gotowa.')

        tournament.status = 'in_progress'
        tournament.updated_by = actor
        tournament.save()

        # Log event
        TournamentEventLog.objects.create(
            tournament=tournament,
            event_type='tournament_started',
            actor=actor,
            payload={'timestamp': timezone.now().isoformat()}
        )
