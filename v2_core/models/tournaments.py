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
        ('registration', 'Rejestracja otwarta'),
        ('scheduled', 'Zaplanowany'),
        ('active', 'W trakcie'),
        ('finished', 'ZakoDczony'),
        ('cancelled', 'OdwoBany'),
    ]

    TYPE_CHOICES = [
        ('round_robin', 'Liga (ka|dy z ka|dym)'),
        ('single_elimination', 'Puchar (pojedyncza eliminacja)'),
    ]

    FORMAT_CHOICES = [
        ('singles', 'Singiel'),
        ('doubles', 'DebeB'),
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

    # Dates
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Termin zamknicia rejestracji'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # Metadata
    facility = models.ForeignKey(
        'facilities.Facility',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournaments'
    )
    rank = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text='Ranga turnieju (1-3, wy|szy = wicej punktów)'
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

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_tournaments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

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
        if self.end_date <= self.start_date:
            raise ValidationError('Data zakoDczenia musi by pózniejsza ni| data rozpoczcia.')

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

    # Round Robin specific (u|ywane tylko dla league)
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
        help_text='Czy u|ywa seedingu (ranking) w pierwszej rundzie'
    )
    third_place_match = models.BooleanField(
        default=True,
        help_text='Czy rozgrywa mecz o 3. miejsce'
    )

    class Meta:
        db_table = 'tournament_configs'
        verbose_name = 'Konfiguracja turnieju'


class Participant(models.Model):
    """Uczestnik turnieju."""
    STATUS_CHOICES = [
        ('registered', 'Zarejestrowany'),
        ('active', 'Aktywny'),
        ('eliminated', 'Wyeliminowany'),
        ('withdrawn', 'Wycofany'),
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
        help_text='Partner w deblu'
    )
    display_name = models.CharField(
        max_length=100,
        help_text='Nazwa wy[wietlana (auto z username lub custom)'
    )

    # Tournament info
    seed = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Numer rozstawienia'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='registered'
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
        ('waiting', 'Oczekuje'),
        ('scheduled', 'Zaplanowany'),
        ('in_progress', 'W trakcie'),
        ('completed', 'ZakoDczony'),
        ('walkover', 'Walkower'),
    ]

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name='tournament_matches'
    )

    # Participants
    participant1 = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_p1'
    )
    participant2 = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_p2'
    )

    # Round info (for elimination)
    round_number = models.PositiveIntegerField(
        default=1,
        help_text='Numer rundy (1=pierwsza, 2=wierfinaB, etc.)'
    )
    match_number = models.PositiveIntegerField(
        default=1,
        help_text='Numer meczu w rundzie'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='waiting'
    )
    scheduled_time = models.DateTimeField(null=True, blank=True)

    # Scores
    set1_p1 = models.IntegerField(null=True, blank=True)
    set1_p2 = models.IntegerField(null=True, blank=True)
    set2_p1 = models.IntegerField(null=True, blank=True)
    set2_p2 = models.IntegerField(null=True, blank=True)
    set3_p1 = models.IntegerField(null=True, blank=True)
    set3_p2 = models.IntegerField(null=True, blank=True)

    # Winner
    winner = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_matches'
    )

    # Court assignment
    court = models.ForeignKey(
        'facilities.Court',
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
        p1 = self.participant1.display_name if self.participant1 else 'TBD'
        p2 = self.participant2.display_name if self.participant2 else 'TBD'
        return f"[{self.tournament.name}] R{self.round_number}-M{self.match_number}: {p1} vs {p2}"
