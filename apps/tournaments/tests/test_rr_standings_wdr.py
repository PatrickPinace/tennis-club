"""
Testy calculate_round_robin_standings() z meczami WDR (walkower).

Scenariusz:
- Turniej RR z 3 uczestnikami: A, B, C
- Mecz A vs B: CMP, wynik 6:3 6:2, wygrał A
- Mecz A vs C: WDR, wygrał A (walkower — C się wycofał)
- Mecz B vs C: WDR, wygrał B (walkower)

Oczekiwania po fix:
- WDR liczy się jako wygrany/przegrany mecz (points_for_win / points_for_loss)
- WDR nie nalicza statystyk setów ani gemów
- Kolejność: A > B > C (A: 2 wygrane, B: 1 wygrana, C: 0 wygranych)
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import Tournament, Participant, TournamentsMatch, RoundRobinConfig
from apps.tournaments.tools import calculate_round_robin_standings


class RRStandingsWDRTest(TestCase):
    def setUp(self):
        self.org = User.objects.create_user(username='org_wdr', password='pass')
        self.user_a = User.objects.create_user(username='player_a', password='pass')
        self.user_b = User.objects.create_user(username='player_b', password='pass')
        self.user_c = User.objects.create_user(username='player_c', password='pass')

        self.tournament = Tournament.objects.create(
            name='WDR Test Liga',
            tournament_type='RND',
            match_format='SNG',
            status='ACT',
            created_by=self.org,
        )

        self.config = RoundRobinConfig.objects.create(
            tournament=self.tournament,
            max_participants=8,
            sets_to_win=2,
            games_per_set=6,
            points_for_win=Decimal('2.00'),
            points_for_loss=Decimal('1.00'),
            points_for_set_win=Decimal('0.50'),
            points_for_set_loss=Decimal('0.00'),
            points_for_gem_win=Decimal('0.10'),
            points_for_gem_loss=Decimal('-0.10'),
            points_for_supertiebreak_win=Decimal('0.05'),
            points_for_supertiebreak_loss=Decimal('-0.05'),
        )

        self.p_a = Participant.objects.create(tournament=self.tournament, user=self.user_a, display_name='A', status='ACT')
        self.p_b = Participant.objects.create(tournament=self.tournament, user=self.user_b, display_name='B', status='ACT')
        self.p_c = Participant.objects.create(tournament=self.tournament, user=self.user_c, display_name='C', status='ACT')

        # Mecz CMP: A vs B, wynik 6:3 6:2 → wygrał A
        self.match_ab = TournamentsMatch.objects.create(
            tournament=self.tournament,
            participant1=self.p_a,
            participant2=self.p_b,
            winner=self.p_a,
            status='CMP',
            round_number=1, match_index=1,
            set1_p1_score=6, set1_p2_score=3,
            set2_p1_score=6, set2_p2_score=2,
        )

        # Mecz WDR: A vs C, wygrał A (walkower)
        self.match_ac = TournamentsMatch.objects.create(
            tournament=self.tournament,
            participant1=self.p_a,
            participant2=self.p_c,
            winner=self.p_a,
            status='WDR',
            round_number=1, match_index=2,
            # brak wyników setów — WDR
        )

        # Mecz WDR: B vs C, wygrał B (walkower)
        self.match_bc = TournamentsMatch.objects.create(
            tournament=self.tournament,
            participant1=self.p_b,
            participant2=self.p_c,
            winner=self.p_b,
            status='WDR',
            round_number=2, match_index=1,
        )

    def _standings_by_name(self):
        participants = self.tournament.participants.all()
        rows = calculate_round_robin_standings(self.tournament, participants, self.config)
        return {r['participant'].display_name: r for r in rows}

    def test_wdr_counts_as_match_played(self):
        s = self._standings_by_name()
        self.assertEqual(s['A']['matches_played'], 2, "A rozegrał 2 mecze (1 CMP + 1 WDR)")
        self.assertEqual(s['B']['matches_played'], 2, "B rozegrał 2 mecze (1 CMP + 1 WDR)")
        self.assertEqual(s['C']['matches_played'], 2, "C rozegrał 2 mecze (2×WDR)")

    def test_wdr_counts_as_win_loss(self):
        s = self._standings_by_name()
        self.assertEqual(s['A']['wins'], 2)
        self.assertEqual(s['A']['losses'], 0)
        self.assertEqual(s['B']['wins'], 1)
        self.assertEqual(s['B']['losses'], 1)
        self.assertEqual(s['C']['wins'], 0)
        self.assertEqual(s['C']['losses'], 2)

    def test_wdr_does_not_add_sets(self):
        s = self._standings_by_name()
        # A ma sety tylko z meczu CMP (A vs B: 2 wygranych setów)
        self.assertEqual(s['A']['sets_won'], 2, "A ma 2 wygrane sety (tylko z CMP)")
        self.assertEqual(s['A']['sets_lost'], 0)
        # B: przegrał 2 sety z A (CMP), WDR vs C nie daje setów
        self.assertEqual(s['B']['sets_won'], 0)
        self.assertEqual(s['B']['sets_lost'], 2)
        # C: żadnych setów (oba mecze to WDR)
        self.assertEqual(s['C']['sets_won'], 0)
        self.assertEqual(s['C']['sets_lost'], 0)

    def test_wdr_does_not_add_games(self):
        s = self._standings_by_name()
        # A ma gemy tylko z CMP (6+6=12 wygranych, 3+2=5 przegranych)
        self.assertEqual(s['A']['games_won'], 12)
        self.assertEqual(s['A']['games_lost'], 5)
        # B ma gemy z CMP (3+2=5 wygranych, 6+6=12 przegranych)
        self.assertEqual(s['B']['games_won'], 5)
        self.assertEqual(s['B']['games_lost'], 12)
        # C: żadnych gemów
        self.assertEqual(s['C']['games_won'], 0)
        self.assertEqual(s['C']['games_lost'], 0)

    def test_wdr_points_only_match_points(self):
        s = self._standings_by_name()
        # A: 1 CMP wygrany + 1 WDR wygrany + sety (2×0.50) + gemy
        # CMP pkt za mecz: 2.00, WDR pkt za mecz: 2.00
        # CMP sety: 2 × 0.50 = 1.00, B sety: 2 × 0.00 = 0.00
        # CMP gemy A: 12 × 0.10 + 5 × (-0.10) = 1.20 - 0.50 = 0.70
        expected_a = Decimal('2.00') + Decimal('2.00') + Decimal('1.00') + Decimal('0.70')
        self.assertAlmostEqual(float(s['A']['points']), float(expected_a), places=2,
                               msg=f"Punkty A: oczekiwano {expected_a}, dostaliśmy {s['A']['points']}")

        # C: 2 WDR przegranych — tylko points_for_loss × 2
        expected_c = Decimal('1.00') + Decimal('1.00')
        self.assertAlmostEqual(float(s['C']['points']), float(expected_c), places=2,
                               msg=f"Punkty C: oczekiwano {expected_c}, dostaliśmy {s['C']['points']}")

    def test_standings_order(self):
        participants = self.tournament.participants.all()
        rows = calculate_round_robin_standings(self.tournament, participants, self.config)
        names = [r['participant'].display_name for r in rows]
        self.assertEqual(names[0], 'A', "A powinien być na 1. miejscu (2 wygrane)")
        self.assertIn(names[1], ['B'], "B powinien być na 2. miejscu")
        self.assertEqual(names[2], 'C', "C powinien być na ostatnim miejscu (0 wygranych)")

    def test_cmp_logic_unchanged(self):
        """Logika CMP jest nienaruszona — A vs B musi zachować stare zachowanie."""
        s = self._standings_by_name()
        # A: wygrane sety z CMP to 2 (6:3 i 6:2)
        # Sprawdzamy przez porównanie z oczekiwanym rezultatem bez WDR
        # Gdyby WDR nie było, A miałby: wins=1, matches_played=1, sets_won=2, games_won=12
        # Po WDR: wins=2, matches_played=2, sets_won=2 (niezmienne), games_won=12 (niezmienne)
        self.assertEqual(s['A']['sets_won'], 2, "Sety A z CMP nie mogą być zmienione przez WDR fix")
        self.assertEqual(s['A']['games_won'], 12, "Gemy A z CMP nie mogą być zmienione przez WDR fix")
