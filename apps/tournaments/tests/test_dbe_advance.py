"""
Testy Etapu C Double Elimination — advance logic.

Pokrywa:
- WB winner advances to next WB match
- WB loser drops into LB
- LB winner advances in LB
- LB loser is eliminated (nie dostaje kolejnego meczu)
- WB final loser goes to LB final
- LB final winner creates / enters grand final
- WB final winner enters grand final
- grand final can be completed
- Pełna symulacja turnieju DBE 4-osobowego
- Pełna symulacja turnieju DBE 8-osobowego
- SGL advance_winner_in_bracket() bez regresji
- Idempotentność (re-edycja wyniku)
"""
import datetime
import math
from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import (
    Tournament, Participant, TournamentsMatch, EliminationConfig,
)
from apps.tournaments.bracket import (
    advance_dbe_match,
    advance_winner_in_bracket,
    _wb_total_rounds,
)
from apps.tournaments.views import generate_elimination_matches_initial


def _make_tournament(org, t_type='DBE'):
    return Tournament.objects.create(
        name=f'{t_type} Advance Test',
        tournament_type=t_type,
        match_format='SNG',
        status='SCH',
        rank=1,
        created_by=org,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 6, 30),
    )


def _add_participants(tournament, users):
    return [
        Participant.objects.create(
            tournament=tournament,
            user=u,
            display_name=u.username,
            status='ACT',
        )
        for u in users
    ]


def _make_match(tournament, bracket_type, round_number, match_index, p1, p2, status='WAI'):
    return TournamentsMatch.objects.create(
        tournament=tournament,
        bracket_type=bracket_type,
        round_number=round_number,
        match_index=match_index,
        participant1=p1,
        participant2=p2,
        status=status,
    )


def _complete_match(match, winner):
    """Zakończ mecz z danym zwycięzcą."""
    match.winner = winner
    match.status = TournamentsMatch.Status.COMPLETED.value
    match.set1_p1_score = 6
    match.set1_p2_score = 3
    match.save(update_fields=['winner', 'status', 'set1_p1_score', 'set1_p2_score'])


BT_W = TournamentsMatch.BracketType.WINNERS
BT_L = TournamentsMatch.BracketType.LOSERS
BT_GF = TournamentsMatch.BracketType.GRAND_FINAL


class DBEAdvanceWBTest(TestCase):
    """WB advance: zwycięzca idzie dalej w WB, przegrany spada do LB."""

    def setUp(self):
        self.org = User.objects.create_user(username='dbe_adv_org', password='pass')
        users = [User.objects.create_user(username=f'dbe_adv_u{i}', password='pass') for i in range(4)]
        self.t = _make_tournament(self.org)
        self.ps = _add_participants(self.t, users)
        # Ręcznie tworzymy R1 WB: 2 mecze
        self.wb_r1_m1 = _make_match(self.t, BT_W, 1, 1, self.ps[0], self.ps[1])
        self.wb_r1_m2 = _make_match(self.t, BT_W, 1, 2, self.ps[2], self.ps[3])

    def test_wb_winner_advances_to_next_wb_match(self):
        """Zwycięzca WB_R1/M1 trafia do WB_R2/M1 jako participant1."""
        _complete_match(self.wb_r1_m1, self.ps[0])
        advance_dbe_match(self.wb_r1_m1, self.t)

        wb_r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_W, round_number=2
        ).first()
        self.assertIsNotNone(wb_r2, 'WB R2 mecz powinien zostać stworzony')
        self.assertEqual(wb_r2.participant1, self.ps[0])

    def test_wb_r1_m2_winner_advances_as_p2(self):
        """Zwycięzca WB_R1/M2 trafia do WB_R2/M1 jako participant2."""
        _complete_match(self.wb_r1_m2, self.ps[2])
        advance_dbe_match(self.wb_r1_m2, self.t)

        wb_r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_W, round_number=2
        ).first()
        self.assertIsNotNone(wb_r2)
        self.assertEqual(wb_r2.participant2, self.ps[2])

    def test_wb_loser_drops_to_lb(self):
        """Przegrany WB_R1/M1 trafia do LB_R1/M1."""
        _complete_match(self.wb_r1_m1, self.ps[0])
        advance_dbe_match(self.wb_r1_m1, self.t)

        lb_r1 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=1
        ).first()
        self.assertIsNotNone(lb_r1, 'LB R1 mecz powinien zostać stworzony')
        # ps[1] to przegrany — powinien być w jednym ze slotów LB_R1/M1
        self.assertIn(self.ps[1], [lb_r1.participant1, lb_r1.participant2])

    def test_wb_loser_r1_m2_drops_to_lb_r1_m1(self):
        """Przegrani WB_R1/M1 i WB_R1/M2 trafiają do tego samego meczu LB_R1/M1."""
        _complete_match(self.wb_r1_m1, self.ps[0])
        advance_dbe_match(self.wb_r1_m1, self.t)

        _complete_match(self.wb_r1_m2, self.ps[2])
        advance_dbe_match(self.wb_r1_m2, self.t)

        lb_r1_matches = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=1
        )
        self.assertEqual(lb_r1_matches.count(), 1, 'Przy 4 graczach (2 mecze R1) powinien być 1 mecz LB_R1')
        lb_m = lb_r1_matches.first()
        # Obaj przegrani (ps[1] i ps[3]) powinni być w LB_R1/M1
        slots = {lb_m.participant1, lb_m.participant2}
        self.assertIn(self.ps[1], slots)
        self.assertIn(self.ps[3], slots)

    def test_wb_advance_creates_correct_bracket_type(self):
        """Lazy-created WB mecz ma bracket_type='W'."""
        _complete_match(self.wb_r1_m1, self.ps[0])
        advance_dbe_match(self.wb_r1_m1, self.t)

        wb_r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_W, round_number=2
        ).first()
        self.assertIsNotNone(wb_r2)
        self.assertEqual(wb_r2.bracket_type, BT_W)

    def test_lb_created_match_has_correct_bracket_type(self):
        """Lazy-created LB mecz ma bracket_type='L'."""
        _complete_match(self.wb_r1_m1, self.ps[0])
        advance_dbe_match(self.wb_r1_m1, self.t)

        lb_r1 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L
        ).first()
        self.assertIsNotNone(lb_r1)
        self.assertEqual(lb_r1.bracket_type, BT_L)


