from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from apps.tournaments.models import Tournament, Participant, TeamMember, TournamentsMatch

class MyActiveMatchesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = User.objects.create_user(username='org', password='pass')
        self.player1 = User.objects.create_user(username='player1', password='pass')
        self.player2 = User.objects.create_user(username='player2', password='pass')
        self.player3 = User.objects.create_user(username='player3', password='pass')

        # Active Tournament
        self.tourn_active = Tournament.objects.create(
            name='Active Tourn', tournament_type='RND', match_format='SNG',
            created_by=self.org, status='ACT'
        )

        # Inactive/Draft Tournament
        self.tourn_draft = Tournament.objects.create(
            name='Draft Tourn', tournament_type='RND', match_format='SNG',
            created_by=self.org, status='DRF'
        )

        # Participants in Active Tournament
        self.p1 = Participant.objects.create(
            tournament=self.tourn_active, user=self.player1, display_name='P1', status='ACT'
        )
        self.p2 = Participant.objects.create(
            tournament=self.tourn_active, user=self.player2, display_name='P2', status='ACT'
        )
        self.p3 = Participant.objects.create(
            tournament=self.tourn_active, user=self.player3, display_name='P3', status='ACT'
        )

        # Match 1: Player 1 vs Player 2 (active match)
        self.match1 = TournamentsMatch.objects.create(
            tournament=self.tourn_active,
            participant1=self.p1,
            participant2=self.p2,
            round_number=1,
            match_index=1,
            status='SCH'
        )

        # Match 2: Player 1 vs Player 3 (completed match)
        self.match2 = TournamentsMatch.objects.create(
            tournament=self.tourn_active,
            participant1=self.p1,
            participant2=self.p3,
            round_number=1,
            match_index=2,
            status='CMP'
        )

        # Match 3: Player 2 vs Player 3 (active match)
        self.match3 = TournamentsMatch.objects.create(
            tournament=self.tourn_active,
            participant1=self.p2,
            participant2=self.p3,
            round_number=1,
            match_index=3,
            status='SCH'
        )

        # Match in draft tournament (should be filtered out)
        p1_draft = Participant.objects.create(
            tournament=self.tourn_draft, user=self.player1, display_name='P1 Draft', status='REG'
        )
        p2_draft = Participant.objects.create(
            tournament=self.tourn_draft, user=self.player2, display_name='P2 Draft', status='REG'
        )
        self.match_draft = TournamentsMatch.objects.create(
            tournament=self.tourn_draft,
            participant1=p1_draft,
            participant2=p2_draft,
            round_number=1,
            match_index=1,
            status='SCH'
        )

    def test_anonymous_user_cannot_access(self):
        url = reverse('tournament-my-active-matches')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_player1_sees_only_own_active_matches_in_active_tournaments(self):
        self.client.login(username='player1', password='pass')
        url = reverse('tournament-my-active-matches')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        
        data = resp.json()
        match_ids = [m['id'] for m in data]

        # Player 1 should see match1 (active), but not match2 (completed), match3 (doesn't play in it), or match_draft (draft tourn)
        self.assertIn(self.match1.id, match_ids)
        self.assertNotIn(self.match2.id, match_ids)
        self.assertNotIn(self.match3.id, match_ids)
        self.assertNotIn(self.match_draft.id, match_ids)

    def test_organizer_sees_all_active_matches_in_active_tournaments(self):
        self.client.login(username='org', password='pass')
        url = reverse('tournament-my-active-matches')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        match_ids = [m['id'] for m in data]

        # Organizer should see match1 and match3 (all active matches in their active tournament)
        self.assertIn(self.match1.id, match_ids)
        self.assertIn(self.match3.id, match_ids)
        self.assertNotIn(self.match2.id, match_ids)  # match2 is CMP (completed)
        self.assertNotIn(self.match_draft.id, match_ids)  # match_draft is in draft tourn
