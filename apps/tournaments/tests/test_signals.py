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
