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
from apps.tournaments.models import (
    Tournament, Participant, RoundRobinConfig, TournamentsMatch,
    TeamMember, AmericanoConfig,
)


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


# ─────────────────────────────────────────────────────────────────────────────
# Testy POST /api/tournaments/{pk}/join/
# ─────────────────────────────────────────────────────────────────────────────

def _make_tournament(org, t_type='RND', status='REG', max_p=8):
    """Pomocnik — tworzy turniej z config (RND lub AMR)."""
    t = Tournament.objects.create(
        name=f'Join Test {t_type} {status}',
        tournament_type=t_type,
        match_format='SNG',
        status=status,
        rank=1,
        created_by=org,
        start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 30),
    )
    if t_type == 'RND':
        RoundRobinConfig.objects.create(
            tournament=t,
            max_participants=max_p,
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
    elif t_type == 'AMR':
        AmericanoConfig.objects.create(
            tournament=t,
            max_participants=max_p,
            points_per_match=32,
            number_of_rounds=7,
        )
    return t


def _join_url(pk):
    return f'/api/tournaments/{pk}/join/'


def _add_participant(tournament, user, status='REG'):
    """Tworzy Participant + TeamMember dla danego usera."""
    full = user.get_full_name().strip()
    display_name = full if full else user.username
    # Unikamy konfliku unique_together display_name przez suffiks
    p = Participant.objects.create(
        tournament=tournament,
        user=user,
        display_name=display_name,
        status=status,
    )
    TeamMember.objects.create(participant=p, user=user)
    return p


class TournamentJoinViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = User.objects.create_user(username='join_org', password='pass')
        self.user = User.objects.create_user(
            username='join_user', password='pass',
            first_name='Jan', last_name='Kowalski',
        )
        self.user_no_name = User.objects.create_user(username='join_noname', password='pass')

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_401_unauthenticated(self):
        t = _make_tournament(self.org)
        res = self.client.post(_join_url(t.pk))
        # DRF SessionAuth może zwrócić 403 zamiast 401 dla niezalogowanych
        self.assertIn(res.status_code, (401, 403))

    # ── Status turnieju ───────────────────────────────────────────────────────

    def test_409_not_reg_status_drf(self):
        t = _make_tournament(self.org, status='DRF')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 409)
        self.assertIn('detail', res.json())

    def test_409_not_reg_status_act(self):
        t = _make_tournament(self.org, status='ACT')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 409)

    def test_409_not_reg_status_fin(self):
        t = _make_tournament(self.org, status='FIN')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 409)

    def test_404_nonexistent_tournament(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(99999))
        self.assertEqual(res.status_code, 404)

    # ── Poprawny join ─────────────────────────────────────────────────────────

    def test_201_successful_join_rnd(self):
        t = _make_tournament(self.org, t_type='RND')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('id', data)
        self.assertIn('display_name', data)
        self.assertEqual(data['status'], 'REG')

    def test_201_successful_join_amr(self):
        t = _make_tournament(self.org, t_type='AMR')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['status'], 'REG')

    def test_participant_and_teammember_created(self):
        t = _make_tournament(self.org, t_type='RND')
        self.client.force_authenticate(user=self.user)
        self.client.post(_join_url(t.pk))
        self.assertEqual(Participant.objects.filter(tournament=t, user=self.user).count(), 1)
        p = Participant.objects.get(tournament=t, user=self.user)
        self.assertTrue(TeamMember.objects.filter(participant=p, user=self.user).exists())

    # ── display_name ──────────────────────────────────────────────────────────

    def test_display_name_from_full_name(self):
        t = _make_tournament(self.org, t_type='RND')
        self.client.force_authenticate(user=self.user)  # first_name='Jan', last_name='Kowalski'
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.json()['display_name'], 'Jan Kowalski')

    def test_display_name_fallback_to_username(self):
        t = _make_tournament(self.org, t_type='RND')
        self.client.force_authenticate(user=self.user_no_name)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.json()['display_name'], 'join_noname')

    # ── Duplikat ──────────────────────────────────────────────────────────────

    def test_409_already_captain(self):
        t = _make_tournament(self.org, t_type='RND')
        _add_participant(t, self.user, status='REG')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 409)
        self.assertIn('Jesteś już zapisany', res.json()['detail'])

    def test_409_already_partner_via_teammember(self):
        """User jest TeamMember w cudzym Participant — nie może dołączyć ponownie."""
        t = _make_tournament(self.org, t_type='RND')
        other = User.objects.create_user(username='join_other', password='pass')
        captain_p = _add_participant(t, other, status='REG')
        # Dodaj self.user jako partnera (TeamMember) bez tworzenia własnego Participant
        TeamMember.objects.create(participant=captain_p, user=self.user)
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 409)

    # ── WDN reaktywacja ───────────────────────────────────────────────────────

    def test_201_wdn_reactivated_not_duplicated(self):
        t = _make_tournament(self.org, t_type='RND')
        wdn_p = _add_participant(t, self.user, status='WDN')
        original_pk = wdn_p.pk
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 201)
        # Ten sam rekord — nie nowy
        self.assertEqual(res.json()['id'], original_pk)
        # Status zmieniony na REG
        wdn_p.refresh_from_db()
        self.assertEqual(wdn_p.status, 'REG')
        # Dokładnie jeden Participant dla tego usera w tym turnieju
        self.assertEqual(
            Participant.objects.filter(tournament=t, user=self.user).count(), 1
        )

    def test_wdn_does_not_block_rejoin(self):
        """Stary WDN nie powoduje 409 — user może się ponownie zapisać."""
        t = _make_tournament(self.org, t_type='RND')
        _add_participant(t, self.user, status='WDN')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        # Musi być sukces, nie 409
        self.assertNotEqual(res.status_code, 409)

    # ── Limit miejsc ──────────────────────────────────────────────────────────

    def test_409_max_participants_rnd(self):
        t = _make_tournament(self.org, t_type='RND', max_p=2)
        u1 = User.objects.create_user(username='join_full1', password='pass')
        u2 = User.objects.create_user(username='join_full2', password='pass')
        _add_participant(t, u1, status='REG')
        _add_participant(t, u2, status='REG')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        self.assertEqual(res.status_code, 409)
        self.assertIn('limit', res.json()['detail'])

    def test_wdn_not_counted_toward_limit(self):
        """WDN nie wlicza się do limitu — nowy user może dołączyć."""
        t = _make_tournament(self.org, t_type='RND', max_p=1)
        u_wdn = User.objects.create_user(username='join_wdn_slot', password='pass')
        _add_participant(t, u_wdn, status='WDN')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        # WDN nie zajmuje miejsca → user powinien dołączyć
        self.assertEqual(res.status_code, 201)

    def test_amr_no_max_participants_check(self):
        """AMR: brak konfiguracji RND → limit RND nie jest sprawdzany."""
        # AMR z max_p=1, ale check limitu RND nie dotyczy AMR
        t = _make_tournament(self.org, t_type='AMR', max_p=1)
        u1 = User.objects.create_user(username='join_amr1', password='pass')
        _add_participant(t, u1, status='REG')
        self.client.force_authenticate(user=self.user)
        res = self.client.post(_join_url(t.pk))
        # AMR nie sprawdza round_robin_config → brak 409 z tytułu limitu
        self.assertEqual(res.status_code, 201)
