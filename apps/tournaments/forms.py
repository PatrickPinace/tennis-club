from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.contrib.auth.models import User
from .models import Tournament, RoundRobinConfig, EliminationConfig, LadderConfig, AmericanoConfig, SwissSystemConfig, Participant, TeamMember, TournamentsMatch


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            'name',
            'description',
            'start_date',
            'end_date',
            'tournament_type',
            'facility',
            'match_format',
            'rank',
            'status',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
            'tournament_type': forms.Select(attrs={'class': 'form-select'}),
            'facility': forms.Select(attrs={'class': 'form-select'}),
            'match_format': forms.Select(attrs={'class': 'form-select'}),
            'rank': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure datetime-local initial rendering when editing existing instance
        for field_name in ('start_date', 'end_date'):
            if self.instance and getattr(self.instance, field_name):
                dt = getattr(self.instance, field_name)
                # Format according to input's expected format
                try:
                    self.initial[field_name] = dt.strftime('%Y-%m-%dT%H:%M')
                except Exception:
                    pass
        # Zmiana etykiet
        self.fields['name'].label = 'Nazwa'
        self.fields['description'].label = 'Opis'
        self.fields['start_date'].label = 'Data rozpoczęcia'
        self.fields['end_date'].label = 'Data zakończenia'
        self.fields['tournament_type'].label = 'Rodzaj Turnieju'
        self.fields['facility'].label = 'Obiekt Tenisowy'
        # Ustawienie pola jako opcjonalne, zgodnie z modelem (blank=True, null=True)
        self.fields['facility'].required = False
        self.fields['match_format'].label = 'Format Meczu'
        self.fields['rank'].label = 'Ranga Turnieju'

    def clean(self):
        cleaned = super().clean()

        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        # Jeśli podano jedną z dat, druga również jest wymagana.
        if (start and not end) or (end and not start):
            self.add_error('start_date', 'Obie daty (rozpoczęcia i zakończenia) muszą być podane, albo obie muszą być puste.')
            self.add_error('end_date', 'Obie daty (rozpoczęcia i zakończenia) muszą być podane, albo obie muszą być puste.')
        if start and end and end < start:
            self.add_error('end_date', 'Data zakończenia musi być późniejsza lub równa dacie rozpoczęcia.')
        return cleaned


