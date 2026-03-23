"""Tennis matches (singles and doubles)."""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class Match(models.Model):
    """Mecz tenisowy (singiel lub debeB)."""
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
        help_text='Partner player1 (debeB)'
    )
    player4 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='matches_as_p4',
        help_text='Partner player2 (debeB)'
    )

    # Match type
    is_doubles = models.BooleanField(default=False)

    # Scores (best of 3 sets)
    set1_p1 = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    set1_p2 = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    set2_p1 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set2_p2 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set3_p1 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    set3_p2 = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])

    # Winner (computed after match completion)
    winner_side = models.CharField(
        max_length=2,
        choices=[('p1', 'Player 1/3'), ('p2', 'Player 2/4')],
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

    class Meta:
        db_table = 'matches'
        verbose_name = 'Mecz'
        verbose_name_plural = 'Mecze'
        ordering = ['-match_date']
        indexes = [
            models.Index(fields=['-match_date']),
            models.Index(fields=['is_doubles']),
        ]

    def __str__(self):
        if self.is_doubles:
            p3_name = self.player3.username if self.player3 else '?'
            p4_name = self.player4.username if self.player4 else '?'
            return f"{self.player1.username}/{p3_name} vs {self.player2.username}/{p4_name} ({self.match_date})"
        return f"{self.player1.username} vs {self.player2.username} ({self.match_date})"

    def get_all_players(self):
        """Zwraca list wszystkich graczy w meczu."""
        players = [self.player1, self.player2]
        if self.is_doubles:
            if self.player3:
                players.append(self.player3)
            if self.player4:
                players.append(self.player4)
        return players
