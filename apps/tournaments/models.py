from decimal import Decimal
import math
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from apps.courts.models import TennisFacility
from django.conf import settings


class Tournament(models.Model): 
    class Status(models.TextChoices):
        DRAFT = 'DRF', 'Nieaktywny/Szkic'
        REGISTRATION = 'REG', 'Oczekuje na graczy (Rejestracja otwarta)'
        SCHEDULED = 'SCH', 'Zaplanowany (Rejestracja zamknięta)'
        ACTIVE = 'ACT', 'Rozpoczęty'
        FINISHED = 'FIN', 'Zakończony'
        CANCELLED = 'CNC', 'Odwołany'
 
    class TournamentType(models.TextChoices):
        """
        SGL	System pucharowy (Pojedyncza eliminacja)
        Po każdej przegranej uczestnik odpada z turnieju.
        Format ten szybko wyłania zwycięzcę, ale nie daje szansy na rehabilitację po słabszym dniu.
        RND	System "każdy z każdym" (Round Robin)
        Każdy uczestnik (lub drużyna) spotyka się z każdym innym uczestnikiem dokładnie jeden raz (lub dwukrotnie w przypadku dwóch rund).
        Jest to format powszechnie stosowany w ligach sportowych.

        LDR	Drabinka (Ladder)
        Uczestnicy są usunięci w hierarchicznej kolejności (jak na drabinie). Wyzwaniem jest pokonanie osób wyżej w rankingu, aby zająć ich miejsce.
        Często używany w nieformalnych rozgrywkach, gdzie gracze mogą się wyzywać do pojedynków.
        """
        SINGLE_ELIMINATION = 'SGL', 'Puchar - pojedyncza eliminacja'
        DOUBLE_ELIMINATION = 'DBE', 'Puchar - podwójna eliminacja'
        ROUND_ROBIN = 'RND', 'Liga (każdy z każdym)'
        LADDER = 'LDR', 'Lider - drabinka'
        AMERICANO = 'AMR', 'Americano / Mexicano'
        SWISS = 'SWS', 'System Szwajcarski'

    class MatchFormat(models.TextChoices):
        SINGLES = 'SNG', 'Singiel (1 vs 1)'
        DOUBLES = 'DBL', 'Debel (2 vs 2)'

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text='Oficjalna data i godzina rozpoczęcia turnieju.'
    )
    end_date = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text='Oficjalna data i godzina zakończenia turnieju.'
    )

    status = models.CharField(
        max_length=3,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text='Aktualny stan i faza turnieju.'
    )

    tournament_type = models.CharField(
        max_length=3,
        choices=TournamentType.choices,
        default=TournamentType.ROUND_ROBIN,
        help_text='Format w jakim odbywają się rozgrywki.',
    )

    match_format = models.CharField(
        max_length=3,
        choices=MatchFormat.choices,
        default=MatchFormat.SINGLES,
        help_text='Liczba graczy biorących udział w pojedynczym spotkaniu.',
    )
    facility = models.ForeignKey(
        TennisFacility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournaments',
        verbose_name='Obiekt tenisowy'
    )
    rank = models.PositiveIntegerField(
        choices=[
            (1, '1'),
            (2, '2'),
            (3, '3'),
        ],
        default=1,
        verbose_name='Ranga turnieju',
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='created_tournaments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    winner = models.ForeignKey(
        'Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_tournaments'
    )

    class Meta:
        app_label = 'tournaments'
        db_table = 'tournaments' 
        ordering = ['-created_at'] 
        verbose_name = 'Turniej'
        verbose_name_plural = 'Turnieje' 

    def __str__(self):
        return self.name

    def clean(self):
        """
        Dodaje walidację na poziomie modelu, aby upewnić się, że data zakończenia
        nie jest wcześniejsza niż data rozpoczęcia.
        """
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError('Data zakończenia nie może być wcześniejsza niż data rozpoczęcia.')

    @property
    def config(self):
        """Zwraca odpowiedni obiekt konfiguracji dla danego typu turnieju."""
        if self.tournament_type == self.TournamentType.ROUND_ROBIN:
            return getattr(self, 'round_robin_config', None)
        elif self.tournament_type in (self.TournamentType.SINGLE_ELIMINATION, self.TournamentType.DOUBLE_ELIMINATION):
            return getattr(self, 'elimination_config', None)
        elif self.tournament_type == self.TournamentType.LADDER:
            return getattr(self, 'ladder_config', None)
        elif self.tournament_type == self.TournamentType.AMERICANO:
            return getattr(self, 'americano_config', None)
        elif self.tournament_type == self.TournamentType.SWISS:
            return getattr(self, 'swiss_system_config', None)
        return None

    @property
    def is_open_for_registration(self):
        """Sprawdza, czy turniej jest otwarty na rejestrację."""
        return self.status == self.Status.REGISTRATION

    @property
    def is_deletable(self):
        """Sprawdza, czy turniej można usunąć (tylko w statusie Draft lub Registration)."""
        return self.status in (self.Status.DRAFT, self.Status.REGISTRATION)

    @property
    def is_draft(self):
        """Sprawdza, czy turniej jest w statusie szkicu."""
        return self.status == self.Status.DRAFT