class RoundRobinConfigForm(forms.ModelForm):
    class Meta:
        model = RoundRobinConfig
        # Exclude tournament OneToOne field; usually set from the view
        exclude = ('tournament',)
        widgets = {
            'max_participants': forms.NumberInput(attrs={'class': 'form-control', 'min': 2}),
            'sets_to_win': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'games_per_set': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'points_for_win': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'points_for_loss': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'points_for_set_win': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'points_for_set_loss': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'points_for_gem_win': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'points_for_gem_loss': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'points_for_supertiebreak_win': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'points_for_supertiebreak_loss': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tie_breaker_priority': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['max_participants'].label = 'Maksymalna liczba zawodników'
        self.fields['sets_to_win'].label = 'Ilość setów, aby wygrać mecz'
        self.fields['games_per_set'].label = 'Ilość gemów w secie'
        self.fields['points_for_win'].label = 'Punkty za wygraną'
        self.fields['points_for_loss'].label = 'Punkty za przegraną'
        self.fields['points_for_set_win'].label = 'Wygrany set'
        self.fields['points_for_set_loss'].label = 'Przegrany set'
        self.fields['points_for_gem_win'].label = 'Wygrany gem'
        self.fields['points_for_gem_loss'].label = 'Przegrany gem'
        self.fields['points_for_supertiebreak_win'].label = 'Wygrany punkt w supertiebreak'
        self.fields['points_for_supertiebreak_loss'].label = 'Przegrany punkt w supertiebreak'
        self.fields['tie_breaker_priority'].label = 'Kolejność w przypadku takiej samej liczby punktów'

    def clean(self):
        cleaned = super().clean()
        max_p = cleaned.get('max_participants')
        sets = cleaned.get('sets_to_win')
        games = cleaned.get('games_per_set')
        if max_p is not None and int(max_p) < 4:
            self.add_error('max_participants', 'Musi być co najmniej 4 uczestników.')
        if sets is not None and sets < 1:
            self.add_error('sets_to_win', 'Liczba setów do wygranej musi być co najmniej 1.')
        if games is not None and games < 1:
            self.add_error('games_per_set', 'Liczba gemów w secie musi być co najmniej 1.')
        return cleaned


class EliminationConfigForm(forms.ModelForm):
    BRACKET_SIZE_CHOICES = [
        (4, '4'),
        (8, '8'),
        (16, '16'),
        (32, '32'),
        (64, '64'),
    ]
    max_participants = forms.ChoiceField(
        choices=BRACKET_SIZE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = EliminationConfig
        exclude = ('tournament',)
        widgets = {
            'sets_to_win': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'games_per_set': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'initial_seeding': forms.Select(attrs={'class': 'form-select'}),
            'third_place_match': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['max_participants'].label = 'Maksymalna liczba zawodników'
        self.fields['sets_to_win'].label = 'Ilość setów, aby wygrać mecz'
        self.fields['games_per_set'].label = 'Ilość gemów w secie'
        self.fields['initial_seeding'].label = 'Parowanie 1. rundy'
        self.fields['third_place_match'].label = 'Mecz o trzecie miejsce'

    def clean(self):
        cleaned = super().clean()
        max_p = cleaned.get('max_participants')
        sets = cleaned.get('sets_to_win')
        games = cleaned.get('games_per_set')
        if max_p is not None and int(max_p) < 4:
            self.add_error('max_participants', 'Musi być co najmniej 4 uczestników.')
        if sets is not None and sets < 1:
            self.add_error('sets_to_win', 'Liczba setów do wygranej musi być co najmniej 1.')
        if games is not None and games < 1:
            self.add_error('games_per_set', 'Liczba gemów w secie musi być co najmniej 1.')
        return cleaned


class LadderConfigForm(forms.ModelForm):
    class Meta:
        model = LadderConfig
        exclude = ('tournament',)
        widgets = {
            'max_participants': forms.NumberInput(attrs={'class': 'form-control', 'min': 2}),
            'sets_to_win': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'games_per_set': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'challenge_range': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'initial_seeding': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['max_participants'].label = 'Maksymalna liczba zawodników'
        self.fields['sets_to_win'].label = 'Ilość setów, aby wygrać mecz'
        self.fields['games_per_set'].label = 'Ilość gemów w secie'
        self.fields['challenge_range'].label = 'Zasięg wyzwania (ile pozycji w górę)'
        self.fields['initial_seeding'].label = 'Początkowe rozstawienie'

    def clean(self):
        cleaned = super().clean()
        max_p = cleaned.get('max_participants')
        sets = cleaned.get('sets_to_win')
        games = cleaned.get('games_per_set')
        challenge_range = cleaned.get('challenge_range')
        if max_p is not None and int(max_p) < 4:
            self.add_error('max_participants', 'Musi być co najmniej 4 uczestników.')
        if sets is not None and sets < 1:
            self.add_error('sets_to_win', 'Liczba setów do wygranej musi być co najmniej 1.')
        if games is not None and games < 1:
            self.add_error('games_per_set', 'Liczba gemów w secie musi być co najmniej 1.')
        if challenge_range is not None and challenge_range < 1:
            self.add_error('challenge_range', 'Zasięg wyzwania musi wynosić co najmniej 1.')
        return cleaned


class AmericanoConfigForm(forms.ModelForm):
    PARTICIPANT_CHOICES = [
        (4, '4'),
        (8, '8'),
        (16, '16'),
        (32, '32'),
    ]
    max_participants = forms.ChoiceField(
        choices=PARTICIPANT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class Meta:
        model = AmericanoConfig
        exclude = ('tournament',)
        widgets = {
            'points_per_match': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'number_of_rounds': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'scheduling_type': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['max_participants'].label = 'Maksymalna liczba uczestników (wielokrotność 4)'
        self.fields['points_per_match'].label = 'Liczba punktów na mecz'
        self.fields['number_of_rounds'].label = 'Liczba rund'
        self.fields['scheduling_type'].label = 'System kojarzenia'

    def clean_max_participants(self):
        # Ponieważ używamy ChoiceField, wartość zawsze będzie jedną z opcji.
        # Musimy ją jednak skonwertować na liczbę całkowitą.
        max_p_str = self.cleaned_data.get('max_participants')
        if max_p_str:
            return int(max_p_str)
        return None



class SwissSystemConfigForm(forms.ModelForm):
    class Meta:
        model = SwissSystemConfig
        exclude = ('tournament',)
        widgets = {
            'initial_seeding': forms.Select(attrs={'class': 'form-select'}),
            'sets_to_win': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'games_per_set': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'max_participants': forms.Select(choices=[(4, '4'), (8, '8'), (16, '16'), (32, '32'), (64, '64')], attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['initial_seeding'].label = 'Parowanie 1. rundy'
        self.fields['sets_to_win'].label = 'Ilość setów, aby wygrać mecz'
        self.fields['games_per_set'].label = 'Ilość gemów w secie'
        self.fields['max_participants'].label = 'Max uczestników'


class AmericanoMatchForm(forms.ModelForm):
    """Formularz do wprowadzania wyników w meczu Americano."""
    class Meta:
        model = TournamentsMatch
        fields = ['set1_p1_score', 'set1_p2_score']
        widgets = {
            'set1_p1_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'set1_p2_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        self.tournament = kwargs.pop('tournament', None)
        super().__init__(*args, **kwargs)

        # Dynamiczne etykiety na podstawie składów
        if self.instance and self.instance.pk:
            p1 = self.instance.participant1.display_name if self.instance.participant1 else 'Gracz 1'
            p2 = self.instance.participant2.display_name if self.instance.participant2 else 'Gracz 2'
            p3 = self.instance.participant3.display_name if self.instance.participant3 else 'Gracz 3'
            p4 = self.instance.participant4.display_name if self.instance.participant4 else 'Gracz 4'
            self.fields['set1_p1_score'].label = f"Punkty: {p1} / {p2}"
            self.fields['set1_p2_score'].label = f"Punkty: {p3} / {p4}"

    def clean(self):
        cleaned_data = super().clean()
        score1 = cleaned_data.get('set1_p1_score')
        score2 = cleaned_data.get('set1_p2_score')

        if score1 is None or score2 is None:
            raise ValidationError("Oba wyniki muszą zostać podane.")

        if self.tournament and self.tournament.config:
            points_per_match = self.tournament.config.points_per_match
            if score1 + score2 != points_per_match:
                raise ValidationError(f"Suma punktów musi wynosić dokładnie {points_per_match}.")

        # Automatyczne ustawienie statusu na zakończony
        cleaned_data['status'] = TournamentsMatch.Status.COMPLETED.value
        cleaned_data['winner'] = None # W Americano nie ma jednego zwycięzcy meczu
        return cleaned_data


class UserSelectWidget(forms.Select):
    """Niestandardowy widget, który dodaje atrybut data-full-name do opcji."""
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        # Metoda create_option jest wywoływana z obiektem ModelChoiceIteratorValue jako 'value'
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        # Sprawdzamy, czy 'value' istnieje i ma atrybut 'instance' (co jest typowe dla ModelChoiceIteratorValue)
        if value and hasattr(value, 'instance'):
            user = value.instance
            option['attrs']['data-full-name'] = user.get_full_name() or user.username
        return option


class ParticipantForm(forms.ModelForm):
    # Zmieniamy pole na takie, które pozwoli na wyszukiwanie
    user = forms.ModelChoiceField(
        # Sortujemy użytkowników po imieniu i nazwisku, wykluczając superużytkowników
        queryset=User.objects.filter(is_superuser=False).order_by('first_name', 'last_name'),
        # Dodajemy pustą etykietę, aby pole nie było domyślnie wypełnione
        empty_label="Wybierz użytkownika",
        widget=UserSelectWidget(attrs={'class': 'form-select'}),
        label="Użytkownik"
    )
    class Meta:
        model = Participant
        # tournament powinien być ustawiony z widoku
        exclude = ('tournament', 'created_at')
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'seed_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        # Możesz przekazać tournament=tournament do konstruktora, by walidować unikalność
        self.tournament = kwargs.pop('tournament', None)
        super().__init__(*args, **kwargs)
        # Dodajemy atrybut, który umożliwi wykorzystanie biblioteki do wyszukiwania (np. Select2)
        self.fields['user'].widget.attrs.update({'data-control': 'select2'})

        # Ustawiamy, aby w dropdownie wyświetlała się pełna nazwa użytkownika
        self.fields['user'].label_from_instance = lambda obj: obj.get_full_name() or obj.username
        self.fields['display_name'].label = 'Nazwa wyświetlana'
        self.fields['seed_number'].label = 'Numer w turnieju'

        if self.tournament and not self.instance.pk:
            max_seed = self.tournament.participants.aggregate(Max('seed_number'))['seed_number__max']
            next_seed = (max_seed or 0) + 1
            self.initial['seed_number'] = next_seed

        # Zapamiętaj oryginalny numer seed, aby wykryć zmiany
        self.old_seed_number = self.instance.seed_number if self.instance.pk else None

    def save(self, commit=True):
        instance = super().save(commit=False)
        if hasattr(self, 'tournament') and self.tournament and not instance.tournament_id:
            instance.tournament = self.tournament
        
        # Jeśli numer seed został zmieniony
        if instance.seed_number and instance.seed_number != self.old_seed_number:
            # Sprawdź konflikt w tym samym turnieju
            colliding_participant = Participant.objects.filter(
                tournament=self.tournament,
                seed_number=instance.seed_number
            ).exclude(pk=instance.pk).first()

            if colliding_participant:
                # Jeśli jest konflikt, podmień numer u kolidującego uczestnika
                # Ustaw mu stary numer edytowanego uczestnika (lub nowy wolny, jeśli brak starego, ale tu zakładamy swap)
                # W przypadku nowego uczestnika (old_seed=None), swap z nowym numerem jest ryzykowny,
                # ale logicznie dla nowego uczestnika 'next_seed' jest wolny, więc konflikt wystąpi tylko przy ręcznej zmianie.
                # Wtedy 'swap' może oznaczać, że tamten dostaje numer, który "zwolniłby się" gdybyśmy nie zajmowali,
                # ale dla nowego uczestnika nie zwalniamy nic.
                # Przyjmijmy logikę requested: "gracz który miał 1 będzie miał 3" (gdzie 3 to stary numer edytowanego/1).
                
                if self.old_seed_number:
                    colliding_participant.seed_number = self.old_seed_number
                    colliding_participant.save()
                else:
                    # Sytuacja: Tworzymy nowego (dostał np. 9), user zmienia na 1.
                    # Gracz 1 ma dostać... co?
                    # User: "jesli nie a jeszcze nikogo zarejestrowanego to wówczas numer 1" - to przy tworzeniu.
                    # User o swapie: "zmiana numeru ... gracz który miał 1 będzie miał 3, a gracz 3 będzie miał 1".
                    # To sugeruje zamianę dwóch istniejących.
                    # Jeśli tworzymy nowego i zabieramy komuś numer, to ten ktoś traci numer?
                    # Bezpieczniej: Przesuń kolidującego na pierwszy wolny (koniec kolejki) lub po prostu zamień?
                    # Ale nowy nie ma "starego numeru" do oddania.
                    # W takim wypadku logiczne wydaje się przesunięcie kolidującego na 'next_seed' (który był pierwotnie proponowany).
                    # Obliczamy jeszcze raz next_seed dla pewności (z uwzględnieniem że nowy zajmuje 'instance.seed_number')
                    # Ale 'next_seed' z inita byłby dobry.
                    # Użyjmy logiki: collided dostaje seed = max + 1 (czyli idzie na koniec).
                    max_seed = self.tournament.participants.aggregate(Max('seed_number'))['seed_number__max']
                    colliding_participant.seed_number = (max_seed or 0) + 1
                    colliding_participant.save()

        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def clean(self):
        cleaned = super().clean()
        display_name = cleaned.get('display_name')
        if self.tournament and display_name:
            qs = Participant.objects.filter(tournament=self.tournament, display_name=display_name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('display_name', 'W tym turnieju istnieje już uczestnik o tej nazwie.')
        return cleaned


class TeamMemberForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_superuser=False).order_by('first_name', 'last_name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Użytkownik',
        help_text='Wyszukaj i wybierz użytkownika, którego chcesz dodać do zespołu.'
    )

    class Meta:
        model = TeamMember
        exclude = ('participant',)

    def __init__(self, *args, **kwargs):
        self.participant = kwargs.pop('participant', None)
        super().__init__(*args, **kwargs)

        self.fields['user'].widget.attrs.update({'data-control': 'select2'})
        self.fields['user'].label_from_instance = lambda obj: obj.get_full_name() or obj.username

        if self.participant:
            # Wyklucz użytkowników, którzy już są w tym zespole
            # --- POPRAWKA: Przy edycji nie wykluczaj samego siebie z listy ---
            existing_members = self.participant.members.all()
            if self.instance and self.instance.pk:
                existing_members = existing_members.exclude(pk=self.instance.pk)
            existing_member_ids = existing_members.values_list('user_id', flat=True)
            self.fields['user'].queryset = self.fields['user'].queryset.exclude(id__in=existing_member_ids)

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get('user')
        if self.participant and user:
            # sprawdź, czy turniej obsługuje deble
            if self.participant.tournament.match_format != 'DBL':
                raise ValidationError('Ten formularz jest używany tylko dla turniejów deblowych.')
            qs = TeamMember.objects.filter(participant=self.participant, user=user)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('user', 'Ten użytkownik jest już członkiem tego zespołu.')
        return cleaned


class TournamentsMatchForm(forms.ModelForm):
    """Formularz do edycji danych meczu, w tym wyników setów."""
    class Meta:
        model = TournamentsMatch
        fields = [
            'participant1',
            'participant2',
            'round_number',
            'match_index',
            'status',
            'scheduled_time',
            'set1_p1_score', 'set1_p2_score',
            'set2_p1_score', 'set2_p2_score',
            'set3_p1_score', 'set3_p2_score',
            'winner',
        ]
        widgets = {
            'participant1': forms.Select(attrs={'class': 'form-select'}),
            'participant2': forms.Select(attrs={'class': 'form-select'}),
            'round_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'match_index': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),

            # Pola wyników setów (używamy małych pól wejściowych)
            'set1_p1_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set1_p2_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set2_p1_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set2_p2_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set3_p1_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set3_p2_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),

            'winner': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        # Pobieramy dodatkowe argumenty przekazane z widoku
        tournament = kwargs.pop('tournament', None)
        user = kwargs.pop('user', None)
        self.has_full_permissions = kwargs.pop('has_full_permissions', False)
        can_start_match = kwargs.pop('can_start_match', False)
        self.tournament = tournament  # Przechowujemy turniej na potrzeby metody clean()
        super().__init__(*args, **kwargs)

        # Zmiana etykiet dla uczestników
        if 'participant1' in self.fields:
            self.fields['participant1'].label = 'Zawodnik 1'
        if 'participant2' in self.fields:
            self.fields['participant2'].label = 'Zawodnik 2'

        # Zmiana etykiet dla rundy, indeksu
        if 'round_number' in self.fields:
            self.fields['round_number'].label = 'Runda'
        if 'match_index' in self.fields:
            self.fields['match_index'].label = 'Index'
        if 'scheduled_time' in self.fields:
            self.fields['scheduled_time'].label = 'Data i Godzina Spotkania'

        # Ustawiamy label dla 'winner' na 'Zwycięzca' i dodajemy opcję 'Brak'
        if 'winner' in self.fields:
            self.fields['winner'].label = 'Zwycięzca'
            # Upewniamy się, że to pole nie jest wymagane, co pozwoli na wybranie pustej opcji
            self.fields['winner'].required = False

        # Ograniczanie pól wyboru (ForeignKey) do uczestników danego turnieju
        if tournament:
            participant_qs = Participant.objects.filter(tournament=tournament)
            if 'participant1' in self.fields:
                self.fields['participant1'].queryset = participant_qs
            if 'participant2' in self.fields:
                self.fields['participant2'].queryset = participant_qs

            if 'winner' in self.fields:
                # Jeśli edytujemy istniejący mecz, ograniczamy wybór zwycięzcy
                # do uczestników tego konkretnego meczu.
                if self.instance and self.instance.pk:
                    participant_ids = []
                    if self.instance.participant1_id:
                        participant_ids.append(self.instance.participant1_id)
                    if self.instance.participant2_id:
                        participant_ids.append(self.instance.participant2_id)
                    self.fields['winner'].queryset = Participant.objects.filter(pk__in=participant_ids)
                else:
                    # Dla nowych meczów, pozwalamy wybrać spośród wszystkich uczestników turnieju.
                    self.fields['winner'].queryset = participant_qs
        else:
            # Jeśli nie ma kontekstu turnieju, ustawiamy pusty QuerySet
            if 'participant1' in self.fields:
                self.fields['participant1'].queryset = Participant.objects.none()
            if 'participant2' in self.fields:
                self.fields['participant2'].queryset = Participant.objects.none()
            if 'winner' in self.fields:
                self.fields['winner'].queryset = Participant.objects.none()
        
        # Jeśli użytkownik nie jest organizatorem, wyłączamy edycję pól strukturalnych
        if user and tournament and user != tournament.created_by:
            # Pola, które mają być tylko do odczytu dla uczestników
            readonly_fields = ['round_number', 'match_index', 'participant1', 'participant2']
            for field_name in readonly_fields:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

        # Dodatkowa opcja: Możesz zmienić domyślny tekst opcji "--------" na "Brak Zwycięzcy"
        if 'winner' in self.fields:
            self.fields['winner'].empty_label = '--- Brak Zwycięzcy ---' 

        # --- ZMIANA: Blokuj zmianę statusu, jeśli mecz jest już zakończony/odwołany ---
        if self.instance and self.instance.pk:
            non_editable_statuses = [
                TournamentsMatch.Status.COMPLETED.value,
                TournamentsMatch.Status.WITHDRAWN.value,
                TournamentsMatch.Status.CANCELLED.value,
            ]
            if self.instance.status in non_editable_statuses:
                if 'status' in self.fields:
                    self.fields['status'].disabled = True
        
        # --- ZMIANA: Odblokuj pole statusu dla użytkowników, którzy mogą tylko rozpocząć mecz ---
        if can_start_match:
            if 'status' in self.fields:
                self.fields['status'].disabled = False

    def clean(self):
        """
        Automatycznie oblicza zwycięzcę na podstawie wyników setów i konfiguracji turnieju.
        """
        cleaned_data = super().clean()
        status = cleaned_data.get('status')

        # --- ZMIANA: Logika dla użytkowników z ograniczonymi uprawnieniami ---
        # Jeśli użytkownik nie ma pełnych uprawnień...
        if not self.has_full_permissions:
            # ...i próbuje ustawić status inny niż "W trakcie", zablokuj to.
            if status and status != TournamentsMatch.Status.IN_PROGRESS.value:
                self.add_error('status', 'Nie masz uprawnień do ustawienia tego statusu. Możesz jedynie zmienić status na "W trakcie".')
            
            # Zawsze zwracaj dane bez dalszego przetwarzania (np. wyłaniania zwycięzcy).
            return cleaned_data

        # Jeśli użytkownik ręcznie wybrał status "Walkower" lub "Odwołany",
        # nie ingerujemy w automatyczne obliczenia.
        # Dodatkowo sprawdzamy, czy status nie jest pusty, aby uniknąć błędów.
        if status and status in (TournamentsMatch.Status.WITHDRAWN.value, TournamentsMatch.Status.CANCELLED.value):
            if 'winner' in cleaned_data and not cleaned_data.get('winner'):
                if status == TournamentsMatch.Status.WITHDRAWN.value:
                    self.add_error('winner', 'Dla statusu "Walkower" musisz ręcznie wskazać zwycięzcę.')
            cleaned_data['winner'] = cleaned_data.get('winner') # Zachowaj ręcznie ustawionego zwycięzcę
            return cleaned_data

        # Pobierz konfigurację turnieju, aby poznać liczbę setów do wygranej
        if not self.tournament or not self.tournament.config:
            return cleaned_data # Nie można kontynuować bez konfiguracji
        
        sets_to_win = self.tournament.config.sets_to_win

        # Pobierz uczestników z formularza lub instancji modelu
        p1 = cleaned_data.get('participant1') or self.instance.participant1
        p2 = cleaned_data.get('participant2') or self.instance.participant2

        # --- ZMIANA: Obsługa wolnego losu (bye) ---
        # Jeśli jeden z uczestników nie istnieje, drugi automatycznie wygrywa.
        if not p1 or not p2:
            if self.has_full_permissions: # Zmiany dokonuje tylko organizator
                cleaned_data['winner'] = p1 if p1 else p2
                cleaned_data['status'] = TournamentsMatch.Status.COMPLETED.value
            return cleaned_data # Zakończ przetwarzanie, bo nie ma dwóch graczy

        p1_sets_won = 0
        p2_sets_won = 0
        any_score_entered = False
        
        # Zlicz wygrane sety
        for i in range(1, 4): # Dla setów 1, 2, 3
            p1_score = cleaned_data.get(f'set{i}_p1_score')
            p2_score = cleaned_data.get(f'set{i}_p2_score')

            # Zliczaj tylko jeśli oba wyniki w secie są podane
            if p1_score is not None and p2_score is not None:
                any_score_entered = True
                if p1_score > p2_score:
                    p1_sets_won += 1
                elif p2_score > p1_score:
                    p2_sets_won += 1

        # Sprawdź, czy któryś z graczy osiągnął wymaganą liczbę setów
        potential_winner = None
        if p1_sets_won >= sets_to_win:
            potential_winner = p1
        elif p2_sets_won >= sets_to_win:
            potential_winner = p2

        # --- ZMIANA: Walidacja ręcznego ustawienia statusu na "Zakończony" ---
        # Jeśli użytkownik ręcznie ustawił status na "Zakończony", ale wynik nie wyłania zwycięzcy, zgłoś błąd.
        if status == TournamentsMatch.Status.COMPLETED.value and not potential_winner:
            self.add_error('status', 'Nie można ustawić statusu na "Zakończony", ponieważ wprowadzony wynik nie wyłania zwycięzcy (żaden gracz nie wygrał wymaganej liczby setów).')
            return cleaned_data

        # Ustaw zwycięzcę i status tylko, jeśli użytkownik ma uprawnienia
        if potential_winner and self.has_full_permissions:
            # Jeśli jest zwycięzca, a status nie jest ręcznie ustawiony na "W trakcie",
            # to zakończ mecz. Pozwala to uczestnikom na aktualizację wyniku w 3. secie bez kończenia meczu.
            if status != TournamentsMatch.Status.IN_PROGRESS.value:
                cleaned_data['status'] = TournamentsMatch.Status.COMPLETED.value
        elif any_score_entered:
            # Jeśli wpisano wyniki, ale nie ma zwycięzcy, ustaw status na "W trakcie"
            if status not in [TournamentsMatch.Status.COMPLETED.value, TournamentsMatch.Status.WITHDRAWN.value]:
                cleaned_data['status'] = TournamentsMatch.Status.IN_PROGRESS.value
        elif cleaned_data.get('scheduled_time') and not any_score_entered:
            # Jeśli jest tylko data, ustaw status na "Zaplanowany"
            cleaned_data['status'] = TournamentsMatch.Status.SCHEDULED.value
        elif not cleaned_data.get('scheduled_time') and not any_score_entered:
            # Jeśli nie ma ani wyników, ani daty, status wraca na "Oczekuje"
            cleaned_data['status'] = TournamentsMatch.Status.WAITING.value

        if cleaned_data.get('status') == TournamentsMatch.Status.COMPLETED.value:
            cleaned_data['winner'] = potential_winner
        else:
            cleaned_data['winner'] = None

        # --- ZMIANA: Walidacja wyników setów zgodnie z zasadami tenisa ---
        for i in range(1, 4):
            p1_score = cleaned_data.get(f'set{i}_p1_score')
            p2_score = cleaned_data.get(f'set{i}_p2_score')

            # Sprawdzaj tylko, jeśli oba wyniki w secie są podane
            if p1_score is not None and p2_score is not None:
                # --- POPRAWKA: Inna walidacja dla super tie-breaka w 3. secie ---
                is_super_tiebreak = (i == 3 and (p1_score >= 10 or p2_score >= 10))

                if is_super_tiebreak:
                    # Walidacja dla super tie-breaka (do 10, przewaga 2)
                    if abs(p1_score - p2_score) < 2:
                        self.add_error(f'set{i}_p1_score', f'Nieprawidłowy wynik w super tie-breaku (set {i}). Wymagana jest przewaga co najmniej 2 punktów.')
                        self.add_error(f'set{i}_p2_score', '')
                    elif p1_score < 10 and p2_score < 10:
                        # Ten warunek technicznie nie powinien wystąpić z powodu `is_super_tiebreak`
                        self.add_error(f'set{i}_p1_score', f'W super tie-breaku (set {i}) jeden z graczy musi zdobyć co najmniej 10 punktów.')
                        self.add_error(f'set{i}_p2_score', '')
                else:
                    # Standardowa walidacja dla setów 1 i 2 (lub seta 3 bez super tie-breaka)
                    if p1_score == p2_score and p1_score >= 6:
                        self.add_error(f'set{i}_p1_score', f'Nieprawidłowy wynik w secie {i}. Wynik 6-6 oznacza tie-break, który musi być rozstrzygnięty.')
                        self.add_error(f'set{i}_p2_score', '')
                    
                    if (p1_score == 7 and p2_score not in [5, 6]) or \
                       (p2_score == 7 and p1_score not in [5, 6]):
                        self.add_error(f'set{i}_p1_score', f'Nieprawidłowy wynik w secie {i}. Wynik 7 gemów jest możliwy tylko przy stanie 7-5 lub 7-6.')
                        self.add_error(f'set{i}_p2_score', '')

        return cleaned_data


class ParticipantMatchForm(TournamentsMatchForm):
    """
    Uproszczony formularz do edycji meczu przez uczestnika, dziedziczący z TournamentsMatchForm.
    """
    class Meta:
        model = TournamentsMatch
        fields = [
            'scheduled_time', 'status',
            'winner', 'set1_p1_score', 'set1_p2_score',
            'set2_p1_score', 'set2_p2_score',
            'set3_p1_score', 'set3_p2_score'
        ]

        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'scheduled_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'},
                                                  format='%Y-%m-%dT%H:%M'),
            'winner': forms.HiddenInput(),

            # Pola wyników setów (używamy małych pól wejściowych)
            'set1_p1_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set1_p2_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set2_p1_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set2_p2_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set3_p1_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
            'set3_p2_score': forms.NumberInput(attrs={'class': 'form-control-score', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        # --- ZMIANA: Przechwyć niestandardowy argument, aby uniknąć błędu ---
        read_only_fields = kwargs.pop('read_only_fields', [])

        # Wywołanie __init__ z klasy nadrzędnej (TournamentsMatchForm)
        super().__init__(*args, **kwargs)

        for field_name in read_only_fields:
            if field_name in self.fields:
                self.fields[field_name].disabled = True