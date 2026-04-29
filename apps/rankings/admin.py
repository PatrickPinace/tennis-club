from django.contrib import admin
from .models import TournamentRankPoints


@admin.register(TournamentRankPoints)
class TournamentRankPointsAdmin(admin.ModelAdmin):
    """Panel administracyjny dla punktacji rang turniejów."""
    list_display = (
        'rank',
        'participation_bonus',
        'match_win_multiplier',
        'set_win_multiplier',
        'set_loss_multiplier',
        'game_win_multiplier',
        'game_loss_multiplier',
    )
    ordering = ('rank',)