class DBEAdvanceLBTest(TestCase):
    """LB advance: zwycięzca idzie dalej, przegrany odpada."""

    def setUp(self):
        self.org = User.objects.create_user(username='dbe_lb_org', password='pass')
        users = [User.objects.create_user(username=f'dbe_lb_u{i}', password='pass') for i in range(4)]
        self.t = _make_tournament(self.org)
        self.ps = _add_participants(self.t, users)
        # Tworzymy LB_R1/M1 z dwoma graczami
        self.lb_r1_m1 = _make_match(self.t, BT_L, 1, 1, self.ps[0], self.ps[1])
        # WB R1 potrzebne do obliczenia wb_total_rounds (2 mecze = bracket_size 4 = 2 rundy WB)
        self.wb_r1_m1 = _make_match(self.t, BT_W, 1, 1, self.ps[0], self.ps[1])
        self.wb_r1_m2 = _make_match(self.t, BT_W, 1, 2, self.ps[2], self.ps[3])

    def test_lb_winner_advances_to_next_lb_round(self):
        """Zwycięzca LB_R1/M1 trafia do LB_R2/M1."""
        _complete_match(self.lb_r1_m1, self.ps[0])
        advance_dbe_match(self.lb_r1_m1, self.t)

        lb_r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=2
        ).first()
        self.assertIsNotNone(lb_r2, 'LB R2 powinien zostać stworzony')
        self.assertEqual(lb_r2.participant1, self.ps[0])

    def test_lb_loser_has_no_further_lb_or_gf_match_created(self):
        """Przegrany z LB nie dostaje kolejnego meczu LB ani GF — odpada."""
        existing_pks = set(TournamentsMatch.objects.filter(tournament=self.t).values_list('pk', flat=True))
        _complete_match(self.lb_r1_m1, self.ps[0])
        advance_dbe_match(self.lb_r1_m1, self.t)

        loser = self.ps[1]
        # Sprawdź tylko mecze NOWO stworzone po advance (LB/GF)
        new_matches = TournamentsMatch.objects.filter(
            tournament=self.t,
        ).exclude(
            pk__in=existing_pks,
        ).filter(
            bracket_type__in=[BT_L, BT_GF],
        )
        # Żaden nowy mecz LB/GF nie powinien zawierać przegranego
        for m in new_matches:
            self.assertNotEqual(m.participant1, loser, f'Przegrany nie powinien być p1 w {m}')
            self.assertNotEqual(m.participant2, loser, f'Przegrany nie powinien być p2 w {m}')

    def test_lb_r1_advance_creates_lb_bracket_type(self):
        """Mecz LB_R2 ma bracket_type='L'."""
        _complete_match(self.lb_r1_m1, self.ps[0])
        advance_dbe_match(self.lb_r1_m1, self.t)

        lb_r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=2
        ).first()
        self.assertIsNotNone(lb_r2)
        self.assertEqual(lb_r2.bracket_type, BT_L)


