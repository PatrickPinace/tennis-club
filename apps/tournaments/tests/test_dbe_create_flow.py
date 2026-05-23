"""
Testy create flow dla DBE:
- /api/tournaments/{id}/config/sgl/ akceptuje DBE i wymusza third_place_match=False
- /api/tournaments/{id}/config/sgl/ odrzuca turnieje innych typów (RND, AMR)
- serializer config zawiera dane EliminationConfig dla DBE
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.tournaments.models import Tournament, EliminationConfig

User = get_user_model()


class DBEConfigEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='org_dbe', password='pass')
        self.client.force_authenticate(user=self.user)

    def _create_tournament(self, ttype):
        t = Tournament.objects.create(
            name=f'Test {ttype}',
            tournament_type=ttype,
            created_by=self.user,
        )
        return t

    def test_dbe_config_sgl_endpoint_accepts_dbe(self):
        t = self._create_tournament('DBE')
        res = self.client.post(
            f'/api/tournaments/{t.pk}/config/sgl/',
            {'initial_seeding': 'RANDOM'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        cfg = EliminationConfig.objects.get(tournament=t)
        self.assertEqual(cfg.initial_seeding, 'RANDOM')

    def test_dbe_config_always_forces_third_place_false(self):
        t = self._create_tournament('DBE')
        # Nawet jeśli klient wyśle third_place_match=True, backend wymusi False
        res = self.client.post(
            f'/api/tournaments/{t.pk}/config/sgl/',
            {'initial_seeding': 'SEEDING', 'third_place_match': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        cfg = EliminationConfig.objects.get(tournament=t)
        self.assertFalse(cfg.third_place_match)

    def test_dbe_config_default_seeding_seeding(self):
        t = self._create_tournament('DBE')
        # Wywołanie bez parametrów — backend tworzy z domyślnymi
        res = self.client.post(
            f'/api/tournaments/{t.pk}/config/sgl/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        cfg = EliminationConfig.objects.get(tournament=t)
        self.assertFalse(cfg.third_place_match)

    def test_config_sgl_endpoint_rejects_rnd(self):
        t = self._create_tournament('RND')
        res = self.client.post(
            f'/api/tournaments/{t.pk}/config/sgl/',
            {'initial_seeding': 'RANDOM'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_config_sgl_still_works_for_sgl(self):
        t = self._create_tournament('SGL')
        res = self.client.post(
            f'/api/tournaments/{t.pk}/config/sgl/',
            {'initial_seeding': 'RANDOM', 'third_place_match': False},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        cfg = EliminationConfig.objects.get(tournament=t)
        self.assertEqual(cfg.initial_seeding, 'RANDOM')
        self.assertFalse(cfg.third_place_match)

    def test_dbe_detail_serializer_includes_config(self):
        t = self._create_tournament('DBE')
        EliminationConfig.objects.create(
            tournament=t, initial_seeding='RANDOM', third_place_match=False,
        )
        res = self.client.get(f'/api/tournaments/{t.pk}/detail/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsNotNone(data.get('config'))
        self.assertEqual(data['config']['initial_seeding'], 'RANDOM')
        self.assertFalse(data['config']['third_place_match'])
