"""Tennis matches (singles and doubles)."""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q, F


class Match(models.Model):
    """Mecz tenisowy (singiel lub debeł)."""

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Zaplanowany'
        IN_PROGRESS = 'in_progress', 'W trakcie'
        COMPLETED = 'completed', 'Zakończony'
        CANCELLED = 'cancelled', 'Anulowany'

    class WinnerSide(models.TextChoices):
        P1 = 'p1', 'Player/Team 1'
        P2 = 'p2', 'Player/Team 2'

    # Players
    player1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='matches_as_p1'
    )
    player2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='matches_as_p2'
    )
    player3 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='matches_as_p3',
        help_text='Partner player1 (debeł)'
    )
    player4 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='matches_as_p4',
        help_text='Partner player2 (debeł)'
    )

    # Match type and status
    is_doubles = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED
    )

    # Scores (best of 3 sets)
    set1_p1 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set1_p2 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set2_p1 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set2_p2 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set3_p1 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set3_p2 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])

    # Winner (computed from sets or manually set)
    winner_side = models.CharField(
        max_length=2,
        choices=WinnerSide.choices,
        null=True,
        blank=True
    )

    # Metadata
    match_date = models.DateField()
    description = models.CharField(max_length=200, default='Mecz towarzyski')
    court = models.ForeignKey(
        'facilities.Court',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def compute_winner(self):
        """Oblicza zwycięzcę na podstawie wyników setów."""
        p1_sets = 0
        p2_sets = 0

        for p1, p2 in [
            (self.set1_p1, self.set1_p2),
            (self.set2_p1, self.set2_p2),
            (self.set3_p1, self.set3_p2),
        ]:
            if p1 is None or p2 is None:
                continue
            if p1 > p2:
                p1_sets += 1
            elif p2 > p1:
                p2_sets += 1

        # Best of 3: potrzeba 2 wygranych setów
        if p1_sets >= 2:
            return self.WinnerSide.P1
        if p2_sets >= 2:
            return self.WinnerSide.P2
        return None

    def clean(self):
        """Walidacja meczu."""
        # Blokuj self-play
        if self.player1_id == self.player2_id:
            raise ValidationError("Player 1 i Player 2 nie mogą być tą samą osobą.")

        # Walidacja debeł vs singiel
        if self.is_doubles:
            if not self.player3_id or not self.player4_id:
                raise ValidationError("Mecz deblowy wymaga player3 i player4.")
        else:
            if self.player3_id or self.player4_id:
                raise ValidationError("Mecz singlowy nie może mieć player3/player4.")

        # Sprawdź zgodność winner_side z wynikiem
        computed = self.compute_winner()

        if self.status == self.Status.COMPLETED and not computed:
            raise ValidationError("Zakończony mecz musi mieć wyliczalnego zwycięzcę (2 wygrane sety).")

        if self.winner_side and computed and self.winner_side != computed:
            raise ValidationError(f"winner_side ({self.winner_side}) nie zgadza się z wynikiem setów ({computed}).")

    def save(self, *args, **kwargs):
        """Automatycznie ustaw winner_side przy zapisie."""
        computed = self.compute_winner()

        # Auto-update winner dla completed matches
        if self.status == self.Status.COMPLETED:
            self.winner_side = computed
        elif self.status in {self.Status.SCHEDULED, self.Status.CANCELLED}:
            # Reset winner dla scheduled/cancelled
            self.winner_side = None

        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'matches'
        verbose_name = 'Mecz'
        verbose_name_plural = 'Mecze'
        ordering = ['-match_date']
        constraints = [
            # Blokuj self-play
            models.CheckConstraint(
                condition=~Q(player1=F('player2')),
                name='matches_player1_ne_player2'
            ),
        ]
        indexes = [
            models.Index(fields=['-match_date']),
            models.Index(fields=['is_doubles']),
            models.Index(fields=['status', 'match_date']),
        ]

    def __str__(self):
        if self.is_doubles:
            p3_name = self.player3.username if self.player3 else '?'
            p4_name = self.player4.username if self.player4 else '?'
            return f"{self.player1.username}/{p3_name} vs {self.player2.username}/{p4_name} ({self.match_date})"
        return f"{self.player1.username} vs {self.player2.username} ({self.match_date})"

    def get_all_players(self):
        """Zwraca listę wszystkich graczy w meczu."""
        players = [self.player1, self.player2]
        if self.is_doubles:
            if self.player3:
                players.append(self.player3)
            if self.player4:
                players.append(self.player4)
        return players