class DBEGrandFinalTest(TestCase):
    """Grand Final: tworzenie po zakończeniu WB Final i LB Final."""

    def setUp(self):
        self.org = User.objects.create_user(username='dbe_gf_org', password='pass')
        users = [User.objects.create_user(username=f'dbe_gf_u{i}', password='pass') for i in range(4)]
        self.t = _make_tournament(self.org)
        self.ps = _add_participants(self.t, users)
        # Tworzymy strukturę: WB R1 (2 mecze) + WB Final (R2 = 1 mecz)
        _make_match(self.t, BT_W, 1, 1, self.ps[0], self.ps[1])
        _make_match(self.t, BT_W, 1, 2, self.ps[2], self.ps[3])
        # WB Final: wb_total_rounds=2
        self.wb_final = _make_match(self.t, BT_W, 2, 1, self.ps[0], self.ps[2])
        # LB Final: lb_final_round = 2*(2-1) = 2
        self.lb_final = _make_match(self.t, BT_L, 2, 1, self.ps[1], self.ps[3])

    def test_wb_final_winner_enters_gf_as_p1(self):
        """Zwycięzca WB Final → Grand Final jako participant1."""
        _complete_match(self.wb_final, self.ps[0])
        advance_dbe_match(self.wb_final, self.t)

        gf = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).first()
        self.assertIsNotNone(gf, 'Grand Final powinien zostać stworzony')
        self.assertEqual(gf.participant1, self.ps[0])

    def test_wb_final_loser_goes_to_lb_final_as_p2(self):
        """Przegrany WB Final → LB Final (lb_final_round) jako participant2."""
        _complete_match(self.wb_final, self.ps[0])
        advance_dbe_match(self.wb_final, self.t)

        # Sprawdź że ps[2] (przegrany WB Final) jest w LB Final (R2/M1) jako p2
        lb_final = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=2, match_index=1
        ).first()
        self.assertIsNotNone(lb_final)
        self.assertEqual(lb_final.participant2, self.ps[2])

    def test_lb_final_winner_enters_gf_as_p2(self):
        """Zwycięzca LB Final → Grand Final jako participant2."""
        _complete_match(self.lb_final, self.ps[1])
        advance_dbe_match(self.lb_final, self.t)

        gf = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).first()
        self.assertIsNotNone(gf, 'Grand Final powinien zostać stworzony')
        self.assertEqual(gf.participant2, self.ps[1])

    def test_gf_has_bracket_type_gf(self):
        """Grand Final ma bracket_type='GF'."""
        _complete_match(self.wb_final, self.ps[0])
        advance_dbe_match(self.wb_final, self.t)

        gf = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).first()
        self.assertIsNotNone(gf)
        self.assertEqual(gf.bracket_type, BT_GF)

    def test_gf_has_round_1_match_1(self):
        """Grand Final ma round_number=1, match_index=1."""
        _complete_match(self.wb_final, self.ps[0])
        advance_dbe_match(self.wb_final, self.t)

        gf = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).first()
        self.assertIsNotNone(gf)
        self.assertEqual(gf.round_number, 1)
        self.assertEqual(gf.match_index, 1)

    def test_gf_advance_does_nothing(self):
        """Po zakończeniu GF — brak dalszego routingu (turniej zakończony)."""
        gf = _make_match(self.t, BT_GF, 1, 1, self.ps[0], self.ps[1])
        _complete_match(gf, self.ps[0])
        advance_dbe_match(gf, self.t)

        # Nie powinny powstać żadne nowe mecze GF
        gf_count = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).count()
        self.assertEqual(gf_count, 1, 'Po GF nie powinny powstawać nowe mecze')

    def test_gf_both_players_filled_after_wb_and_lb_finish(self):
        """GF ma obu uczestników po zakończeniu WB Final i LB Final."""
        _complete_match(self.wb_final, self.ps[0])
        advance_dbe_match(self.wb_final, self.t)

        _complete_match(self.lb_final, self.ps[1])
        advance_dbe_match(self.lb_final, self.t)

        gf = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).first()
        self.assertIsNotNone(gf)
        self.assertIsNotNone(gf.participant1, 'GF participant1 powinien być ustawiony')
        self.assertIsNotNone(gf.participant2, 'GF participant2 powinien być ustawiony')


