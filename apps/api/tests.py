"""
Testy PATCH /api/tournaments/{id}/config/

Pokrywa:
- 404 dla non-RND
- 403 dla niezalogowanego / nieuprawnionego
- 400 dla sets_to_win gdy turniej już startował
- 400 gdy points_for_win < points_for_loss
- 400 gdy punkty poza [-100, 100]
- 200 dla organizatora: partial update + odpowiedź zawiera config i standings
- 200 dla is_staff
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.tournaments.models import Tournament, Participant, RoundRobinConfig, TournamentsMatch


def _make_rnd_tournament(org, status='DRF'):
    t = Tournament.objects.create(
        name='Config Test Liga',
        tournament_type='RND',
        match_format='SNG',
        status=status,
        rank=1,
        created_by=org,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 3, 31),
    )
    RoundRobinConfig.objects.get_or_create(
        tournament=t,
        defaults=dict(
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
            tie_breaker_priority='SETS',
        )
    )
    return t


def _config_url(pk):
    return f'/api/tournaments/{pk}/config/'


class RRConfigUpdatePermissionsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = User.objects.create_user(username='cfg_org', password='pass')
        self.other = User.objects.create_user(username='cfg_other', password='pass')
        self.staff = User.objects.create_user(username='cfg_staff', password='pass', is_staff=True)
        self.t = _make_rnd_tournament(self.org)

    def test_401_or_403_unauthenticated(self):
        # DRF z SessionAuthentication zwraca 403 dla niezalogowanych (nie 401)
        res = self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'GAMES'}, format='json')
        self.assertIn(res.status_code, (401, 403))

    def test_403_non_organizer(self):
        self.client.force_authenticate(user=self.other)
        res = self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'GAMES'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_200_organizer(self):
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'GAMES'}, format='json')
        self.assertEqual(res.status_code, 200)

    def test_200_staff(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'HEAD'}, format='json')
        self.assertEqual(res.status_code, 200)

    def test_404_non_rnd_tournament(self):
        se_t = Tournament.objects.create(
            name='SE Turniej', tournament_type='SEL', match_format='SNG',
            status='DRF', rank=1, created_by=self.org,
        )
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(se_t.pk), {'tie_breaker_priority': 'SETS'}, format='json')
        self.assertEqual(res.status_code, 404)

    def test_404_nonexistent_tournament(self):
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(99999), {'tie_breaker_priority': 'SETS'}, format='json')
        self.assertEqual(res.status_code, 404)


class RRConfigUpdateValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = User.objects.create_user(username='val_org', password='pass')

    def test_400_sets_to_win_after_start(self):
        t = _make_rnd_tournament(self.org, status='ACT')
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(t.pk), {'sets_to_win': 1}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('sets_to_win', res.json())

    def test_400_games_per_set_after_start(self):
        t = _make_rnd_tournament(self.org, status='ACT')
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(t.pk), {'games_per_set': 4}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('games_per_set', res.json())

    def test_ok_other_fields_after_start(self):
        """Punkty można zmieniać nawet gdy turniej trwa."""
        t = _make_rnd_tournament(self.org, status='ACT')
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(t.pk), {'points_for_win': '3.00'}, format='json')
        self.assertEqual(res.status_code, 200)

    def test_400_win_less_than_loss(self):
        t = _make_rnd_tournament(self.org)
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(t.pk), {'points_for_win': '0.50', 'points_for_loss': '1.00'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('points_for_win', res.json())

    def test_400_points_out_of_range(self):
        t = _make_rnd_tournament(self.org)
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(t.pk), {'points_for_win': '999'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_400_max_participants_too_small(self):
        t = _make_rnd_tournament(self.org)
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(t.pk), {'max_participants': 1}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('max_participants', res.json())

    def test_400_sets_to_win_zero(self):
        t = _make_rnd_tournament(self.org)
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(t.pk), {'sets_to_win': 0}, format='json')
        self.assertEqual(res.status_code, 400)


class RRConfigUpdateResponseTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = User.objects.create_user(username='resp_org', password='pass')
        self.t = _make_rnd_tournament(self.org)
        # Dodaj uczestnika i mecz żeby standings nie był pusty
        p1_user = User.objects.create_user(username='resp_p1', password='pass')
        p2_user = User.objects.create_user(username='resp_p2', password='pass')
        p1 = Participant.objects.create(tournament=self.t, user=p1_user, display_name='P1', status='ACT')
        p2 = Participant.objects.create(tournament=self.t, user=p2_user, display_name='P2', status='ACT')
        TournamentsMatch.objects.create(
            tournament=self.t,
            participant1=p1, participant2=p2, winner=p1, status='CMP',
            round_number=1, match_index=1,
            set1_p1_score=6, set1_p2_score=3, set2_p1_score=6, set2_p2_score=2,
        )

    def test_response_shape(self):
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'GAMES'}, format='json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('config', data)
        self.assertIn('standings', data)

    def test_config_updated_in_response(self):
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'HEAD', 'points_for_win': '3.00'}, format='json')
        self.assertEqual(res.status_code, 200)
        cfg = res.json()['config']
        self.assertEqual(cfg['tie_breaker_priority'], 'HEAD')
        self.assertEqual(Decimal(cfg['points_for_win']), Decimal('3.00'))

    def test_config_persisted_in_db(self):
        self.client.force_authenticate(user=self.org)
        self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'GAMES', 'max_participants': 12}, format='json')
        self.t.round_robin_config.refresh_from_db()
        self.assertEqual(self.t.round_robin_config.tie_breaker_priority, 'GAMES')
        self.assertEqual(self.t.round_robin_config.max_participants, 12)

    def test_standings_present_in_response(self):
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_config_url(self.t.pk), {'tie_breaker_priority': 'SETS'}, format='json')
        standings = res.json()['standings']
        self.assertIsInstance(standings, list)
        self.assertEqual(len(standings), 2)
        self.assertIn('display_name', standings[0])
        self.assertIn('points', standings[0])

    def test_partial_update_does_not_reset_other_fields(self):
        """PATCH z jednym polem nie zeruje pozostałych."""
        self.client.force_authenticate(user=self.org)
        self.client.patch(_config_url(self.t.pk), {'max_participants': 10}, format='json')
        self.t.round_robin_config.refresh_from_db()
        # points_for_win powinno zostać domyślne (2.00)
        self.assertEqual(self.t.round_robin_config.points_for_win, Decimal('2.00'))
        self.assertEqual(self.t.round_robin_config.max_participants, 10)
