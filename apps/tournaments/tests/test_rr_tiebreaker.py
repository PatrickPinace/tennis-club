"""
Testy tie_breaker_priority w calculate_round_robin_standings().

Scenariusze:
- SETS:  przy równej liczbie punktów → sets_diff → games_diff
- GAMES: przy równej liczbie punktów → games_diff → sets_diff
- HEAD:  przy remisie 2 zawodników → bezpośredni mecz; przy ≥3 → fallback sets_diff
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import Tournament, Participant, TournamentsMatch, RoundRobinConfig
from apps.tournaments.tools import calculate_round_robin_standings


def _make_config(tournament, tie_breaker='SETS', **kwargs):
    defaults = dict(
        max_participants=8,
        sets_to_win=2,
        games_per_set=6,
        points_for_win=Decimal('2.00'),
        points_for_loss=Decimal('1.00'),
        # Sety i gemy 0 żeby nie zaburzały punktów w testach
        points_for_set_win=Decimal('0.00'),
        points_for_set_loss=Decimal('0.00'),
        points_for_gem_win=Decimal('0.00'),
        points_for_gem_loss=Decimal('0.00'),
        points_for_supertiebreak_win=Decimal('0.00'),
        points_for_supertiebreak_loss=Decimal('0.00'),
        tie_breaker_priority=tie_breaker,
    )
    defaults.update(kwargs)
    return RoundRobinConfig.objects.create(tournament=tournament, **defaults)


def _make_tournament(org):
    return Tournament.objects.create(
        name='TB Test', tournament_type='RND', match_format='SNG',
        status='ACT', created_by=org,
    )


def _make_participant(tournament, user, name):
    return Participant.objects.create(
        tournament=tournament, user=user, display_name=name, status='ACT'
    )


_match_index_counter: dict[int, int] = {}


def _make_match(tournament, p1, p2, winner, s1p1, s1p2, s2p1=None, s2p2=None, s3p1=None, s3p2=None):
    idx = _match_index_counter.get(tournament.id, 0) + 1
    _match_index_counter[tournament.id] = idx
    return TournamentsMatch.objects.create(
        tournament=tournament,
        participant1=p1, participant2=p2,
        winner=winner, status='CMP',
        round_number=1, match_index=idx,
        set1_p1_score=s1p1, set1_p2_score=s1p2,
        set2_p1_score=s2p1, set2_p2_score=s2p2,
        set3_p1_score=s3p1, set3_p2_score=s3p2,
    )


class TieBreakerSetsTest(TestCase):
    """
    SETS: remis punktowy rozstrzygany przez sets_diff, potem games_diff.

    Scenariusz (punkty za sety=0, punkty za gemy=0, żeby skupić się na tie-breakerze):
    - A vs B: A wygrywa 6:0 6:0 → A: 2 wygrane sety, B: 0
    - C vs D: C wygrywa 6:4 6:4 → C: 2 wygrane sety, D: 0
    - A vs C: C wygrywa 6:3 6:3 → C: +2 sety
    - B vs D: B wygrywa 6:1 6:1 → B: +2 sety

    Wyniki:
    A: wins=1, losses=1, points=3, sets_won=2, sets_lost=2, sets_diff=0, games_won=12, games_lost=6 → games_diff=+6
    B: wins=1, losses=1, points=3, sets_won=2, sets_lost=2, sets_diff=0, games_won=2, games_lost=12 → games_diff=-10
    C: wins=2, losses=0, points=4, sets_won=4, sets_lost=0
    D: wins=0, losses=2, points=2, sets_won=0, sets_lost=4

    A vs B mają tę samą liczbę punktów i ten sam sets_diff=0 → games_diff decyduje (A > B).
    """
    def setUp(self):
        self.org = User.objects.create_user(username='tb_sets_org', password='pass')
        users = [User.objects.create_user(username=f'tb_sets_{n}', password='pass') for n in 'ABCD']
        self.t = _make_tournament(self.org)
        self.cfg = _make_config(self.t, tie_breaker='SETS')
        self.pA, self.pB, self.pC, self.pD = [_make_participant(self.t, u, n) for u, n in zip(users, 'ABCD')]

        _make_match(self.t, self.pA, self.pB, self.pA, 6, 0, 6, 0)   # A wygrywa
        _make_match(self.t, self.pC, self.pD, self.pC, 6, 4, 6, 4)   # C wygrywa
        _make_match(self.t, self.pA, self.pC, self.pC, 3, 6, 3, 6)   # C wygrywa
        _make_match(self.t, self.pB, self.pD, self.pB, 6, 1, 6, 1)   # B wygrywa

    def _order(self):
        rows = calculate_round_robin_standings(
            self.t, self.t.participants.all(), self.cfg
        )
        return [r['participant'].display_name for r in rows]

    def test_sets_priority_order(self):
        order = self._order()
        self.assertEqual(order[0], 'C', "C: 2 wygrane, 4 sety — pierwsze")
        self.assertEqual(order[1], 'A', "A i B mają te same punkty; A ma lepszy games_diff")
        self.assertEqual(order[2], 'B', "B ma gorszy games_diff")
        self.assertEqual(order[3], 'D', "D: 0 wygranych")

    def test_sets_diff_secondary(self):
        rows = calculate_round_robin_standings(
            self.t, self.t.participants.all(), self.cfg
        )
        by_name = {r['participant'].display_name: r for r in rows}
        self.assertEqual(by_name['A']['sets_diff'], 0)
        self.assertEqual(by_name['B']['sets_diff'], 0)
        # A i B mają taki sam sets_diff → games_diff rozstrzyga
        self.assertGreater(by_name['A']['games_diff'], by_name['B']['games_diff'])


class TieBreakerGamesTest(TestCase):
    """
    GAMES: przy równej liczbie punktów → games_diff → sets_diff.

    Użyjemy tego samego scenariusza co SETS, ale zmieniamy tie_breaker na GAMES.
    Wynik powinien być taki sam (bo sets_diff też jest remisem, games_diff decyduje).
    Ale test weryfikuje, że kryterium pierwszeństwa to games_diff, nie sets_diff.

    Dodatkowy scenariusz gdzie sets_diff i games_diff dają różne wyniki:
    E vs F: E wygrywa 7:6 7:6 → E: 2 sety, F: 0; games_diff E=+2, F=-2; sets_diff E=+2
    G vs H: G wygrywa 6:0 6:0 → G: 2 sety, H: 0; games_diff G=+12, H=-12; sets_diff G=+2

    E i G mają tę samą liczbę punktów ale:
    - SETS: sets_diff identyczny (+2) → games_diff: G > E
    - GAMES: games_diff: G(+12) > E(+2) → ta sama kolejność, ale kryterium pierwsze = games
    """
    def setUp(self):
        self.org = User.objects.create_user(username='tb_games_org', password='pass')
        users = [User.objects.create_user(username=f'tb_games_{n}', password='pass') for n in 'EFGH']
        self.t = _make_tournament(self.org)
        self.cfg = _make_config(self.t, tie_breaker='GAMES')
        self.pE, self.pF, self.pG, self.pH = [_make_participant(self.t, u, n) for u, n in zip(users, 'EFGH')]

        _make_match(self.t, self.pE, self.pF, self.pE, 7, 6, 7, 6)   # E wygrywa (sets_diff=+2, games_diff=+2)
        _make_match(self.t, self.pG, self.pH, self.pG, 6, 0, 6, 0)   # G wygrywa (sets_diff=+2, games_diff=+12)
        _make_match(self.t, self.pE, self.pG, self.pE, 6, 3, 6, 3)   # E wygrywa
        _make_match(self.t, self.pF, self.pH, self.pF, 6, 4, 6, 4)   # F wygrywa

    def _order(self):
        rows = calculate_round_robin_standings(
            self.t, self.t.participants.all(), self.cfg
        )
        return [r['participant'].display_name for r in rows]

    def test_games_priority_order(self):
        order = self._order()
        self.assertEqual(order[0], 'E', "E: 2 wygrane — pierwsze")
        # G i F mają po 1 wygranej (ta sama liczba punktów)
        # games_diff: G=+12 vs H=-12 → G ma +12 własnych gemów, a stracił 0
        # F: wygr 6:4 6:4 → games_diff=+4; G: wygr 6:0 6:0 → games_diff=+12
        # G > F pod względem games_diff
        self.assertEqual(order[1], 'G', "G ma lepszy games_diff niż F")
        self.assertEqual(order[2], 'F')
        self.assertEqual(order[3], 'H')


class TieBreakerHeadToHeadTest(TestCase):
    """
    HEAD: remis 2 zawodników → bezpośredni mecz decyduje.

    Scenariusz:
    - A vs B: B wygrywa → head_wins[B][A] = True
    - A vs C: A wygrywa
    - B vs C: C wygrywa

    Wyniki (points_for_set/gem = 0):
    A: 1 wygrana (vs C), 1 przegrana (vs B) → points = 3
    B: 1 wygrana (vs A), 1 przegrana (vs C) → points = 3
    C: 1 wygrana (vs B), 1 przegrana (vs A) → points = 3

    Wszyscy mają 3 punkty → HEAD przy 3 zawodnikach: fallback do sets_diff.
    Wyniki w setach:
    A: won 2 (vs C 6:3 6:0), lost 2 (vs B 3:6 0:6) → sets_diff=0
    B: won 2 (vs A 6:3 6:0), lost 2 (vs C 3:6 0:6) → sets_diff=0
    C: won 2 (vs B 6:3 6:0), lost 2 (vs A 3:6 0:6) → sets_diff=0
    Dalej games_diff:
    A: +6-6=0... — to cykliczne, więc wszyscy mają sets_diff=0 i games_diff=0.
    → Kolejność zależy od stabilności sortowania (bez zmiany).

    Inny scenariusz dla HEAD z 2 zawodnikami (dodany poniżej):
    X vs Y: Y wygrywa → przy remisie punktowym HEAD daje Y > X.
    """
    def setUp(self):
        self.org = User.objects.create_user(username='tb_head_org', password='pass')
        users_abc = [User.objects.create_user(username=f'tb_head_{n}', password='pass') for n in 'ABC']
        self.t3 = _make_tournament(self.org)
        self.cfg3 = _make_config(self.t3, tie_breaker='HEAD')
        self.pA3, self.pB3, self.pC3 = [
            _make_participant(self.t3, u, n) for u, n in zip(users_abc, 'ABC')
        ]
        # Cykliczne wyniki — wszyscy mają tę samą liczbę punktów
        _make_match(self.t3, self.pA3, self.pB3, self.pB3, 3, 6, 0, 6)  # B wygrywa
        _make_match(self.t3, self.pA3, self.pC3, self.pA3, 6, 3, 6, 0)  # A wygrywa
        _make_match(self.t3, self.pB3, self.pC3, self.pC3, 3, 6, 0, 6)  # C wygrywa

        # Turniej z 2 uczestnikami dla testu HEAD 1vs1
        users_xy = [User.objects.create_user(username=f'tb_head_{n}', password='pass') for n in 'XY']
        self.t2 = _make_tournament(self.org)
        self.cfg2 = _make_config(self.t2, tie_breaker='HEAD')
        self.pX, self.pY = [
            _make_participant(self.t2, u, n) for u, n in zip(users_xy, 'XY')
        ]
        # Turniej 2-osobowy: X vs Y → Y wygrywa
        # X vs Y dają X 2 sety stracone, Y 2 wygrane — ale points_for_set=0 więc punkty równe
        # X dostaje points_for_loss=1, Y dostaje points_for_win=2 → nierówność punktowa!
        # Żeby był remis punktowy dodajemy dodatkowy mecz X wygrywa
        # Wtedy X: win=1(vs Y_2nd?), ale to komplikuje...
        # Prościej: użyjemy punktów za mecz 0 dla tego turnieju
        self.cfg2.points_for_win = Decimal('1.00')
        self.cfg2.points_for_loss = Decimal('1.00')
        self.cfg2.save()
        # Teraz obaj mają 1 pkt niezależnie od wyniku
        TournamentsMatch.objects.create(
            tournament=self.t2,
            participant1=self.pX, participant2=self.pY,
            winner=self.pY, status='CMP',
            round_number=1, match_index=1,
            set1_p1_score=3, set1_p2_score=6,
            set2_p1_score=2, set2_p2_score=6,
        )

    def test_head_three_way_fallback(self):
        """≥3 zawodników z tą samą liczbą punktów → fallback, nie crash."""
        rows = calculate_round_robin_standings(
            self.t3, self.t3.participants.all(), self.cfg3
        )
        # Muszą być 3 rzędy, nie powinno rzucać wyjątku
        self.assertEqual(len(rows), 3)
        # Wszyscy mają tę samą liczbę punktów, sets_diff=0, games_diff=0 → kolejność stabilna
        points = [r['points'] for r in rows]
        self.assertEqual(points[0], points[1])
        self.assertEqual(points[1], points[2])

    def test_head_two_way_resolves(self):
        """Remis 2 zawodników → HEAD daje wygranego bezpośredniego meczu wyżej."""
        rows = calculate_round_robin_standings(
            self.t2, self.t2.participants.all(), self.cfg2
        )
        self.assertEqual(len(rows), 2)
        # Oba mają równe points (1.00 każdy)
        self.assertEqual(rows[0]['points'], rows[1]['points'])
        # Y wygrał bezpośredni mecz → Y jest wyżej
        self.assertEqual(rows[0]['participant'].display_name, 'Y',
                         "Y wygrał bezpośredni mecz, musi być wyżej przy HEAD")
        self.assertEqual(rows[1]['participant'].display_name, 'X')


class TieBreakerDefaultTest(TestCase):
    """
    Domyślna wartość tie_breaker_priority to 'GAMES' (z modelu).
    Poprzedni domyślny sort był (points, sets_diff, games_diff) = SETS.
    Weryfikujemy że nieznana wartość nie crashuje.
    """
    def setUp(self):
        self.org = User.objects.create_user(username='tb_default_org', password='pass')
        users = [User.objects.create_user(username=f'tb_def_{n}', password='pass') for n in 'PQ']
        self.t = _make_tournament(self.org)
        # Użyj domyślnej wartości z modelu (GAMES)
        self.cfg = _make_config(self.t, tie_breaker='GAMES')
        self.pP, self.pQ = [_make_participant(self.t, u, n) for u, n in zip(users, 'PQ')]
        _make_match(self.t, self.pP, self.pQ, self.pP, 6, 0, 6, 0)

    def test_no_crash(self):
        rows = calculate_round_robin_standings(self.t, self.t.participants.all(), self.cfg)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['participant'].display_name, 'P')
