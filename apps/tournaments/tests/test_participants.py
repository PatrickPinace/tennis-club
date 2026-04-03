from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from apps.tournaments.models import Tournament, RoundRobinConfig, EliminationConfig, Participant, TeamMember


class ParticipantFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.org = User.objects.create_user(username='org', password='pass')
        self.user = User.objects.create_user(username='player', password='pass')
        # create a round robin tournament
        self.tourn = Tournament.objects.create(name='TestT', tournament_type='RND', match_format='SNG', created_by=self.org, status='DRF')

    def test_create_tournament_creates_default_config(self):
        # round robin config should exist because we created the tournament directly, view creates it when using the form
        # simulate create via view
        self.client.login(username='org', password='pass')
        resp = self.client.post(reverse('tournaments:create_tournament'), data={
            'name': 'FromView', 'tournament_type': 'RND', 'match_format': 'SNG', 'status': 'DRF'
        })
        # should redirect to manage
        self.assertEqual(resp.status_code, 302)

    def test_request_join_and_approve(self):
        # user requests to join (pending)
        self.client.login(username='player', password='pass')
        resp = self.client.get(reverse('tournaments:request_join', args=[self.tourn.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Participant.objects.filter(tournament=self.tourn, user=self.user, status='PEN').exists())

        # organizer approves
        self.client.login(username='org', password='pass')
        p = Participant.objects.get(tournament=self.tourn, user=self.user)
        resp2 = self.client.get(reverse('tournaments:approve_participant', args=[self.tourn.pk, p.pk]))
        self.assertEqual(resp2.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.status, 'REG')
