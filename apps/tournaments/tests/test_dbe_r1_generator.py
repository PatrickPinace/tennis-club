"""
Testy Etapu B Double Elimination — generowanie R1 Winners Bracket.

Scenariusze:
- DBE REG→SCH generuje mecze R1 WB (4, 8 uczestników)
- Wszystkie mecze R1 mają bracket_type='W'
- Liczba meczów zgodna z bracket_size (potęga 2, z BYE)
- Mecze z BYE mają status CMP, reszta WAI
- Istniejące mecze turnieju są kasowane przy regeneracji
- Reuse generate_elimination_matches_initial() z jawnym bracket_type='W'
- SGL: bracket_type='W' nadal ustawiany (brak regresji)
- DBE z 4 uczestnikami (bez BYE): 2 mecze WAI
- DBE z 6 uczestnikami: bracket_size=8, 2 BYE → 4 mecze (2 CMP, 2 WAI)
- DBE z 1 uczestnikiem: błąd
"""
import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import (
    Tournament, Participant, TournamentsMatch, EliminationConfig,
)
from apps.tournaments.bracket import generate_elimination_matches_initial


def _make_tournament(org, t_type='DBE', match_format='SNG'):
    return Tournament.objects.create(
        name=f'{t_type} Test',
        tournament_type=t_type,
        match_format=match_format,
        status='REG',
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
            status='REG',
        )
        for u in users
    ]


def _default_config(tournament):
    config, _ = EliminationConfig.objects.get_or_create(
        tournament=tournament,
        defaults={'initial_seeding': 'RANDOM', 'third_place_match': False},
    )
    return config


