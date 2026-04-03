from django.db import models

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