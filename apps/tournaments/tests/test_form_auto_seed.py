from django.test import TestCase
from django.contrib.auth.models import User
from apps.tournaments.models import Tournament, Participant
from apps.tournaments.forms import ParticipantForm

class ParticipantFormAutoSeedTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.tournament = Tournament.objects.create(
            name='Test Tournament',
            tournament_type='SWS', # Swiss
            match_format='SNG',
            created_by=self.user,
            status='REG'
        )

    def test_initial_seed_empty_tournament(self):
        """Dla pustego turnieju seed powinien być 1."""
        form = ParticipantForm(tournament=self.tournament)
        self.assertEqual(form.initial.get('seed_number'), 1)

    def test_initial_seed_with_participants(self):
        """Dla turnieju z uczestnikami seed powinien być max + 1."""
        Participant.objects.create(tournament=self.tournament, display_name="P1", seed_number=1, user=self.user)
        Participant.objects.create(tournament=self.tournament, display_name="P2", seed_number=2, user=self.user)
        
        form = ParticipantForm(tournament=self.tournament)
        self.assertEqual(form.initial.get('seed_number'), 3)

    def test_initial_seed_edit_existing(self):
        """Przy edycji istniejącego uczestnika seed NIE powinien być nadpisywany nowym."""
        p1 = Participant.objects.create(tournament=self.tournament, display_name="P1", seed_number=1, user=self.user)
        # Tworzymy kolejnego, żeby max było np. 2, a nie 1 (choć i tak p1.seed=1)
        Participant.objects.create(tournament=self.tournament, display_name="P2", seed_number=2, user=self.user)
        
        form = ParticipantForm(instance=p1, tournament=self.tournament)
        # initial['seed_number'] nie powinno być ustawiane przez logikę "new seed"
        # Jeśli logika działa poprawnie, initial nie będzie zawierał wymuszonej wartości next_seed
        # W Django ModelForm initial jest pobierany z instancji, chyba że zostanie nadpisany w __init__.
        # My w __init__ nadpisywaliśmy. Teraz sprawdzamy, czy tego nie robimy.
        # Wartość powinna pochodzić z instancji (czyli 1), a nie być obliczonym next_seed (czyli 3).
        self.assertEqual(form.initial.get('seed_number'), 1) 

    def test_swap_seeds_existing(self):
        """Zamiana numerów między dwoma istniejącymi uczestnikami."""
        p1 = Participant.objects.create(tournament=self.tournament, display_name="P1", seed_number=1, user=self.user)
        p2 = Participant.objects.create(tournament=self.tournament, display_name="P2", seed_number=2, user=self.user)
        
        # Zmieniamy P1 seed na 2. Oczekujemy, że P2 dostanie seed 1.
        form = ParticipantForm(data={
            'display_name': 'P1',
            'seed_number': 2,
            'status': 'REG',
            'user': self.user.id
        }, instance=p1, tournament=self.tournament)
        
        self.assertTrue(form.is_valid())
        form.save()
        
        p1.refresh_from_db()
        p2.refresh_from_db()
        
        self.assertEqual(p1.seed_number, 2)
        self.assertEqual(p2.seed_number, 1) # P2 powinien przejąć stary numer P1

    def test_swap_seed_new_participant_collision(self):
        """Nowy uczestnik dostaje zajęty numer - konfliktowy przesuwa się na koniec."""
        p1 = Participant.objects.create(tournament=self.tournament, display_name="P1", seed_number=1, user=self.user)
        
        # Tworzymy nowego P2, ale wymuszamy seed 1
        form = ParticipantForm(data={
            'display_name': 'P2',
            'seed_number': 1,
            'status': 'REG',
            'user': self.user.id
        }, tournament=self.tournament)
        
        self.assertTrue(form.is_valid())
        form.save()
        
        p1.refresh_from_db()
        p2 = Participant.objects.get(display_name="P2")
        
        self.assertEqual(p2.seed_number, 1) # Nowy wziął 1
        self.assertEqual(p1.seed_number, 2) # Stary (P1) został przesunięty na 2 (max + 1)