class TournamentConfigBase(models.Model):
    # Relacja OneToOne do modelu Tournament
    tournament = models.OneToOneField(
        'Tournament', 
        on_delete=models.CASCADE, 
        primary_key=True,
        related_name='+'
    )
    
    # Wspólne pola dla konfiguracji
    max_participants = models.IntegerField(
        default=16, 
        help_text='Maksymalna liczba graczy/zespołów.'
    )
        
    # Konfiguracja Setów
    sets_to_win = models.IntegerField(
        default=2,
        help_text='Liczba setów, które należy wygrać, aby wygrać mecz (np. 1 z 2 lub 2 z 3).'
    )
    games_per_set = models.IntegerField(
        default=6,
        help_text='Liczba gemów wymaganych do wygrania seta (standardowo do 6 gemów z przewagą 2).'
    )

    class Meta:
        abstract = True
        verbose_name = 'Podstawowa Konfiguracja Turnieju'


class RoundRobinConfig(TournamentConfigBase):
    tournament = models.OneToOneField(
    'Tournament',
    on_delete=models.CASCADE,
    primary_key=True,
    related_name='round_robin_config' # Unikalna nazwa
    )
    # Punkty za wynik w tabeli Round Robin
    points_for_win = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.00"),
        help_text='Liczba punktów za wygrany mecz.'
    )
    points_for_loss = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text='Liczba punktów za przegrany mecz.'
    )   
    points_for_set_win = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.50"),
        help_text='Liczba punktów za wygrany set.'
    )
    points_for_set_loss = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text='Liczba punktów za przegrany set.'
    ) 
    points_for_gem_win = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal("0.1"),
        help_text='Liczba punktów za wygrany gem.'
    )
    points_for_gem_loss = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=Decimal("-0.1"),
        help_text='Liczba punktów za przegrany gem.'
    )
    points_for_supertiebreak_win = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=Decimal("0.05"),
        help_text='Liczba punktów za wygrany super tie-break.'
    )
    points_for_supertiebreak_loss = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=Decimal("-0.05"),
        help_text='Liczba punktów za przegrany super tie-break.'
    )

    # Dodatkowe kryterium tie-breakera
    TIE_BREAKERS = [
        ('HEAD', 'Bezpośrednie spotkanie'),
        ('SETS', 'Bilans setów'),
        ('GAMES', 'Bilans gemów'),
    ]
    tie_breaker_priority = models.CharField(
        max_length=5,
        choices=TIE_BREAKERS,
        default='GAMES',
        help_text='Główne kryterium decydujące o kolejności w przypadku równej liczby punktów.'
    )

    class Meta:
        verbose_name = 'Konfiguracja Round Robin'
        verbose_name_plural = 'Konfiguracje Round Robin'


class EliminationConfig(TournamentConfigBase):
    tournament = models.OneToOneField(
    'Tournament',
    on_delete=models.CASCADE,
    primary_key=True,
    related_name='elimination_config' # Unikalna nazwa
    )
    INITIAL_SEEDING_CHOICES = [
        ('RANDOM', 'Losowe'),
        ('SEEDING', 'Według rankingu (seed) - Najsilniejszy z najsłabszym'),
    ]

    # Pole specyficzne dla drabinki
    initial_seeding = models.CharField(
        max_length=10,
        choices=INITIAL_SEEDING_CHOICES,
        default='SEEDING',
        help_text='Sposób parowania w pierwszej rundzie.'
    )
    
    # Czy jest mecz o 3. miejsce (zazwyczaj tylko w Single Elimination)
    third_place_match = models.BooleanField(
        default=True,
        help_text='Czy ma być rozgrywany mecz o trzecie miejsce.'
    )

    class Meta:
        verbose_name = 'Konfiguracja Eliminacji'
        verbose_name_plural = 'Konfiguracje Eliminacji'


