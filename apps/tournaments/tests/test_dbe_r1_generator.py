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
from apps.tournaments.views import generate_elimination_matches_initial


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

        # bracket_size=8, 4 pary → zawsze 4 mecze (losowość decyduje ile jest BYE per para)
        self.assertEqual(count, 4)
        # Łączna liczba uczestników we wszystkich slotach p1 = 6 (bez None)
        matches = TournamentsMatch.objects.filter(tournament=t)
        self.assertEqual(matches.count(), 4)
        # Wszystkie mają bracket_type='W'
        types = matches.values_list('bracket_type', flat=True)
        self.assertTrue(all(bt == 'W' for bt in types))

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
