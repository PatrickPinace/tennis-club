from django.db import models
from django.contrib.auth.models import User


class PlayerRanking(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ranking')
    match_type = models.CharField(max_length=3, default='SNG')  # SNG / DBL
    season = models.PositiveIntegerField(null=True, blank=True)  # None = all-time
    points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    position = models.IntegerField(default=0)
    matches_won = models.IntegerField(default=0)
    matches_lost = models.IntegerField(default=0)
    matches_played = models.IntegerField(default=0)
    sets_won = models.IntegerField(default=0)
    sets_lost = models.IntegerField(default=0)
    games_won = models.IntegerField(default=0)
    games_lost = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'player_rankings'
        unique_together = ('user', 'match_type', 'season')
        ordering = ('-points', '-matches_won', '-sets_won')

    def __str__(self):
        return f"{self.user.username} [{self.match_type}/{self.season or 'all'}] — {self.points} pkt"


class TournamentRankPoints(models.Model):
    """
    Model przechowujący punkty rankingowe przyznawane za turnieje o danej randze.
    """
    rank = models.PositiveIntegerField(
        unique=True,
        verbose_name="Ranga turnieju"
    )
    participation_bonus = models.PositiveIntegerField(
        default=0, 
        verbose_name="Bonus za udział"
    )
    match_win_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        verbose_name="Mnożnik za wygrany mecz"
    )
    set_win_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.5,
        verbose_name="Mnożnik za wygrany set"
    )
    set_loss_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=-0.5,
        verbose_name="Mnożnik za przegrany set"
    )
    game_win_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.1,
        verbose_name="Mnożnik za wygrany gem"
    )
    game_loss_multiplier = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=-0.1,
        verbose_name="Mnożnik za przegrany gem"
    )

    def __str__(self):
        return f"Ranga {self.rank}: {self.participation_bonus} pkt bonusu"