class LadderConfig(TournamentConfigBase):
    tournament = models.OneToOneField(
        'Tournament',
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='ladder_config' # Unikalna nazwa
    )
    challenge_range = models.PositiveIntegerField(
        default=3,
        help_text='Maksymalna liczba pozycji w górę, o które gracz może rzucić wyzwanie.'
    )
    initial_seeding = models.CharField(
        max_length=10,
        choices=[('RANDOM', 'Losowe'), ('SEEDING', 'Według numeru rozstawienia (seed)')],
        default='SEEDING',
        help_text='Sposób początkowego ustawienia graczy na drabince po zamknięciu rejestracji.'
    )

    class Meta:
        verbose_name = 'Konfiguracja Drabinki'
        verbose_name_plural = 'Konfiguracje Drabinki'


class AmericanoConfig(models.Model):
    """Konfiguracja dla turniejów typu Americano / Mexicano."""
    SCHEDULING_CHOICES = [
        ('STATIC', 'Americano (stały harmonogram)'),
        ('DYNAMIC', 'Mexicano (dynamiczne kojarzenie co rundę)'),
    ]

    tournament = models.OneToOneField(
        'Tournament',
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='americano_config'
    )
    max_participants = models.IntegerField(
        default=16,
        help_text='Maksymalna liczba graczy. Powinna być wielokrotnością 4.'
    )
    points_per_match = models.PositiveIntegerField(
        default=32,
        help_text='Suma punktów do zdobycia w każdym meczu (np. 32, 48).'
    )
    number_of_rounds = models.PositiveIntegerField(
        default=7,
        help_text='Liczba rund do rozegrania w turnieju.'
    )
    scheduling_type = models.CharField(
        max_length=10,
        choices=SCHEDULING_CHOICES,
        default='STATIC',
        help_text='Sposób kojarzenia graczy w pary i mecze.'
    )

    class Meta:
        verbose_name = 'Konfiguracja Americano'
        verbose_name_plural = 'Konfiguracje Americano'


class SwissSystemConfig(TournamentConfigBase):
    """Konfiguracja dla turniejów w Systemie Szwajcarskim."""
    
    INITIAL_SEEDING_CHOICES = [
        ('RANDOM', 'Losowe'),
        ('SEEDING', 'Według rankingu (seed) - Najsilniejszy z najsłabszym'),
    ]

    tournament = models.OneToOneField(
        'Tournament',
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='swiss_system_config'
    )
    @property
    def wins_to_qualify(self):
        """
        Liczba wygranych do awansu (log2(max_participants) - 1).
        """
        if not self.max_participants:
            return 3 # Domyślna wartość w przypadku braku max_participants
        return int(math.log2(self.max_participants)) - 1
        
    @property
    def losses_to_eliminate(self):
        """
        Liczba przegranych do eliminacji (log2(max_participants) - 1).
        """
        if not self.max_participants:
            return 3 # Domyślna wartość
        return int(math.log2(self.max_participants)) - 1
    @property
    def number_of_rounds(self):
        """
        Liczba rund jest obliczana dynamicznie:
        (liczba wygranych do awansu) + (liczba przegranych do eliminacji) - 1
        """
        return self.wins_to_qualify + self.losses_to_eliminate - 1
    initial_seeding = models.CharField(
        max_length=10,
        choices=INITIAL_SEEDING_CHOICES,
        default='SEEDING',
        help_text='Sposób parowania w pierwszej rundzie.'
    )

    class Meta:
        verbose_name = 'Konfiguracja Systemu Szwajcarskiego'
        verbose_name_plural = 'Konfiguracje Systemu Szwajcarskiego'


