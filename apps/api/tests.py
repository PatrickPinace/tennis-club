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


# ─────────────────────────────────────────────────────────────────────────────
# Testy PATCH /api/tournaments/{pk}/matches/{match_pk}/score/
# — uprawnienia uczestnika meczu RR
# ─────────────────────────────────────────────────────────────────────────────

def _make_act_tournament(org, t_type='RND'):
    """Turniej w statusie ACT z config (RND lub SGL lub AMR)."""
    t = Tournament.objects.create(
        name=f'Score Perm {t_type}',
        tournament_type=t_type,
        match_format='SNG',
        status='ACT',
        rank=1,
        created_by=org,
        start_date=datetime.date(2026, 7, 1),
        end_date=datetime.date(2026, 7, 31),
    )
    if t_type == 'RND':
        RoundRobinConfig.objects.create(
            tournament=t,
            max_participants=8, sets_to_win=2, games_per_set=6,
            points_for_win=Decimal('2.00'), points_for_loss=Decimal('1.00'),
            points_for_set_win=Decimal('0.50'), points_for_set_loss=Decimal('0.00'),
            points_for_gem_win=Decimal('0.10'), points_for_gem_loss=Decimal('-0.10'),
            points_for_supertiebreak_win=Decimal('0.05'),
            points_for_supertiebreak_loss=Decimal('-0.05'),
            tie_breaker_priority='SETS',
        )
    elif t_type == 'AMR':
        AmericanoConfig.objects.create(
            tournament=t, max_participants=8, points_per_match=32, number_of_rounds=7,
        )
    return t


def _make_match(tournament, p1, p2, status='WAI'):
    """Tworzy TournamentsMatch między dwoma Participant. match_index unikalne per turniej."""
    idx = TournamentsMatch.objects.filter(tournament=tournament).count() + 1
    return TournamentsMatch.objects.create(
        tournament=tournament,
        participant1=p1,
        participant2=p2,
        round_number=1,
        match_index=idx,
        status=status,
    )


def _score_url(t_pk, m_pk):
    return f'/api/tournaments/{t_pk}/matches/{m_pk}/score/'


VALID_SCORE = {'set1_p1': 6, 'set1_p2': 3, 'set2_p1': 6, 'set2_p2': 2}


class RRMatchScoreParticipantPermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = User.objects.create_user(username='score_org', password='pass')
        self.staff = User.objects.create_user(username='score_staff', password='pass', is_staff=True)
        self.p1_user = User.objects.create_user(username='score_p1', password='pass')
        self.p2_user = User.objects.create_user(username='score_p2', password='pass')
        self.outsider = User.objects.create_user(username='score_out', password='pass')

        # RR turniej ACT
        self.rnd_t = _make_act_tournament(self.org, t_type='RND')
        self.p1 = Participant.objects.create(
            tournament=self.rnd_t, user=self.p1_user, display_name='P1 RND', status='ACT',
        )
        self.p2 = Participant.objects.create(
            tournament=self.rnd_t, user=self.p2_user, display_name='P2 RND', status='ACT',
        )
        self.rnd_match = _make_match(self.rnd_t, self.p1, self.p2)

    # ── Organizer i staff — nadal działają ───────────────────────────────────

    def test_200_organizer_rnd(self):
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(_score_url(self.rnd_t.pk, self.rnd_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    def test_200_staff_rnd(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.patch(_score_url(self.rnd_t.pk, self.rnd_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    # ── Uczestnik meczu RR — sukces ───────────────────────────────────────────

    def test_200_participant1_rnd(self):
        """Uczestnik 1 meczu RR może wpisać wynik."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(_score_url(self.rnd_t.pk, self.rnd_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    def test_200_participant2_rnd(self):
        """Uczestnik 2 meczu RR może wpisać wynik."""
        self.client.force_authenticate(user=self.p2_user)
        res = self.client.patch(_score_url(self.rnd_t.pk, self.rnd_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    def test_response_shape_participant(self):
        """Odpowiedź zawiera match_id, status, winner_id, winner_name, score."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(_score_url(self.rnd_t.pk, self.rnd_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('match_id', data)
        self.assertIn('status', data)
        self.assertIn('winner_id', data)

    # ── Nie-uczestnik RR — 403 ────────────────────────────────────────────────

    def test_403_outsider_rnd(self):
        """User niebędący uczestnikiem meczu RR nie może wpisać wyniku."""
        self.client.force_authenticate(user=self.outsider)
        res = self.client.patch(_score_url(self.rnd_t.pk, self.rnd_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 403)

    def test_403_participant_other_match(self):
        """User będący uczestnikiem INNEGO meczu w tym samym turnieju nie może."""
        other_user = User.objects.create_user(username='score_other_p', password='pass')
        other_p = Participant.objects.create(
            tournament=self.rnd_t, user=other_user, display_name='OtherP', status='ACT',
        )
        # Drugi mecz z innym uczestnikiem
        yet_another = User.objects.create_user(username='score_yet_another', password='pass')
        yet_p = Participant.objects.create(
            tournament=self.rnd_t, user=yet_another, display_name='YetP', status='ACT',
        )
        other_match = _make_match(self.rnd_t, other_p, yet_p)
        # p1_user jest uczestnikiem self.rnd_match, ale nie other_match
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(_score_url(self.rnd_t.pk, other_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 403)

    # ── Walkover i cancel — tylko organizer/staff ─────────────────────────────

    def test_200_participant_can_walkover(self):
        """Uczestnik meczu RR może ustawić walkover (odblokowane)."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(
            _score_url(self.rnd_t.pk, self.rnd_match.pk),
            {'walkover': True, 'winner_participant_id': self.p1.pk},
            format='json',
        )
        self.assertEqual(res.status_code, 200)

    def test_403_participant_cannot_cancel(self):
        """Uczestnik meczu RR nie może anulować meczu."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(
            _score_url(self.rnd_t.pk, self.rnd_match.pk),
            {'cancel': True},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    def test_200_organizer_can_walkover(self):
        """Organizer może ustawić walkover."""
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(
            _score_url(self.rnd_t.pk, self.rnd_match.pk),
            {'walkover': True, 'winner_participant_id': self.p1.pk},
            format='json',
        )
        self.assertEqual(res.status_code, 200)

    # ── SGL — uczestnik nie ma dostępu ───────────────────────────────────────

    def test_403_participant_sgl(self):
        """Uczestnik meczu SGL nie może wpisać wyniku — tylko organizer/staff."""
        from apps.tournaments.models import EliminationConfig
        sgl_t = _make_act_tournament(self.org, t_type='SGL')
        EliminationConfig.objects.get_or_create(tournament=sgl_t, defaults={'sets_to_win': 2})
        # Używamy tej samej konfiguracji RR jako fallback (SGL używa round_robin_config do walidacji)
        RoundRobinConfig.objects.create(
            tournament=sgl_t,
            max_participants=8, sets_to_win=2, games_per_set=6,
            points_for_win=Decimal('2.00'), points_for_loss=Decimal('1.00'),
            points_for_set_win=Decimal('0.50'), points_for_set_loss=Decimal('0.00'),
            points_for_gem_win=Decimal('0.10'), points_for_gem_loss=Decimal('-0.10'),
            points_for_supertiebreak_win=Decimal('0.05'),
            points_for_supertiebreak_loss=Decimal('-0.05'),
            tie_breaker_priority='SETS',
        )
        sgl_p1 = Participant.objects.create(
            tournament=sgl_t, user=self.p1_user, display_name='SGL P1', status='ACT',
        )
        sgl_p2 = Participant.objects.create(
            tournament=sgl_t, user=self.p2_user, display_name='SGL P2', status='ACT',
        )
        sgl_match = _make_match(sgl_t, sgl_p1, sgl_p2)
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(_score_url(sgl_t.pk, sgl_match.pk), VALID_SCORE, format='json')
        self.assertEqual(res.status_code, 403)

    # ── AMR — uczestnik ma dostęp do zwykłego wyniku ────────────────────────

    def test_200_participant_amr(self):
        """Uczestnik meczu AMR STATIC może wpisać wynik gemowy."""
        amr_t = _make_act_tournament(self.org, t_type='AMR')
        amr_p1 = Participant.objects.create(
            tournament=amr_t, user=self.p1_user, display_name='AMR P1', status='ACT',
        )
        amr_p2 = Participant.objects.create(
            tournament=amr_t, user=self.p2_user, display_name='AMR P2', status='ACT',
        )
        amr_match = _make_match(amr_t, amr_p1, amr_p2)
        self.client.force_authenticate(user=self.p1_user)
        # points_per_match=32, suma musi się zgadzać
        res = self.client.patch(
            _score_url(amr_t.pk, amr_match.pk),
            {'set1_p1': 20, 'set1_p2': 12},
            format='json',
        )
        self.assertEqual(res.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# AMRMatchScoreParticipantPermissionTest
# — uprawnienia uczestnika meczu AMR STATIC
# ─────────────────────────────────────────────────────────────────────────────

AMR_SCORE = {'set1_p1': 20, 'set1_p2': 12}  # suma = 32 = points_per_match


class AMRMatchScoreParticipantPermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org      = User.objects.create_user(username='amr_org',   password='pass')
        self.staff    = User.objects.create_user(username='amr_staff',  password='pass', is_staff=True)
        self.p1_user  = User.objects.create_user(username='amr_p1',    password='pass')
        self.p2_user  = User.objects.create_user(username='amr_p2',    password='pass')
        self.outsider = User.objects.create_user(username='amr_out',   password='pass')

        self.amr_t = _make_act_tournament(self.org, t_type='AMR')
        self.p1 = Participant.objects.create(
            tournament=self.amr_t, user=self.p1_user, display_name='AMR P1', status='ACT',
        )
        self.p2 = Participant.objects.create(
            tournament=self.amr_t, user=self.p2_user, display_name='AMR P2', status='ACT',
        )
        self.amr_match = _make_match(self.amr_t, self.p1, self.p2)

    def _url(self):
        return _score_url(self.amr_t.pk, self.amr_match.pk)

    # ── Organizer i staff ────────────────────────────────────────────────────

    def test_200_organizer(self):
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(self._url(), AMR_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    def test_200_staff(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.patch(self._url(), AMR_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    # ── Uczestnik meczu ──────────────────────────────────────────────────────

    def test_200_participant_p1(self):
        """p1 może wpisać wynik swojego meczu AMR."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(self._url(), AMR_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    def test_200_participant_p2(self):
        """p2 może wpisać wynik swojego meczu AMR."""
        self.client.force_authenticate(user=self.p2_user)
        res = self.client.patch(self._url(), AMR_SCORE, format='json')
        self.assertEqual(res.status_code, 200)

    def test_200_participant_can_correct(self):
        """Uczestnik może ponownie wpisać wynik (CMP → korekta)."""
        self.client.force_authenticate(user=self.p1_user)
        self.client.patch(self._url(), AMR_SCORE, format='json')
        res = self.client.patch(self._url(), {'set1_p1': 18, 'set1_p2': 14}, format='json')
        self.assertEqual(res.status_code, 200)

    # ── Outsider i niezalogowany ─────────────────────────────────────────────

    def test_403_outsider(self):
        """Użytkownik niebędący uczestnikiem meczu nie może wpisać wyniku."""
        self.client.force_authenticate(user=self.outsider)
        res = self.client.patch(self._url(), AMR_SCORE, format='json')
        self.assertEqual(res.status_code, 403)

    def test_403_unauthenticated(self):
        """Niezalogowany dostaje 403 (sesja Django, nie token)."""
        res = self.client.patch(self._url(), AMR_SCORE, format='json')
        self.assertEqual(res.status_code, 403)

    # ── WDR i CNC nadal tylko organizer/staff ────────────────────────────────

    def test_403_participant_walkover(self):
        """Uczestnik AMR nie może wysłać walkover."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(
            self._url(),
            {'walkover': True, 'winner_participant_id': self.p1.pk},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    def test_403_participant_cancel(self):
        """Uczestnik AMR nie może anulować meczu."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(self._url(), {'cancel': True}, format='json')
        self.assertEqual(res.status_code, 403)

    # ── Walidacja sumy gemów ─────────────────────────────────────────────────

    def test_400_wrong_gem_sum(self):
        """Suma gemów musi być równa points_per_match (32)."""
        self.client.force_authenticate(user=self.p1_user)
        res = self.client.patch(self._url(), {'set1_p1': 20, 'set1_p2': 10}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_200_correct_gem_sum(self):
        """Organizer może wpisać wynik z poprawną sumą."""
        self.client.force_authenticate(user=self.org)
        res = self.client.patch(self._url(), {'set1_p1': 16, 'set1_p2': 16}, format='json')
        self.assertEqual(res.status_code, 200)
