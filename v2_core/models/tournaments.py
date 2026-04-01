"""Tournament models (Round Robin and Single Elimination)."""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Tournament(models.Model):
    """Turniej tenisowy."""
    STATUS_CHOICES = [
        ('draft', 'Szkic'),
        ('registration_open', 'Rejestracja otwarta'),
        ('registration_closed', 'Rejestracja zamknięta'),
        ('participants_confirmed', 'Skład zatwierdzony'),
        ('bracket_ready', 'Drabinka gotowa'),
        ('in_progress', 'W trakcie'),
        ('finished', 'Zakończony'),
        ('cancelled', 'Odwołany'),
    ]

    TYPE_CHOICES = [
        ('round_robin', 'Liga (każdy z każdym)'),
        ('single_elimination', 'Puchar (pojedyncza eliminacja)'),
    ]

    FORMAT_CHOICES = [
        ('singles', 'Singiel'),
        ('doubles', 'debel'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Publiczny'),
        ('private', 'Prywatny'),
        ('invite_only', 'Tylko zaproszenia'),
    ]

    REGISTRATION_MODE_CHOICES = [
        ('auto', 'Automatyczne zatwierdzenie'),
        ('approval_required', 'Wymaga zatwierdzenia'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    tournament_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='round_robin'
    )
    match_format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default='singles'
    )

    # Visibility and registration
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default='public',
        help_text='Widoczność turnieju'
    )
    registration_mode = models.CharField(
        max_length=20,
        choices=REGISTRATION_MODE_CHOICES,
        default='auto',
        help_text='Tryb akceptacji uczestników'
    )

    # Dates
    registration_open_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data i godzina otwarcia zapisów'
    )
    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Termin zamknięcia rejestracji'
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data i godzina faktycznego zakończenia'
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data i godzina odwołania'
    )

    # Status
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # Metadata
    facility = models.ForeignKey(
        'Facility',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournaments'
    )
    rank = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text='Ranga turnieju (1-3, wyższy = więcej punktów)'
    )
    min_participants = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(2)],
        help_text='Minimalna liczba uczestników'
    )
    max_participants = models.PositiveIntegerField(default=16)

    # Winner
    winner = models.ForeignKey(
        'Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_tournaments'
    )

    # User tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_tournaments'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_tournaments',
        help_text='Ostatnia osoba modyfikująca turniej'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tournaments'
        verbose_name = 'Turniej'
        verbose_name_plural = 'Turnieje'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-start_date']),
        ]

    def clean(self):
        """Walidacja zgodna ze specyfikacją turniejów."""
        if self.end_date <= self.start_date:
            raise ValidationError('Data zakończenia musi być późniejsza niż data rozpoczęcia.')

        if self.max_participants < self.min_participants:
            raise ValidationError('Maksymalna liczba uczestników musi być >= minimalnej liczby.')

        if self.min_participants < 2:
            raise ValidationError('Minimalna liczba uczestników musi wynosić co najmniej 2.')

        if self.registration_deadline and self.registration_deadline > self.start_date:
            raise ValidationError('Termin zamknięcia rejestracji musi być przed datą rozpoczęcia turnieju.')

    def __str__(self):
        return self.name


class TournamentConfig(models.Model):
    """Konfiguracja turnieju (scoring rules)."""
    tournament = models.OneToOneField(
        Tournament,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='config'
    )

    # Match settings
    sets_to_win = models.IntegerField(
        default=2,
        help_text='Liczba wygranych setów potrzebna do wygranej'
    )
    games_per_set = models.IntegerField(
        default=6,
        help_text='Liczba gemów do wygrania seta'
    )

    # Round Robin specific (używane tylko dla league)
    points_for_match_win = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("3.00"),
        help_text='Punkty za wygrany mecz (liga)'
    )
    points_for_match_loss = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text='Punkty za przegrany mecz (liga)'
    )
    points_for_set_win = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text='Punkty za wygrany set (liga)'
    )

    # Single Elimination specific
    use_seeding = models.BooleanField(
        default=True,
        help_text='Czy używa seedingu (ranking) w pierwszej rundzie'
    )
    third_place_match = models.BooleanField(
        default=True,
        help_text='Czy rozgrywa mecz o 3. miejsce'
    )

    class Meta:
        db_table = 'tournament_configs'
        verbose_name = 'Konfiguracja turnieju'


class Participant(models.Model):
    """Uczestnik turnieju."""
    STATUS_CHOICES = [
        ('pending', 'Oczekuje'),
        ('confirmed', 'Potwierdzony'),
        ('waitlist', 'Lista rezerwowa'),
        ('withdrawn', 'Wycofany'),
        ('rejected', 'Odrzucony'),
        ('eliminated', 'Wyeliminowany'),
        ('winner', 'Zwycięzca'),
    ]

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tournament_participations'
    )

    # Team info (for doubles)
    partner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tournament_partnerships',
        help_text='Partner w debelu'
    )
    display_name = models.CharField(
        max_length=100,
        help_text='Nazwa wyświetlana (auto z username lub custom)'
    )

    # Tournament info
    seed = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text='Numer rozstawienia'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Registration and lifecycle tracking
    joined_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data i godzina zgłoszenia'
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data i godzina zatwierdzenia przez managera'
    )
    withdrawn_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data i godzina wycofania się'
    )
    withdrawal_reason = models.TextField(
        blank=True,
        help_text='Powód wycofania się'
    )

    # Final results
    final_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Finalna pozycja w turnieju (1=zwycięzca)'
    )

    # Stats (for Round Robin)
    points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Punkty w tabeli (liga)'
    )
    matches_won = models.IntegerField(default=0)
    matches_lost = models.IntegerField(default=0)
    sets_won = models.IntegerField(default=0)
    sets_lost = models.IntegerField(default=0)
    games_won = models.IntegerField(default=0)
    games_lost = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tournament_participants'
        verbose_name = 'Uczestnik turnieju'
        verbose_name_plural = 'Uczestnicy turnieju'
        unique_together = [['tournament', 'user']]
        ordering = ['-points', '-matches_won']
        indexes = [
            models.Index(fields=['tournament', '-points']),
        ]

    def __str__(self):
        return self.display_name


