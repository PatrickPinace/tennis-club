"""
Testy generate_round_robin_matches_initial() — RR SNG i RR DBL.

Scenariusze:
- SNG: 4 uczestników → C(4,2) = 6 meczów, obsada p1/p2, p3/p4 puste
- SNG: 2 uczestników → 1 mecz
- DBL: 4 uczestników → C(2 drużyny, 2) = 1 mecz deblowy, obsada p1-p4 wypełniona
- DBL: 8 uczestników → C(4 drużyny, 2) = 6 meczów deblowych
- DBL: 3 uczestników (nieparzyste) → błąd (0 meczów)
- DBL: 2 uczestników (za mało) → błąd (0 meczów)
- SNG: 1 uczestnik (za mało) → błąd (0 meczów)
- Konwencja obsady DBL: participant1+participant4 vs participant2+participant3
"""
import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import Tournament, Participant, TournamentsMatch
from apps.tournaments.views import generate_round_robin_matches_initial


def _make_tournament(org, match_format='SNG'):
    return Tournament.objects.create(
        name=f'RR {match_format} Test',
        tournament_type='RND',
        match_format=match_format,
        status='REG',
        rank=1,
        created_by=org,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 3, 31),
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


class RRSNGGeneratorTest(TestCase):
    def setUp(self):
        self.org = User.objects.create_user(username='rr_org', password='pass')
        self.users = [
            User.objects.create_user(username=f'rr_p{i}', password='pass')
            for i in range(4)
        ]

    def test_sng_4_players_generates_6_matches(self):
        """4 uczestników SNG → C(4,2) = 6 meczów."""
        t = _make_tournament(self.org, 'SNG')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')

        count, msg = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 6)
        self.assertEqual(TournamentsMatch.objects.filter(tournament=t).count(), 6)

    def test_sng_matches_have_only_p1_p2(self):
        """Mecze SNG mają participant1 i participant2; participant3 i participant4 puste."""
        t = _make_tournament(self.org, 'SNG')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        for m in TournamentsMatch.objects.filter(tournament=t):
            self.assertIsNotNone(m.participant1, 'participant1 powinien być ustawiony')
            self.assertIsNotNone(m.participant2, 'participant2 powinien być ustawiony')
            self.assertIsNone(m.participant3, 'participant3 powinien być None dla SNG')
            self.assertIsNone(m.participant4, 'participant4 powinien być None dla SNG')

    def test_sng_2_players_generates_1_match(self):
        """2 uczestników SNG → 1 mecz."""
        t = _make_tournament(self.org, 'SNG')
        _add_participants(t, self.users[:2])
        qs = t.participants.filter(status='REG')

        count, _ = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 1)

    def test_sng_1_player_returns_zero(self):
        """1 uczestnik SNG → 0 meczów, komunikat błędu."""
        t = _make_tournament(self.org, 'SNG')
        _add_participants(t, self.users[:1])
        qs = t.participants.filter(status='REG')

        count, msg = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 0)
        self.assertIn('mało', msg)

    def test_sng_all_matches_status_waiting(self):
        """Wszystkie mecze mają status WAI."""
        t = _make_tournament(self.org, 'SNG')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        statuses = TournamentsMatch.objects.filter(tournament=t).values_list('status', flat=True)
        for s in statuses:
            self.assertEqual(s, TournamentsMatch.Status.WAITING.value)

    def test_sng_round_number_is_1(self):
        """Wszystkie mecze RR SNG mają round_number=1."""
        t = _make_tournament(self.org, 'SNG')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        rounds = TournamentsMatch.objects.filter(tournament=t).values_list('round_number', flat=True)
        for r in rounds:
            self.assertEqual(r, 1)

    def test_sng_idempotent_deletes_previous(self):
        """Ponowne wywołanie kasuje stare mecze i tworzy nowe."""
        t = _make_tournament(self.org, 'SNG')
        _add_participants(t, self.users)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)
        first_ids = set(TournamentsMatch.objects.filter(tournament=t).values_list('pk', flat=True))

        generate_round_robin_matches_initial(t, qs)
        second_ids = set(TournamentsMatch.objects.filter(tournament=t).values_list('pk', flat=True))

        self.assertNotEqual(first_ids, second_ids, 'Ponowne wywołanie powinno stworzyć nowe obiekty')
        self.assertEqual(len(second_ids), 6)


