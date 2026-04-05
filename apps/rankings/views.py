from django.shortcuts import render
from django.db.models.functions import ExtractYear
from apps.tournaments.models import Tournament
from .models import PlayerRanking, TournamentRankPoints


def index(request):
    available_years = (
        Tournament.objects
        .filter(status=Tournament.Status.FINISHED.value, end_date__isnull=False)
        .annotate(year=ExtractYear('end_date'))
        .values_list('year', flat=True)
        .distinct()
        .order_by('-year')
    )

    selected_match_type = request.GET.get('type', 'SNG')
    selected_year_str = request.GET.get('year')

    if selected_year_str is None:
        selected_year = available_years[0] if available_years else None
    elif selected_year_str.isdigit():
        selected_year = int(selected_year_str)
    else:
        selected_year = None  # "Wszystkie lata"

    rankings = (
        PlayerRanking.objects
        .filter(match_type=selected_match_type, season=selected_year)
        .select_related('user')
        .order_by('position')
    )

    scoring_rules = TournamentRankPoints.objects.order_by('rank')

    context = {
        'player_rankings': rankings,
        'available_years': available_years,
        'selected_year': selected_year,
        'selected_match_type': selected_match_type,
        'scoring_rules': scoring_rules,
        'is_precomputed': True,
    }
    return render(request, 'rankings/index.html', context)
