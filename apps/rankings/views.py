from django.shortcuts import render
from django.db.models.functions import ExtractYear
from apps.tournaments.models import Tournament
from .models import PlayerRanking, TournamentRankPoints, RankingCalculationInfo


def index(request):
    years_end = (
        Tournament.objects
        .filter(status__in=[Tournament.Status.FINISHED.value, Tournament.Status.ACTIVE.value], end_date__isnull=False)
        .annotate(year=ExtractYear('end_date'))
        .values_list('year', flat=True)
        .distinct()
    )
    years_start = (
        Tournament.objects
        .filter(status__in=[Tournament.Status.FINISHED.value, Tournament.Status.ACTIVE.value], end_date__isnull=True, start_date__isnull=False)
        .annotate(year=ExtractYear('start_date'))
        .values_list('year', flat=True)
        .distinct()
    )
    available_years = sorted(list(set(years_end) | set(years_start)), reverse=True)

    selected_match_type = request.GET.get('type', 'SNG')
    selected_year_str = request.GET.get('year')

    if selected_year_str is None:
        selected_year = None  # Domyślnie "Wszystkie lata" (All-time)
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
    latest_update = RankingCalculationInfo.objects.order_by('-last_run').first()

    context = {
        'player_rankings': rankings,
        'available_years': available_years,
        'selected_year': selected_year,
        'selected_match_type': selected_match_type,
        'scoring_rules': scoring_rules,
        'latest_update': latest_update,
        'is_precomputed': True,
    }
    return render(request, 'rankings/index.html', context)
