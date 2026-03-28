"""Rankings and tournament points."""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class RankingHistory(models.Model):
    """Historia zmian w rankingu gracza."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ranking_history'
    )

    # Snapshot date
    date = models.DateField(auto_now_add=True)

    # Rankings
    elo_rating = models.IntegerField()
    ranking_points = models.DecimalField(max_digits=10, decimal_places=2)
    position = models.PositiveIntegerField(
        null=True,
        help_text='Pozycja w rankingu klubowym'
    )

    # Match stats
    total_matches = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)

    class Meta:
        db_table = 'ranking_history'
        verbose_name = 'Historia rankingu'
        verbose_name_plural = 'Historie rankingów'
        ordering = ['-date', 'position']
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['date', 'position']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.date} (#{self.position})"


class TournamentRankPoints(models.Model):
    """Punkty rankingowe za turnieje różnej rangi."""
    rank = models.PositiveIntegerField(
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        help_text='Ranga turnieju (1-3)'
    )

    # Points
    winner_points = models.IntegerField(default=100)
    finalist_points = models.IntegerField(default=70)
    semifinal_points = models.IntegerField(default=45)
    quarterfinal_points = models.IntegerField(default=25)
    participation_points = models.IntegerField(default=10)

    class Meta:
        db_table = 'tournament_rank_points'
        verbose_name = 'Punkty za rangę turnieju'
        verbose_name_plural = 'Punkty za rangę turnieju'
        ordering = ['rank']

    def __str__(self):
        return f"Ranga {self.rank}"
