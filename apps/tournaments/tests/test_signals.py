"""
Testy signala rebuild_rankings_on_tournament_finish.

Weryfikuje:
- signal odpala rebuild przy zmianie → FIN
- signal NIE odpala ponownie gdy status już był FIN
- signal NIE odpala przy tworzeniu turnieju ze statusem FIN
- signal NIE odpala gdy brak end_date
- signal NIE odpala dla innych statusów
"""
import datetime
from decimal import Decimal
from unittest.mock import patch, call
from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import Tournament, RoundRobinConfig


def _make_tournament(org, status='DRF', end_date=datetime.date(2026, 3, 31)):
    return Tournament.objects.create(
        name='Signal Test',
        tournament_type='RND',
        match_format='SNG',
        status=status,
        rank=1,
        created_by=org,
        start_date=datetime.date(2026, 1, 1),
        end_date=end_date,
    )


class RebuildSignalTest(TestCase):
    def setUp(self):
        self.org = User.objects.create_user(username='sig_org', password='pass')

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_triggers_on_status_change_to_fin(self, mock_rebuild):
        """DRF → FIN: rebuild powinien zostać wywołany."""
        t = _make_tournament(self.org, status='DRF')
        mock_rebuild.reset_mock()

        t.status = 'FIN'
        t.save()

        mock_rebuild.assert_called_once_with(match_type='SNG', season=2026)

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_no_trigger_if_already_fin(self, mock_rebuild):
        """FIN → FIN (ponowny save): rebuild NIE powinien być wywołany ponownie."""
        t = _make_tournament(self.org, status='DRF')
        t.status = 'FIN'
        t.save()
        mock_rebuild.reset_mock()

        # Drugi save bez zmiany statusu
        t.name = 'Updated name'
        t.save()

        mock_rebuild.assert_not_called()

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_no_trigger_on_create_with_fin(self, mock_rebuild):
        """Tworzenie turnieju ze statusem FIN: rebuild NIE powinien być wywołany."""
        Tournament.objects.create(
            name='Created FIN',
            tournament_type='RND',
            match_format='SNG',
            status='FIN',
            rank=1,
            created_by=self.org,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        mock_rebuild.assert_not_called()

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_no_trigger_without_end_date(self, mock_rebuild):
        """Brak end_date: rebuild NIE powinien być wywołany (nie ma sezonu)."""
        t = _make_tournament(self.org, status='DRF', end_date=None)
        mock_rebuild.reset_mock()

        t.status = 'FIN'
        t.save()

        mock_rebuild.assert_not_called()

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_no_trigger_for_other_statuses(self, mock_rebuild):
        """DRF → ACT / ACT → CNC: rebuild NIE powinien być wywołany."""
        t = _make_tournament(self.org, status='DRF')
        mock_rebuild.reset_mock()

        t.status = 'ACT'
        t.save()
        t.status = 'CNC'
        t.save()

        mock_rebuild.assert_not_called()

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_uses_correct_match_type_and_season(self, mock_rebuild):
        """Rebuild używa match_format turnieju i roku z end_date."""
        t = Tournament.objects.create(
            name='DBL Signal Test',
            tournament_type='RND',
            match_format='DBL',
            status='ACT',
            rank=1,
            created_by=self.org,
            start_date=datetime.date(2025, 6, 1),
            end_date=datetime.date(2025, 12, 31),
        )
        mock_rebuild.reset_mock()

        t.status = 'FIN'
        t.save()

        mock_rebuild.assert_called_once_with(match_type='DBL', season=2025)

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings', side_effect=Exception('DB error'))
    def test_exception_does_not_propagate(self, mock_rebuild):
        """Błąd w rebuild nie powinien propagować się do save() — turniej zapisany mimo błędu."""
        t = _make_tournament(self.org, status='DRF')

        # save() nie powinno rzucać wyjątku
        t.status = 'FIN'
        t.save()

        # Turniej zapisany mimo błędu rebuild
        t.refresh_from_db()
        self.assertEqual(t.status, 'FIN')

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_no_trigger_for_unranked_tournament(self, mock_rebuild):
        """is_ranked=False → FIN: rebuild NIE powinien być wywołany (turniej towarzyski)."""
        t = Tournament.objects.create(
            name='Towarzyski test',
            tournament_type='RND',
            match_format='SNG',
            status='DRF',
            rank=1,
            is_ranked=False,
            created_by=self.org,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        mock_rebuild.reset_mock()

        t.status = 'FIN'
        t.save()

        mock_rebuild.assert_not_called()

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_trigger_for_ranked_tournament(self, mock_rebuild):
        """is_ranked=True (domyślnie) → FIN: rebuild powinien zostać wywołany."""
        t = Tournament.objects.create(
            name='Rankingowy test',
            tournament_type='RND',
            match_format='SNG',
            status='DRF',
            rank=1,
            is_ranked=True,
            created_by=self.org,
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        mock_rebuild.reset_mock()

        t.status = 'FIN'
        t.save()

        mock_rebuild.assert_called_once_with(match_type='SNG', season=2026)

    @patch('apps.rankings.services.ranking_calculator.rebuild_rankings')
    def test_unranked_tournament_excluded_from_ranking_calculation(self, mock_rebuild):
        """
        Turniej is_ranked=False nie powinien wpływać na PlayerRanking.

        Weryfikuje Q(tournament__is_ranked=True) w _build_filters przez
        sprawdzenie, że calculate_rankings() ignoruje mecze z turnieju unranked.
        """
        from django.contrib.auth.models import User as DjangoUser
        from apps.tournaments.models import Participant, TournamentsMatch
        from apps.rankings.services.ranking_calculator import calculate_rankings
        from apps.rankings.models import PlayerRanking

        player = DjangoUser.objects.create_user(username='calc_player', password='pass')

        # Turniej rankingowy (FIN, is_ranked=True)
        ranked_t = Tournament.objects.create(
            name='Ranked T', tournament_type='RND', match_format='SNG',
            status='FIN', rank=1, is_ranked=True, created_by=self.org,
            start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 3, 31),
        )
        # Turniej towarzyski (FIN, is_ranked=False)
        unranked_t = Tournament.objects.create(
            name='Unranked T', tournament_type='RND', match_format='SNG',
            status='FIN', rank=1, is_ranked=False, created_by=self.org,
            start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 3, 31),
        )

        # Uczestnik w obu turniejach
        p_ranked = Participant.objects.create(
            tournament=ranked_t, user=player, display_name='Player', status='ACT',
        )
        p_unranked = Participant.objects.create(
            tournament=unranked_t, user=player, display_name='Player', status='ACT',
        )

        # Mecz wygrany w turnieju rankingowym
        m_ranked = TournamentsMatch.objects.create(
            tournament=ranked_t, round_number=1, match_index=0,
            participant1=p_ranked, status='CMP',
            set1_p1_score=6, set1_p2_score=3,
            set2_p1_score=6, set2_p2_score=2,
            winner=p_ranked,
        )
        p_ranked.won_matches.add(m_ranked)

        # Mecz wygrany w turnieju towarzyskim
        m_unranked = TournamentsMatch.objects.create(
            tournament=unranked_t, round_number=1, match_index=0,
            participant1=p_unranked, status='CMP',
            set1_p1_score=6, set1_p2_score=0,
            set2_p1_score=6, set2_p2_score=0,
            winner=p_unranked,
        )
        p_unranked.won_matches.add(m_unranked)

        results = calculate_rankings(match_type='SNG', season=2026)
        player_row = next((r for r in results if r['user_id'] == player.pk), None)

        # Gracz powinien pojawić się w rankingu (1 mecz z ranked_t)
        self.assertIsNotNone(player_row, 'Gracz nie znaleziony w calculate_rankings — brak meczów z turnieju rankingowego.')
        # Tylko 1 wygrana z ranked_t, mecz z unranked_t nie liczony
        self.assertEqual(player_row['matches_won'], 1,
            f'Oczekiwano 1 wygranej (tylko ranked_t), otrzymano {player_row["matches_won"]}.')
        self.assertEqual(player_row['matches_played'], 1,
            f'Oczekiwano 1 meczu (tylko ranked_t), otrzymano {player_row["matches_played"]}.')
