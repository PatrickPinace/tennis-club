from django.contrib import admin
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages

from .models import TournamentRankPoints, PlayerRanking
from apps.rankings.services.ranking_calculator import rebuild_rankings


class RecalculateRankingForm(forms.Form):
    MATCH_TYPE_CHOICES = [
        ('', 'Wszystkie formaty (SNG & DBL)'),
        ('SNG', 'Singiel (SNG)'),
        ('DBL', 'Debel (DBL)'),
    ]
    
    match_type = forms.ChoiceField(
        choices=MATCH_TYPE_CHOICES,
        required=False,
        label='Format meczu'
    )
    
    season = forms.IntegerField(
        required=False,
        label='Sezon (rok)',
        help_text='Pozostaw puste, aby przeliczyć ranking ogólny (all-time) oraz wszystkie sezony.'
    )


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


@admin.register(PlayerRanking)
class PlayerRankingAdmin(admin.ModelAdmin):
    """Panel administracyjny dla rankingu graczy."""
    list_display = (
        'position',
        'user',
        'match_type',
        'season',
        'points',
        'matches_played',
        'matches_won',
        'matches_lost',
    )
    list_filter = ('match_type', 'season')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    ordering = ('match_type', '-season', 'position')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'recalculate-ranking/',
                self.admin_site.admin_view(self.recalculate_ranking_view),
                name='recalculate-ranking',
            ),
        ]
        return custom_urls + urls

    def recalculate_ranking_view(self, request):
        # Sprawdzamy czy ma uprawnienia do edycji
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        if request.method == 'POST':
            form = RecalculateRankingForm(request.POST)
            if form.is_valid():
                match_type = form.cleaned_data.get('match_type') or None
                season = form.cleaned_data.get('season') or None
                
                try:
                    count = rebuild_rankings(match_type=match_type, season=season)
                    messages.success(
                        request,
                        f"Pomyślnie przeliczono ranking Elo dla wybranego formatu i sezonu. Zaktualizowano {count} wpisów."
                    )
                    return redirect('..')
                except Exception as e:
                    messages.error(
                        request,
                        f"Wystąpił błąd podczas przeliczania rankingu: {str(e)}"
                    )
        else:
            form = RecalculateRankingForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Przelicz ranking Elo',
            'opts': self.model._meta,
        }
        return render(request, 'admin/rankings/playerranking/recalculate_form.html', context)