class TournamentMatch(models.Model):
    """Mecz w turnieju."""
    STATUS_CHOICES = [
        ('scheduled', 'Zaplanowany'),
        ('ready', 'Gotowy'),
        ('in_progress', 'W trakcie'),
        ('completed', 'Zakończony'),
        ('walkover', 'Walkower'),
        ('cancelled', 'Odwołany'),
    ]

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='tournament_matches'
    )

    # Participants (nullable for bracket generation before all matches known)
    player1_participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_player1'
    )
    player2_participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_player2'
    )

    # Results
    winner_participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_tournament_matches'
    )
    loser_participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lost_tournament_matches'
    )

    # Bracket structure (for single elimination)
    round_number = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Numer rundy (1=pierwsza runda, wyższe=dalsze rundy)'
    )
    match_number = models.PositiveIntegerField(
        default=1,
        help_text='Numer meczu w rundzie (dla identyfikacji)'
    )
    bracket_position = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Pozycja w drabince (unikalna w obrębie turnieju)'
    )

    # Source matches (for bracket tree navigation)
    source_match_1 = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feeds_into_as_source1',
        help_text='Mecz źródłowy dla player1 (zwycięzca source_match_1 -> player1)'
    )
    source_match_2 = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feeds_into_as_source2',
        help_text='Mecz źródłowy dla player2 (zwycięzca source_match_2 -> player2)'
    )

    # Status and scheduling
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )
    scheduled_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Planowany czas rozpoczęcia'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Faktyczny czas zakończenia'
    )

    # Walkover handling
    walkover_reason = models.TextField(
        blank=True,
        help_text='Powód walkower (wycofanie, kontuzja, etc.)'
    )

    # Scores
    set1_p1 = models.IntegerField(null=True, blank=True)
    set1_p2 = models.IntegerField(null=True, blank=True)
    set2_p1 = models.IntegerField(null=True, blank=True)
    set2_p2 = models.IntegerField(null=True, blank=True)
    set3_p1 = models.IntegerField(null=True, blank=True)
    set3_p2 = models.IntegerField(null=True, blank=True)

    # Court assignment
    court = models.ForeignKey(
        'Court',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournament_matches'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tournament_matches'
        verbose_name = 'Mecz turniejowy'
        verbose_name_plural = 'Mecze turniejowe'
        ordering = ['round_number', 'match_number']
        unique_together = [['tournament', 'round_number', 'match_number']]
        indexes = [
            models.Index(fields=['tournament', 'status']),
            models.Index(fields=['scheduled_time']),
        ]

    def __str__(self):
        p1 = self.player1_participant.display_name if self.player1_participant else 'TBD'
        p2 = self.player2_participant.display_name if self.player2_participant else 'TBD'
        return f"[{self.tournament.name}] R{self.round_number}-M{self.match_number}: {p1} vs {p2}"


class TournamentManager(models.Model):
    """Manager turnieju - osoba z prawami do zarządzania turniejem."""
    ROLE_CHOICES = [
        ('owner', 'Właściciel'),
        ('manager', 'Manager'),
    ]

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='managers'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='managed_tournaments'
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='manager',
        help_text='Rola w zarządzaniu turniejem'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tournament_managers'
        verbose_name = 'Manager turnieju'
        verbose_name_plural = 'Managerowie turnieju'
        unique_together = [['tournament', 'user']]
        indexes = [
            models.Index(fields=['tournament', 'user']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.tournament.name} ({self.get_role_display()})"


class TournamentEventLog(models.Model):
    """Log zdarzeń turniejowych dla audytu i debugowania."""
    EVENT_TYPE_CHOICES = [
        ('created', 'Utworzenie turnieju'),
        ('registration_opened', 'Otwarcie zapisów'),
        ('registration_closed', 'Zamknięcie zapisów'),
        ('participant_joined', 'Zapis uczestnika'),
        ('participant_approved', 'Zatwierdzenie uczestnika'),
        ('participant_rejected', 'Odrzucenie uczestnika'),
        ('participant_withdrawn', 'Wycofanie uczestnika'),
        ('participants_confirmed', 'Zatwierdzenie składu'),
        ('bracket_generated', 'Wygenerowanie drabinki'),
        ('tournament_started', 'Start turnieju'),
        ('match_scheduled', 'Zaplanowanie meczu'),
        ('match_result', 'Wynik meczu'),
        ('match_walkover', 'Walkover'),
        ('tournament_finished', 'Zakończenie turnieju'),
        ('tournament_cancelled', 'Odwołanie turnieju'),
        ('ranking_points_awarded', 'Naliczenie punktów rankingowych'),
    ]

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='event_logs'
    )
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournament_actions',
        help_text='Użytkownik wykonujący akcję (może być NULL dla akcji systemowych)'
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text='Dodatkowe dane o zdarzeniu (JSON)'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tournament_event_logs'
        verbose_name = 'Log zdarzeń turniejowych'
        verbose_name_plural = 'Logi zdarzeń turniejowych'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tournament', '-created_at']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        actor_name = self.actor.username if self.actor else 'SYSTEM'
        return f"[{self.tournament.name}] {self.get_event_type_display()} - {actor_name}"