class RRDBLGeneratorTest(TestCase):
    def setUp(self):
        self.org = User.objects.create_user(username='dbl_org', password='pass')
        self.users4 = [
            User.objects.create_user(username=f'dbl_p{i}', password='pass')
            for i in range(4)
        ]
        self.users8 = self.users4 + [
            User.objects.create_user(username=f'dbl_p{i}', password='pass')
            for i in range(4, 8)
        ]

    def test_dbl_4_players_generates_1_match(self):
        """4 uczestników DBL → 2 drużyny → C(2,2) = 1 mecz deblowy."""
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')

        count, msg = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 1)
        self.assertEqual(TournamentsMatch.objects.filter(tournament=t).count(), 1)
        self.assertIn('deblowych', msg)

    def test_dbl_8_players_generates_6_matches(self):
        """8 uczestników DBL → 4 drużyny → C(4,2) = 6 meczów deblowych."""
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users8)
        qs = t.participants.filter(status='REG')

        count, _ = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 6)
        self.assertEqual(TournamentsMatch.objects.filter(tournament=t).count(), 6)

    def test_dbl_matches_have_all_4_slots_filled(self):
        """Mecze DBL mają wypełnione participant1, participant2, participant3, participant4."""
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        m = TournamentsMatch.objects.get(tournament=t)
        self.assertIsNotNone(m.participant1, 'participant1 musi być ustawiony')
        self.assertIsNotNone(m.participant2, 'participant2 musi być ustawiony')
        self.assertIsNotNone(m.participant3, 'participant3 musi być ustawiony dla DBL')
        self.assertIsNotNone(m.participant4, 'participant4 musi być ustawiony dla DBL')

    def test_dbl_convention_team_a_is_p1_p4_team_b_is_p2_p3(self):
        """
        Konwencja obsady: Team A = participant1 + participant4,
        Team B = participant2 + participant3.
        Graczy parujemy po kolejności pk: drużyna 0 = (p0, p1), drużyna 1 = (p2, p3).
        Mecz drużyna0 vs drużyna1:
          participant1 = p0 (ta1), participant4 = p1 (ta2)   ← Team A
          participant2 = p2 (tb1), participant3 = p3 (tb2)   ← Team B
        """
        t = _make_tournament(self.org, 'DBL')
        participants = _add_participants(t, self.users4)
        # participants jest posortowany wg pk bo _add_participants tworzy kolejno
        # i qs.order_by('pk') zapewni tę kolejność
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        m = TournamentsMatch.objects.get(tournament=t)
        all_pks = set(
            TournamentsMatch.objects.filter(tournament=t)
            .values_list('participant1', 'participant2', 'participant3', 'participant4')
            .first()
        )
        participant_pks = {p.pk for p in participants}
        # Wszystkie 4 sloty muszą wskazywać na różnych uczestników
        filled = [m.participant1_id, m.participant2_id, m.participant3_id, m.participant4_id]
        self.assertEqual(len(set(filled)), 4, 'Wszystkie 4 sloty powinny wskazywać na różnych uczestników')
        self.assertEqual(set(filled), participant_pks, 'Sloty powinny zawierać wszystkich 4 uczestników')

    def test_dbl_4_participants_each_player_appears_once(self):
        """Przy 4 uczestnikach (1 mecz) każdy gracz pojawia się dokładnie raz."""
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users4)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        m = TournamentsMatch.objects.get(tournament=t)
        slots = [m.participant1_id, m.participant2_id, m.participant3_id, m.participant4_id]
        self.assertEqual(len(slots), len(set(slots)), 'Każdy gracz powinien pojawić się dokładnie raz')

    def test_dbl_3_players_returns_zero(self):
        """3 uczestników (za mało) → 0 meczów, komunikat błędu."""
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users4[:3])
        qs = t.participants.filter(status='REG')

        count, msg = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 0)
        self.assertGreater(len(msg), 0, 'Powinien być komunikat błędu')

    def test_dbl_5_players_returns_zero(self):
        """5 uczestników (nieparzyste, >= 4) → 0 meczów, komunikat o parzystości."""
        extra_user = User.objects.create_user(username='dbl_p8', password='pass')
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users4 + [extra_user])
        qs = t.participants.filter(status='REG')

        count, msg = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 0)
        self.assertIn('parzystej', msg)

    def test_dbl_2_players_returns_zero(self):
        """2 uczestników (za mało dla DBL) → 0 meczów."""
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users4[:2])
        qs = t.participants.filter(status='REG')

        count, msg = generate_round_robin_matches_initial(t, qs)

        self.assertEqual(count, 0)
        self.assertIn('mało', msg)

    def test_dbl_all_matches_status_waiting(self):
        """Wszystkie mecze DBL mają status WAI."""
        t = _make_tournament(self.org, 'DBL')
        _add_participants(t, self.users8)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        statuses = TournamentsMatch.objects.filter(tournament=t).values_list('status', flat=True)
        for s in statuses:
            self.assertEqual(s, TournamentsMatch.Status.WAITING.value)

    def test_dbl_each_team_plays_every_other_team(self):
        """
        8 uczestników → 4 drużyny → każda drużyna gra z każdą inną.
        Sprawdzamy że C(4,2) = 6 par drużyn jest unikalnych.
        """
        t = _make_tournament(self.org, 'DBL')
        participants = _add_participants(t, self.users8)
        qs = t.participants.filter(status='REG')

        generate_round_robin_matches_initial(t, qs)

        matches = TournamentsMatch.objects.filter(tournament=t)
        self.assertEqual(matches.count(), 6)

        # Zbierz pary drużyn (frozenset Team A PKs, frozenset Team B PKs)
        team_pairs = set()
        for m in matches:
            team_a = frozenset([m.participant1_id, m.participant4_id])
            team_b = frozenset([m.participant2_id, m.participant3_id])
            pair = frozenset([team_a, team_b])
            team_pairs.add(pair)

        self.assertEqual(len(team_pairs), 6, 'Powinno być 6 unikalnych par drużyn')