class Participant(models.Model):
    tournament = models.ForeignKey(
        'Tournament', 
        on_delete=models.CASCADE, 
        related_name='participants',
        help_text='Turniej, do którego należy to zgłoszenie.'
    )
    
    # Reprezentuje gracza lub zespół. 
    # Używamy OneToMany (ForeignKey) na wypadek, gdyby ten sam użytkownik miał więcej zgłoszeń
    # (np. w singlu i deblu w tym samym turnieju, choć to jest rzadkie)
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='tournament_participations',
        help_text='Konto użytkownika głównego. Może być puste, jeśli jest to zespół zewnętrzny.'
    )
    
    # Nazwa wyświetlana (np. ksywka gracza lub nazwa zespołu w przypadku debla)
    display_name = models.CharField(
        max_length=100,
        help_text='Nazwa wyświetlana w drabince/tabeli turnieju.'
    )
    
    # Numer rozstawienia (seeding)
    seed_number = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text='Numer rozstawienia (seeding) w turnieju, jeśli dotyczy.'
    )
    
    # Status w turnieju (np. Zgłoszony, Aktywny, Wyeliminowany)
    PARTICIPANT_STATUSES = [
        ('PEN', 'Oczekuje na zatwierdzenie'),
        ('REG', 'Zarejestrowany'),
        ('ACT', 'Aktywny w rozgrywkach'),
        ('OUT', 'Wyeliminowany'),
        ('WDN', 'Wycofany'),
        ('BYE', 'Wolny los (Bye)'),
    ]
    status = models.CharField(
        max_length=3,
        choices=PARTICIPANT_STATUSES,
        default='REG',
        help_text='Status uczestnika w tym turnieju.'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tournament_participants'
        verbose_name = 'Uczestnik Turnieju'
        verbose_name_plural = 'Uczestnicy Turnieju'
        # Zapewnienie, że w danym turnieju istnieje tylko jedno zgłoszenie z daną nazwą
        unique_together = ('tournament', 'display_name')

    def __str__(self):
        return f'{self.display_name}'
    

class TeamMember(models.Model):
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='members',
        help_text='Zgłoszenie zespołu, do którego należy ten członek.'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text='Konto użytkownika wchodzące w skład zespołu.'
    )
    
    class Meta:
        # Zapewnienie, że jeden użytkownik jest tylko raz w danym zespole/zgłoszeniu
        unique_together = ('participant', 'user')
        verbose_name = 'Członek Zespołu'
        verbose_name_plural = 'Członkowie Zespołów'


class TournamentsMatch(models.Model):
    """Reprezentuje pojedynczy mecz w turnieju."""
    
    tournament = models.ForeignKey(
        'Tournament',
        on_delete=models.CASCADE,
        related_name='matches',
        help_text='Turniej, do którego należy mecz.'
    )
    
    # Uczestnicy
    participant1 = models.ForeignKey(
        'Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_p1',
        help_text='Pierwszy uczestnik/zespół.'
    )
    participant2 = models.ForeignKey(
        'Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_p2',
        help_text='Drugi uczestnik/zespół.'
    )
    participant3 = models.ForeignKey(
        'Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_p3',
        help_text='Trzeci uczestnik/zespół (dla debla/americano).'
    )
    participant4 = models.ForeignKey(
        'Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_p4',
        help_text='Czwarty uczestnik/zespół (dla debla/americano).'
    )

    # Informacje o etapie (dla turniejów pucharowych lub faz grupowych)
    round_number = models.PositiveIntegerField(
        default=1,
        help_text='Numer rundy/etapu (np. Runda 1, Półfinał, Faza grupowa).'
    )
    match_index = models.PositiveIntegerField(
        default=1,
        help_text='Indeks meczu w danej rundzie (np. Mecz 1, Mecz 2).'
    )
    
    class Status(models.TextChoices):
        WAITING = 'WAI', 'Oczekuje'
        SCHEDULED = 'SCH', 'Zaplanowany'
        IN_PROGRESS = 'INP', 'W trakcie'
        COMPLETED = 'CMP', 'Zakończony'
        WITHDRAWN = 'WDR', 'Wycofany/Walkower'
        CANCELLED = 'CNC', 'Odwołany'

    status = models.CharField(
        max_length=3,
        choices=Status.choices,
        default=Status.WAITING,
        help_text='Status aktualnej rozgrywki.'
    )

    # Wyniki gemów w poszczególnych setach (maksymalnie 5 setów)
    # Set 1
    set1_p1_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Liczba gemów Ucz. 1 w Secie 1.')
    set1_p2_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Liczba gemów Ucz. 2 w Secie 1.')
    # Set 2
    set2_p1_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Liczba gemów Ucz. 1 w Secie 2.')
    set2_p2_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Liczba gemów Ucz. 2 w Secie 2.')
    # Set 3
    set3_p1_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Liczba gemów Ucz. 1 w Secie 3.')
    set3_p2_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Liczba gemów Ucz. 2 w Secie 3.')

    winner = models.ForeignKey(
        'Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_matches',
        help_text='Zwycięzca meczu.'
    )

    # Data/Czas
    scheduled_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Planowana data i godzina rozpoczęcia meczu.'
    )

    class Meta:
        app_label = 'tournaments'
        db_table = 'tournament_matches' 
        verbose_name = 'Mecz Turniejowy'
        verbose_name_plural = 'Mecze Turniejowe'
        ordering = ['round_number', 'match_index']
        unique_together = ('tournament', 'round_number', 'match_index') 

    def __str__(self):
        p1_name = self.participant1.display_name if self.participant1 else 'BYE'
        p2_name = self.participant2.display_name if self.participant2 else 'BYE'
        return f'[{self.tournament.name}] Runda {self.round_number}, Mecz {self.match_index}: {p1_name} vs {p2_name}'