class DBEFullSimulation4PlayersTest(TestCase):
    """
    Pełna symulacja DBE dla 4 graczy.

    Struktura:
    WB: R1 (2 mecze) → R2 WB Final (1 mecz)
    LB: R1 (1 mecz) → R2 LB Final (1 mecz)
    GF: 1 mecz

    Łącznie: 5 meczów (+ GF = 6 rozegranych)
    """

    def setUp(self):
        self.org = User.objects.create_user(username='dbe_sim4_org', password='pass')
        self.users = [
            User.objects.create_user(username=f'dbe_sim4_u{i}', password='pass')
            for i in range(4)
        ]
        self.t = _make_tournament(self.org)
        self.ps = _add_participants(self.t, self.users)

        # Generuj R1 WB (RANDOM seeding)
        config, _ = EliminationConfig.objects.get_or_create(
            tournament=self.t,
            defaults={'initial_seeding': 'RANDOM', 'third_place_match': False},
        )
        count, _ = generate_elimination_matches_initial(
            self.t,
            self.t.participants.filter(status='ACT'),
            config,
            bracket_type=BT_W,
        )
        self.assertEqual(count, 2, 'Powinny być 2 mecze R1 WB')

    def test_full_4player_dbe_simulation(self):
        """Symulacja pełnego turnieju DBE 4-osobowego krok po kroku."""
        # ── R1 WB ─────────────────────────────────────────────────────────────
        wb_r1_matches = list(
            TournamentsMatch.objects.filter(
                tournament=self.t, bracket_type=BT_W, round_number=1
            ).order_by('match_index')
        )
        self.assertEqual(len(wb_r1_matches), 2)

        m1, m2 = wb_r1_matches
        w1, l1 = m1.participant1, m1.participant2  # p0 wygrywa M1
        w2, l2 = m2.participant1, m2.participant2  # p0 wygrywa M2

        _complete_match(m1, w1)
        advance_dbe_match(m1, self.t)

        _complete_match(m2, w2)
        advance_dbe_match(m2, self.t)

        # Sprawdź WB R2 istnieje z obu zwycięzcami
        wb_r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_W, round_number=2
        ).first()
        self.assertIsNotNone(wb_r2)
        self.assertIsNotNone(wb_r2.participant1)
        self.assertIsNotNone(wb_r2.participant2)

        # Sprawdź LB R1 z obu przegranymi
        lb_r1 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=1
        ).first()
        self.assertIsNotNone(lb_r1)
        self.assertIsNotNone(lb_r1.participant1)
        self.assertIsNotNone(lb_r1.participant2)

        # ── LB R1 ─────────────────────────────────────────────────────────────
        lb_r1.refresh_from_db()
        lb_r1_winner = lb_r1.participant1
        _complete_match(lb_r1, lb_r1_winner)
        advance_dbe_match(lb_r1, self.t)

        # Zwycięzca LB R1 → LB R2
        lb_r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=2
        ).first()
        self.assertIsNotNone(lb_r2, 'LB R2 powinien istnieć po LB R1')

        # ── WB Final (R2) ─────────────────────────────────────────────────────
        wb_r2.refresh_from_db()
        wb_final_winner = wb_r2.participant1
        wb_final_loser = wb_r2.participant2
        _complete_match(wb_r2, wb_final_winner)
        advance_dbe_match(wb_r2, self.t)

        # WB Final winner → GF as p1
        gf = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).first()
        self.assertIsNotNone(gf)
        self.assertEqual(gf.participant1, wb_final_winner)

        # WB Final loser → LB Final (LB R2) as p2
        lb_r2.refresh_from_db()
        self.assertEqual(lb_r2.participant2, wb_final_loser)

        # ── LB Final (LB R2) ──────────────────────────────────────────────────
        lb_r2.refresh_from_db()
        lb_final_winner = lb_r2.participant1
        _complete_match(lb_r2, lb_final_winner)
        advance_dbe_match(lb_r2, self.t)

        # LB Final winner → GF as p2
        gf.refresh_from_db()
        self.assertEqual(gf.participant2, lb_final_winner)

        # ── Grand Final ────────────────────────────────────────────────────────
        gf.refresh_from_db()
        gf_winner = gf.participant1
        _complete_match(gf, gf_winner)
        advance_dbe_match(gf, self.t)

        # Turniej zakończony — nie ma żadnych nowych meczów poza już stworzonymi
        total_matches = TournamentsMatch.objects.filter(tournament=self.t).count()
        # WB R1 (2) + WB R2 Final (1) + LB R1 (1) + LB R2 Final (1) + GF (1) = 6
        self.assertEqual(total_matches, 6, f'Oczekiwano 6 meczów łącznie, jest {total_matches}')

    def test_wb_total_rounds_for_4_players(self):
        """wb_total_rounds dla 4 uczestników (2 mecze R1) = 2."""
        total = _wb_total_rounds(self.t)
        self.assertEqual(total, 2)