class DBEGeneratorBracketTypeTest(TestCase):
    """Testy że generate_elimination_matches_initial() ustawia bracket_type jawnie."""

    def setUp(self):
        self.org = User.objects.create_user(username='dbe_org', password='pass')
        self.users4 = [
            User.objects.create_user(username=f'dbe_u{i}', password='pass')
            for i in range(4)
        ]
        self.users8 = self.users4 + [
            User.objects.create_user(username=f'dbe_u{i}', password='pass')
            for i in range(4, 8)
        ]

    def test_dbe_4_players_generates_2_matches(self):
        """4 uczestników DBE → bracket_size=4 → 2 mecze R1 WB."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        count, msg = generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        self.assertEqual(count, 2)
        self.assertEqual(TournamentsMatch.objects.filter(tournament=t).count(), 2)

    def test_dbe_4_players_all_bracket_type_W(self):
        """Wszystkie mecze R1 mają bracket_type='W'."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        types = TournamentsMatch.objects.filter(tournament=t).values_list('bracket_type', flat=True)
        for bt in types:
            self.assertEqual(bt, TournamentsMatch.BracketType.WINNERS)

    def test_dbe_4_players_all_round_1(self):
        """Wszystkie mecze R1 mają round_number=1."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        rounds = TournamentsMatch.objects.filter(tournament=t).values_list('round_number', flat=True)
        for r in rounds:
            self.assertEqual(r, 1)

    def test_dbe_4_players_no_byes_all_waiting(self):
        """4 uczestników (bracket_size=4) → brak BYE → wszystkie mecze WAI."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        statuses = TournamentsMatch.objects.filter(tournament=t).values_list('status', flat=True)
        for s in statuses:
            self.assertEqual(s, TournamentsMatch.Status.WAITING.value)

    def test_dbe_8_players_generates_4_matches(self):
        """8 uczestników DBE → 4 mecze R1 WB, brak BYE."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users8)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        count, _ = generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        self.assertEqual(count, 4)

    def test_dbe_8_players_all_bracket_type_W(self):
        """8 uczestników DBE → wszystkie bracket_type='W'."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users8)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        types = TournamentsMatch.objects.filter(tournament=t).values_list('bracket_type', flat=True)
        self.assertTrue(all(bt == 'W' for bt in types))

    def test_dbe_6_players_bracket_size_8_with_byes(self):
        """6 uczestników → bracket_size=8 → 2 BYE → zawsze 4 mecze R1."""
        users6 = self.users4 + [
            User.objects.create_user(username=f'dbe_u6_{i}', password='pass')
            for i in range(2)
        ]
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, users6)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        count, _ = generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        # bracket_size=8, 4 pary → 4 mecze WB R1 (count = liczba stworzonych R1 WB)
        self.assertEqual(count, 4)
        wb_r1_matches = TournamentsMatch.objects.filter(
            tournament=t, round_number=1, bracket_type=TournamentsMatch.BracketType.WINNERS
        )
        self.assertEqual(wb_r1_matches.count(), 4)
        # Wszystkie WB R1 mają bracket_type='W'
        types = wb_r1_matches.values_list('bracket_type', flat=True)
        self.assertTrue(all(bt == 'W' for bt in types))
        # Gracze z BYE zostali już awansowani do R2
        bye_matches = wb_r1_matches.filter(participant2=None)
        self.assertGreater(bye_matches.count(), 0)
        r2_matches = TournamentsMatch.objects.filter(tournament=t, round_number=2)
        self.assertGreater(r2_matches.count(), 0)

    def test_dbe_6_players_bye_matches_have_bracket_type_W(self):
        """Mecze BYE w DBE mają bracket_type='W'."""
        users6 = self.users4 + [
            User.objects.create_user(username=f'dbe_u6b_{i}', password='pass')
            for i in range(2)
        ]
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, users6)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        bye_matches = TournamentsMatch.objects.filter(
            tournament=t, status=TournamentsMatch.Status.COMPLETED.value
        )
        for m in bye_matches:
            self.assertEqual(m.bracket_type, TournamentsMatch.BracketType.WINNERS)

    def test_dbe_1_player_returns_zero(self):
        """1 uczestnik DBE → 0 meczów, komunikat błędu."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users4[:1])
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        count, msg = generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )

        self.assertEqual(count, 0)
        self.assertIn('mało', msg)

    def test_dbe_idempotent_clears_previous_matches(self):
        """Ponowne wywołanie kasuje stare mecze i tworzy nowe."""
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)

        generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )
        first_ids = set(TournamentsMatch.objects.filter(tournament=t).values_list('pk', flat=True))

        generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )
        second_ids = set(TournamentsMatch.objects.filter(tournament=t).values_list('pk', flat=True))

        self.assertNotEqual(first_ids, second_ids)
        self.assertEqual(len(second_ids), 2)


class DBEByeDistributionTest(TestCase):
    """Testy dla przypadków z BYE: 5 i 7 uczestników.

    Cel: sprawdzić że:
    - brak BYE-vs-BYE (żaden mecz R1 nie ma obu uczestników None)
    - match_index jest spójny (bez dziur w numeracji)
    - żaden mecz R2+ nie ma statusu WAI z participant=None (stranded WAI)
    """

    def setUp(self):
        self.org = User.objects.create_user(username='bye_dist_org', password='pass')

    def _make_users(self, n, prefix='bye_u'):
        return [
            User.objects.create_user(username=f'{prefix}_{i}', password='pass')
            for i in range(n)
        ]

    def _run_generation(self, num_players, prefix):
        users = self._make_users(num_players, prefix=prefix)
        t = _make_tournament(self.org, 'DBE')
        _add_participants(t, users)
        qs = t.participants.filter(status='REG')
        config = _default_config(t)
        count, msg = generate_elimination_matches_initial(
            t, qs, config, bracket_type=TournamentsMatch.BracketType.WINNERS
        )
        return t, count

    def test_5_players_no_bye_vs_bye(self):
        """5 uczestników → bracket_size=8, 3 BYE → żaden mecz WB R1 nie ma obu uczestników None."""
        t, count = self._run_generation(5, 'p5')
        wb_r1 = TournamentsMatch.objects.filter(
            tournament=t, round_number=1, bracket_type=TournamentsMatch.BracketType.WINNERS
        )
        for m in wb_r1:
            self.assertFalse(
                m.participant1 is None and m.participant2 is None,
                f'BYE-vs-BYE znaleziony w meczu WB R1/M{m.match_index}',
            )

    def test_5_players_match_index_contiguous(self):
        """5 uczestników → match_index WB R1 powinny być spójne (1..N bez dziur)."""
        t, count = self._run_generation(5, 'p5c')
        r1_indices = sorted(
            TournamentsMatch.objects.filter(
                tournament=t, round_number=1, bracket_type=TournamentsMatch.BracketType.WINNERS
            ).values_list('match_index', flat=True)
        )
        expected = list(range(1, len(r1_indices) + 1))
        self.assertEqual(r1_indices, expected, f'Dziury w match_index: {r1_indices}')

    def test_5_players_no_stranded_wai(self):
        """5 uczestników → po generacji brak meczów WAI bez żadnego uczestnika (obie strony None).

        Mecz WAI z jednym uczestnikiem (czeka na drugiego) jest poprawny.
        Stranded = mecz WAI gdzie OBOJE uczestnicy są None — taki mecz nigdy nie może być rozegrany.
        """
        t, count = self._run_generation(5, 'p5s')
        stranded = TournamentsMatch.objects.filter(
            tournament=t,
            status=TournamentsMatch.Status.WAITING.value,
            participant1=None,
            participant2=None,
        )
        self.assertEqual(
            stranded.count(), 0,
            f'Stranded WAI mecze (oboje None): {list(stranded.values("bracket_type","round_number","match_index"))}',
        )

    def test_7_players_no_bye_vs_bye(self):
        """7 uczestników → bracket_size=8, 1 BYE → żaden mecz WB R1 nie ma obu uczestników None."""
        t, count = self._run_generation(7, 'p7')
        wb_r1 = TournamentsMatch.objects.filter(
            tournament=t, round_number=1, bracket_type=TournamentsMatch.BracketType.WINNERS
        )
        for m in wb_r1:
            self.assertFalse(
                m.participant1 is None and m.participant2 is None,
                f'BYE-vs-BYE znaleziony w meczu WB R1/M{m.match_index}',
            )

    def test_7_players_match_index_contiguous(self):
        """7 uczestników → match_index WB R1 spójne (1..4)."""
        t, count = self._run_generation(7, 'p7c')
        r1_indices = sorted(
            TournamentsMatch.objects.filter(
                tournament=t, round_number=1, bracket_type=TournamentsMatch.BracketType.WINNERS
            ).values_list('match_index', flat=True)
        )
        expected = list(range(1, len(r1_indices) + 1))
        self.assertEqual(r1_indices, expected, f'Dziury w match_index: {r1_indices}')

    def test_7_players_correct_r1_count(self):
        """7 uczestników → 4 mecze WB R1 (bracket_size=8)."""
        t, count = self._run_generation(7, 'p7n')
        self.assertEqual(count, 4)

    def test_5_players_correct_r1_count(self):
        """5 uczestników → 3 BYE = bracket_size=8 → 4 mecze WB R1 (bez BYE-vs-BYE)."""
        t, count = self._run_generation(5, 'p5n')
        # bracket_size=8 → 4 pary; 3 pary mają BYE w slot_b, 1 para ma 2 graczy
        # 4 pary → 4 mecze WB R1 (żadnej pary BYE-vs-BYE)
        self.assertEqual(count, 4)

    def test_7_players_no_stranded_wai(self):
        """7 uczestników → po generacji brak meczów WAI bez żadnego uczestnika (obie strony None)."""
        t, count = self._run_generation(7, 'p7s')
        stranded = TournamentsMatch.objects.filter(
            tournament=t,
            status=TournamentsMatch.Status.WAITING.value,
            participant1=None,
            participant2=None,
        )
        self.assertEqual(
            stranded.count(), 0,
            f'Stranded WAI mecze (oboje None): {list(stranded.values("bracket_type","round_number","match_index"))}',
        )

    def test_5_players_bye_advance_creates_r2(self):
        """5 uczestników → gracze z BYE w R1 są awansowani do R2 po generacji."""
        t, count = self._run_generation(5, 'p5r2')
        r2 = TournamentsMatch.objects.filter(tournament=t, round_number=2)
        self.assertGreater(r2.count(), 0, 'Brak meczów R2 po awansie z BYE')
        # Wszystkie mecze R2 powinny być bracket_type W lub L
        for m in r2:
            self.assertIn(m.bracket_type, [
                TournamentsMatch.BracketType.WINNERS,
                TournamentsMatch.BracketType.LOSERS,
            ])


class SGLBracketTypeRegressionTest(TestCase):
    """Testy regresji: SGL nadal dostaje bracket_type='W' (domyślnie i jawnie)."""

    def setUp(self):
        self.org = User.objects.create_user(username='sgl_org_b', password='pass')
        self.users = [
            User.objects.create_user(username=f'sgl_b_u{i}', password='pass')
            for i in range(4)
        ]

    def test_sgl_default_bracket_type_is_W(self):
        """SGL wywołane bez bracket_type → mecze mają bracket_type='W' (default)."""
        t = _make_tournament(self.org, 'SGL')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')
        config, _ = EliminationConfig.objects.get_or_create(
            tournament=t,
            defaults={'initial_seeding': 'RANDOM', 'third_place_match': False},
        )

        # Wywołanie bez jawnego bracket_type
        count, _ = generate_elimination_matches_initial(t, qs, config)

        types = TournamentsMatch.objects.filter(tournament=t).values_list('bracket_type', flat=True)
        for bt in types:
            self.assertEqual(bt, TournamentsMatch.BracketType.WINNERS,
                             'SGL bez bracket_type powinien domyślnie dostawać W')

    def test_sgl_4_players_generates_2_matches(self):
        """SGL z 4 uczestnikami nadal generuje 2 mecze R1."""
        t = _make_tournament(self.org, 'SGL')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')
        config, _ = EliminationConfig.objects.get_or_create(
            tournament=t,
            defaults={'initial_seeding': 'RANDOM', 'third_place_match': False},
        )

        count, _ = generate_elimination_matches_initial(t, qs, config)

        self.assertEqual(count, 2)

    def test_sgl_matches_have_round_1(self):
        """SGL R1 mecze mają round_number=1."""
        t = _make_tournament(self.org, 'SGL')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')
        config, _ = EliminationConfig.objects.get_or_create(
            tournament=t,
            defaults={'initial_seeding': 'RANDOM', 'third_place_match': False},
        )

        generate_elimination_matches_initial(t, qs, config)

        rounds = TournamentsMatch.objects.filter(tournament=t).values_list('round_number', flat=True)
        for r in rounds:
            self.assertEqual(r, 1)