class ChallengeRejection(models.Model):
    """
    Model do śledzenia, kto odrzucił czyje wyzwanie w turnieju drabinkowym.
    Wpisy są usuwane, gdy jeden z graczy zakończy jakikolwiek mecz,
    co symbolizuje "nową rundę" dla tego gracza.
    """
    tournament = models.ForeignKey('Tournament', on_delete=models.CASCADE, related_name='rejections')
    rejecting_participant = models.ForeignKey('Participant', on_delete=models.CASCADE, related_name='rejections_made')
    challenger_participant = models.ForeignKey('Participant', on_delete=models.CASCADE, related_name='challenges_rejected')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tournament_challenge_rejections'
        verbose_name = 'Odrzucenie Wyzwania'
        verbose_name_plural = 'Odrzucenia Wyzwań'
        # Uczestnik może odrzucić wyzwanie danego gracza tylko raz w "rundzie".
        unique_together = ('tournament', 'rejecting_participant', 'challenger_participant')


class MatchScoreHistory(models.Model):
    """
    Przechowuje historię zmian wyników w meczu, aby umożliwić śledzenie
    postępów w czasie rzeczywistym i analizę po zakończeniu meczu.
    """
    match = models.ForeignKey(
        'TournamentsMatch',
        on_delete=models.CASCADE,
        related_name='score_history',
        help_text='Mecz, którego dotyczy wpis historii.'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text='Użytkownik, który zaktualizował wynik.'
    )
    updated_at = models.DateTimeField(auto_now_add=True, help_text='Data i godzina aktualizacji wyniku.')

    # Wyniki w momencie aktualizacji
    set1_p1_score = models.PositiveSmallIntegerField(null=True, blank=True)
    set1_p2_score = models.PositiveSmallIntegerField(null=True, blank=True)
    set2_p1_score = models.PositiveSmallIntegerField(null=True, blank=True)
    set2_p2_score = models.PositiveSmallIntegerField(null=True, blank=True)
    set3_p1_score = models.PositiveSmallIntegerField(null=True, blank=True)
    set3_p2_score = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'tournament_match_score_history'
        verbose_name = 'Historia Wyniku Meczu'
        verbose_name_plural = 'Historie Wyników Meczów'
        ordering = ['-updated_at']


class MatchReaction(models.Model):
    """
    Reprezentuje reakcję (np. polubienie, emotkę) użytkownika na konkretny mecz.
    """
    # Dostępne typy reakcji (można łatwo rozszerzyć)
    REACTION_CHOICES = [
        ('👍', '👍'),
    ]

    match = models.ForeignKey(TournamentsMatch, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=8, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Każdy użytkownik może mieć tylko jedną reakcję danego typu na dany mecz
        unique_together = ('match', 'user', 'emoji')
        ordering = ['created_at']