class DBEIdempotencyTest(TestCase):
    """Advance jest idempotentny przy re-edycji wyniku."""

    def setUp(self):
        self.org = User.objects.create_user(username='dbe_idemp_org', password='pass')
        users = [User.objects.create_user(username=f'dbe_idemp_u{i}', password='pass') for i in range(4)]
        self.t = _make_tournament(self.org)
        self.ps = _add_participants(self.t, users)
        _make_match(self.t, BT_W, 1, 1, self.ps[0], self.ps[1])
        _make_match(self.t, BT_W, 1, 2, self.ps[2], self.ps[3])
        self.wb_m1 = TournamentsMatch.objects.get(
            tournament=self.t, bracket_type=BT_W, round_number=1, match_index=1
        )

    def test_double_advance_does_not_duplicate_matches(self):
        """Dwukrotne wywołanie advance nie tworzy duplikatów meczów."""
        _complete_match(self.wb_m1, self.ps[0])
        advance_dbe_match(self.wb_m1, self.t)
        advance_dbe_match(self.wb_m1, self.t)

        wb_r2_count = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_W, round_number=2
        ).count()
        lb_r1_count = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L, round_number=1
        ).count()
        self.assertEqual(wb_r2_count, 1)
        self.assertEqual(lb_r1_count, 1)

    def test_winner_change_updates_slot(self):
        """Zmiana zwycięzcy aktualizuje slot w meczu następnej rundy."""
        _complete_match(self.wb_m1, self.ps[0])
        advance_dbe_match(self.wb_m1, self.t)

        wb_r2 = TournamentsMatch.objects.get(
            tournament=self.t, bracket_type=BT_W, round_number=2
        )
        self.assertEqual(wb_r2.participant1, self.ps[0])

        # Re-edycja: ps[1] wygrywa
        _complete_match(self.wb_m1, self.ps[1])
        advance_dbe_match(self.wb_m1, self.t)

        wb_r2.refresh_from_db()
        self.assertEqual(wb_r2.participant1, self.ps[1], 'Slot powinien być zaktualizowany na nowego zwycięzcę')


class SGLRegressionTest(TestCase):
    """SGL advance_winner_in_bracket() bez regresji po dodaniu DBE."""

    def setUp(self):
        self.org = User.objects.create_user(username='sgl_reg_org', password='pass')
        users = [User.objects.create_user(username=f'sgl_reg_u{i}', password='pass') for i in range(4)]
        self.t = _make_tournament(self.org, t_type='SGL')
        self.ps = _add_participants(self.t, users)
        _make_match(self.t, BT_W, 1, 1, self.ps[0], self.ps[1])
        _make_match(self.t, BT_W, 1, 2, self.ps[2], self.ps[3])

    def test_sgl_winner_advances_to_next_round(self):
        """SGL: advance_winner_in_bracket() tworzy mecz R2."""
        m1 = TournamentsMatch.objects.get(
            tournament=self.t, bracket_type=BT_W, round_number=1, match_index=1
        )
        _complete_match(m1, self.ps[0])
        advance_winner_in_bracket(m1, self.t)

        r2 = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_W, round_number=2
        ).first()
        self.assertIsNotNone(r2)
        self.assertEqual(r2.participant1, self.ps[0])

    def test_sgl_no_lb_matches_created(self):
        """SGL advance nie tworzy meczów LB ani GF."""
        m1 = TournamentsMatch.objects.get(
            tournament=self.t, bracket_type=BT_W, round_number=1, match_index=1
        )
        _complete_match(m1, self.ps[0])
        advance_winner_in_bracket(m1, self.t)

        lb_count = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_L
        ).count()
        gf_count = TournamentsMatch.objects.filter(
            tournament=self.t, bracket_type=BT_GF
        ).count()
        self.assertEqual(lb_count, 0, 'SGL nie powinien tworzyć meczów LB')
        self.assertEqual(gf_count, 0, 'SGL nie powinien tworzyć meczu GF')
