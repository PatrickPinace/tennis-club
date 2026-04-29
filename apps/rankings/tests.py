"""
Testy calculate_rankings() z meczami WDR (walkower).

Scenariusz:
- Turniej FIN, typ RND (SNG), ranga 1
- 2 graczy: A i B
- Mecz CMP: A wygrywa 6:3 6:2
- Mecz WDR: A wygrywa nad B (walkower w fikcyjnym 2. meczu)

Oczekiwania po fix:
- matches_played: A=2, B=2 (WDR wchodzi do licznika)
- matches_won: A=2, B=0
- sets_won/games_won: tylko z CMP (WDR nie dodaje statystyk setów/gemów)
- total_points: mnożniki z TournamentRankPoints, WDR liczy jako wygrana meczu
"""
from decimal import Decimal
import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import Tournament, Participant, TournamentsMatch, RoundRobinConfig
from apps.rankings.models import TournamentRankPoints
from apps.rankings.services.ranking_calculator import calculate_rankings


class RankingCalculatorWDRTest(TestCase):
    def setUp(self):
        self.org = User.objects.create_user(username='org_rank', password='pass')
        self.user_a = User.objects.create_user(username='rank_a', password='pass')
        self.user_b = User.objects.create_user(username='rank_b', password='pass')

        # TournamentRankPoints dla rangi 1
        self.trp = TournamentRankPoints.objects.create(
            rank=1,
            participation_bonus=0,
            match_win_multiplier=Decimal('1.0'),
            set_win_multiplier=Decimal('0.5'),
            set_loss_multiplier=Decimal('-0.5'),
            game_win_multiplier=Decimal('0.1'),
            game_loss_multiplier=Decimal('-0.1'),
        )

        self.tournament = Tournament.objects.create(
            name='Ranking WDR Test',
            tournament_type='RND',
            match_format='SNG',
            status='FIN',
            rank=1,
            created_by=self.org,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 31),
        )

        self.p_a = Participant.objects.create(
            tournament=self.tournament, user=self.user_a, display_name='A', status='ACT'
        )
        self.p_b = Participant.objects.create(
            tournament=self.tournament, user=self.user_b, display_name='B', status='ACT'
        )

        # Mecz CMP: A wygrywa 6:3 6:2
        self.match_cmp = TournamentsMatch.objects.create(
            tournament=self.tournament,
            participant1=self.p_a,
            participant2=self.p_b,
            winner=self.p_a,
            status='CMP',
            round_number=1, match_index=1,
            set1_p1_score=6, set1_p2_score=3,
            set2_p1_score=6, set2_p2_score=2,
        )

        # Mecz WDR: A wygrywa (B oddaje walkower)
        self.match_wdr = TournamentsMatch.objects.create(
            tournament=self.tournament,
            participant1=self.p_a,
            participant2=self.p_b,
            winner=self.p_a,
            status='WDR',
            round_number=2, match_index=1,
        )

    def _get_row(self, user):
        results = calculate_rankings(match_type='SNG', season=2026)
        for row in results:
            if row['user_id'] == user.pk:
                return row
        return None

    def test_wdr_counts_in_matches_played(self):
        row_a = self._get_row(self.user_a)
        row_b = self._get_row(self.user_b)
        self.assertIsNotNone(row_a, "A musi być w rankingu")
        self.assertIsNotNone(row_b, "B musi być w rankingu (ma mecze)")
        self.assertEqual(row_a['matches_played'], 2, "A rozegrał 2 mecze (CMP + WDR)")
        self.assertEqual(row_b['matches_played'], 2, "B rozegrał 2 mecze (CMP + WDR)")

    def test_wdr_counts_in_matches_won(self):
        row_a = self._get_row(self.user_a)
        row_b = self._get_row(self.user_b)
        self.assertEqual(row_a['matches_won'], 2, "A wygrał 2 mecze (CMP + WDR)")
        self.assertEqual(row_b['matches_won'], 0, "B nie wygrał żadnego meczu")

    def test_wdr_does_not_add_sets_to_ranking(self):
        row_a = self._get_row(self.user_a)
        row_b = self._get_row(self.user_b)
        # A: 2 wygrane sety (tylko z CMP)
        self.assertEqual(row_a['sets_won'], 2, "A ma 2 wygrane sety — tylko z CMP")
        self.assertEqual(row_a['sets_lost'], 0)
        # B: 2 przegrane sety (tylko z CMP)
        self.assertEqual(row_b['sets_won'], 0)
        self.assertEqual(row_b['sets_lost'], 2, "B ma 2 przegrane sety — tylko z CMP")

    def test_wdr_does_not_add_games_to_ranking(self):
        row_a = self._get_row(self.user_a)
        row_b = self._get_row(self.user_b)
        # A: 12 wygranych gemów (6+6), 5 przegranych (3+2) — tylko z CMP
        self.assertEqual(row_a['games_won'], 12)
        self.assertEqual(row_a['games_lost'], 5)
        # B: 5 wygranych, 12 przegranych — tylko z CMP
        self.assertEqual(row_b['games_won'], 5)
        self.assertEqual(row_b['games_lost'], 12)

    def test_matches_won_greater_than_zero_appears_in_ranking(self):
        """B ma 0 wygranych ale 2 mecze rozegrane — musi się pojawić w rankingu."""
        results = calculate_rankings(match_type='SNG', season=2026)
        user_ids = [r['user_id'] for r in results]
        self.assertIn(self.user_a.pk, user_ids)
        self.assertIn(self.user_b.pk, user_ids, "B pojawia się w rankingu bo ma matches_played>0")
