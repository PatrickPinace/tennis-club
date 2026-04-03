from django.shortcuts import render
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, Q, Sum, F, Case, When, IntegerField, Value, Subquery, OuterRef, functions, DecimalField
from .models import TournamentRankPoints
from django.db.models.functions import Coalesce
from apps.tournaments.models import Tournament, TournamentsMatch, Participant
from datetime import date


def index(request):
    """
    Widok generujący i wyświetlający ranking graczy na podstawie wyników
    w zakończonych turniejach.
    """

    # Pobierz dostępne lata do filtrowania
    available_years = Tournament.objects.filter(
        status=Tournament.Status.FINISHED.value,
        end_date__isnull=False
    ).annotate(
        year=functions.ExtractYear('end_date')
    ).values_list('year', flat=True).distinct().order_by('-year')

    # Definiuj wspólny filtr dla zakończonych turniejów
    finished_tournament_filter = Q(tournament__status=Tournament.Status.FINISHED.value)

    # --- POPRAWKA: Dodaj filtr statusu meczu, aby liczyć tylko zakończone mecze ---
    completed_match_filter = Q(status=TournamentsMatch.Status.COMPLETED.value)

    # --- Filtracja ---
    selected_year_str = request.GET.get('year')
    selected_year = None
    selected_match_type = request.GET.get('type', 'SNG')  # Domyślnie 'SNG' (Single)

    if selected_year_str is None:
        # --- ZMIANA: Domyślnie ustaw najnowszy dostępny rok, jeśli żaden nie jest wybrany ---
        if available_years:
            selected_year = available_years[0]  # available_years jest posortowane malejąco
            finished_tournament_filter &= Q(tournament__end_date__year=selected_year)
        else:
            selected_year = None # Brak danych, więc nie filtrujemy po roku
    elif selected_year_str.isdigit():
        # Użyj roku wybranego przez użytkownika
        selected_year = int(selected_year_str)
        finished_tournament_filter &= Q(tournament__end_date__year=selected_year)
    # Jeśli selected_year_str to pusty string (opcja "Wszystkie"), nie dodawaj filtra roku

    if selected_match_type == 'SNG':
        finished_tournament_filter &= Q(tournament__match_format=Tournament.MatchFormat.SINGLES.value)
    elif selected_match_type == 'DBL':
        finished_tournament_filter &= Q(tournament__match_format=Tournament.MatchFormat.DOUBLES.value)

    # Subzapytania do agregacji gemów, setów i super tie-breaków
    # Agregują statystyki dla użytkownika występującego jako participant1 lub participant2 w meczu.

    # --- Gemy wygrane/przegrane ---
    games_won_as_p1_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter &
            Q(participant1__user=OuterRef('pk'))
        ).order_by().values('participant1__user').annotate(
            total=Sum(Coalesce(F('set1_p1_score'), 0) + Coalesce(F('set2_p1_score'), 0) + Coalesce(F('set3_p1_score'), 0))            

        ).values('total')[:1],
        output_field=IntegerField()
    )
    games_won_as_p2_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant2__user=OuterRef('pk')
        ).order_by().values('participant2__user').annotate(
            total=Sum(Coalesce(F('set1_p2_score'), 0) + Coalesce(F('set2_p2_score'), 0) + Coalesce(F('set3_p2_score'), 0))
        ).values('total')[:1],
        output_field=IntegerField()
    )

    games_lost_as_p1_subquery = Subquery(
       TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter &
            Q(participant1__user=OuterRef('pk'))
        ).order_by().values('participant1__user').annotate(            
            total=Sum(Coalesce(F('set1_p2_score'), 0) + Coalesce(F('set2_p2_score'), 0) + Coalesce(F('set3_p2_score'), 0))
        ).values('total')[:1],
        output_field=IntegerField()
    )
    games_lost_as_p2_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant2__user=OuterRef('pk')
        ).order_by().values('participant2__user').annotate(
            total=Sum(Coalesce(F('set1_p1_score'), 0) + Coalesce(F('set2_p1_score'), 0) + Coalesce(F('set3_p1_score'), 0))
        ).values('total')[:1],
        output_field=IntegerField()
    )

    # Nowe subzapytania, które łączą role participant1 i participant2
    total_games_won_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter &
            (Q(participant1__user=OuterRef('pk')) | Q(participant2__user=OuterRef('pk')))
        ).order_by().values('pk').annotate(
            total=Sum(
                Case(
                    When(participant1__user=OuterRef('pk'), then=Coalesce(F('set1_p1_score'), 0) + Coalesce(F('set2_p1_score'), 0) + Coalesce(F('set3_p1_score'), 0)),
                    default=Coalesce(F('set1_p2_score'), 0) + Coalesce(F('set2_p2_score'), 0) + Coalesce(F('set3_p2_score'), 0),
                    output_field=IntegerField()
                )
            )
        ).values('total')[:1],
        output_field=IntegerField()
    )

    total_games_lost_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter &
            (Q(participant1__user=OuterRef('pk')) | Q(participant2__user=OuterRef('pk')))
        ).order_by().values('pk').annotate(
            total=Sum(
                Case(
                    When(participant1__user=OuterRef('pk'), then=Coalesce(F('set1_p2_score'), 0) + Coalesce(F('set2_p2_score'), 0) + Coalesce(F('set3_p2_score'), 0)),
                    default=Coalesce(F('set1_p1_score'), 0) + Coalesce(F('set2_p1_score'), 0) + Coalesce(F('set3_p1_score'), 0),
                    output_field=IntegerField()
                )
            )
        ).values('total')[:1],
        output_field=IntegerField()
    )

    # Podobne zmiany dla setów







    # --- Sety wygrane/przegrane ---
    sets_won_as_p1_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant1__user=OuterRef('pk')
        ).order_by().values('participant1__user').annotate(
            total=Sum(
                Case(When(Q(set1_p1_score__gt=F('set1_p2_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set2_p1_score__gt=F('set2_p2_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set3_p1_score__gt=F('set3_p2_score')), then=1), default=0, output_field=IntegerField())
            )
        ).values('total')[:1],
        output_field=IntegerField()
    )
    sets_won_as_p2_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant2__user=OuterRef('pk')
        ).order_by().values('participant2__user').annotate(
            total=Sum(
                Case(When(Q(set1_p2_score__gt=F('set1_p1_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set2_p2_score__gt=F('set2_p1_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set3_p2_score__gt=F('set3_p1_score')), then=1), default=0, output_field=IntegerField())
            )
        ).values('total')[:1],
        output_field=IntegerField()
    )

    sets_lost_as_p1_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant1__user=OuterRef('pk')
        ).order_by().values('participant1__user').annotate(
            total=Sum(
                Case(When(Q(set1_p1_score__lt=F('set1_p2_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set2_p1_score__lt=F('set2_p2_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set3_p1_score__lt=F('set3_p2_score')), then=1), default=0, output_field=IntegerField())
            )
        ).values('total')[:1],
        output_field=IntegerField()
    )
    sets_lost_as_p2_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant2__user=OuterRef('pk')
        ).order_by().values('participant2__user').annotate(
            total=Sum(
                Case(When(Q(set1_p2_score__lt=F('set1_p1_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set2_p2_score__lt=F('set2_p1_score')), then=1), default=0, output_field=IntegerField()) +
                Case(When(Q(set3_p2_score__lt=F('set3_p1_score')), then=1), default=0, output_field=IntegerField())
            )
        ).values('total')[:1],
        output_field=IntegerField()
    )
    

    # Subzapytania do zliczania rozegranych meczów
    matches_as_p1_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant1__user=OuterRef('pk')
        ).order_by().values('participant1__user').annotate(count=Count('id')).values('count')[:1],
        output_field=IntegerField()
    )
    matches_as_p2_subquery = Subquery(
        TournamentsMatch.objects.filter(
            finished_tournament_filter & completed_match_filter,
            participant2__user=OuterRef('pk')
        ).order_by().values('participant2__user').annotate(count=Count('id')).values('count')[:1],
        output_field=IntegerField()
    )
    
    # Krok 2: Oblicz punkty dla każdego użytkownika.
    # Używamy adnotacji, aby wykonać obliczenia w bazie danych.
    player_rankings = User.objects.annotate(
        # Zlicz wygrane mecze w zakończonych turniejach.
        # Musimy użyć subzapytania, aby poprawnie zastosować filtr roku.
        matches_won=Count(
            'tournament_participations__won_matches', # Relacja do wygranych meczów
            filter=Q(tournament_participations__won_matches__in=Subquery( # Upewnij się, że wygrane mecze są z właściwego okresu
                TournamentsMatch.objects.filter(finished_tournament_filter).values('pk')
            )),
            distinct=True
        )
    ).annotate(
        # Zlicz wszystkie rozegrane mecze (jako p1 lub p2) w zakończonych turniejach
        matches_played=Coalesce(matches_as_p1_subquery, 0) + Coalesce(matches_as_p2_subquery, 0),
        # --- Adnotacje dla gemów i setów ---
        _games_won_p1=Coalesce(games_won_as_p1_subquery, 0),
        _games_won_p2=Coalesce(games_won_as_p2_subquery, 0),
        _games_lost_p1=Coalesce(games_lost_as_p1_subquery, 0),
        _games_lost_p2=Coalesce(games_lost_as_p2_subquery, 0),
        _sets_won_p1=Coalesce(sets_won_as_p1_subquery, 0),

        _sets_won_p2=Coalesce(sets_won_as_p2_subquery, 0),
        _sets_lost_p1=Coalesce(sets_lost_as_p1_subquery, 0),
        _sets_lost_p2=Coalesce(sets_lost_as_p2_subquery, 0),
    ).annotate(

        # Połącz statystyki z ról P1 i P2
        total_games_won=F('_games_won_p1') + F('_games_won_p2'),
        total_games_lost=F('_games_lost_p1') + F('_games_lost_p2'),
        total_sets_won=F('_sets_won_p1') + F('_sets_won_p2'),
        total_sets_lost=F('_sets_lost_p1') + F('_sets_lost_p2'),
    ).annotate(
        total_games_played=F('total_games_won') + F('total_games_lost'),
        total_sets_played=F('total_sets_won') + F('total_sets_lost'),
    ).annotate(
        # Oblicz liczbę przegranych meczów
        matches_lost=F('matches_played') - F('matches_won')
    ).annotate(
        # Krok 1: Określ najwyższą rangę turnieju, w którym użytkownik brał udział
        # (spośród zakończonych turniejów, zgodnych z filtrem typu meczu).
        # To zapewnia deterministyczne pobieranie mnożników.
        user_highest_tournament_rank=Subquery(
            Participant.objects.filter(
                user=OuterRef('pk'),
                tournament__status=Tournament.Status.FINISHED.value,
                tournament__end_date__isnull=False,
                tournament__match_format=selected_match_type,
                # Jeśli selected_year jest ustawiony, dodaj filtr roku do wyboru rangi
                **(
                    {'tournament__end_date__year': selected_year}
                    if selected_year else {}
                )
            ).order_by('-tournament__rank').values('tournament__rank')[:1],
            output_field=IntegerField()
        ),
        # Krok 2: Pobierz indywidualne mnożniki z TournamentRankPoints
        # na podstawie określonej najwyższej rangi turnieju.
        match_win_multiplier_val=Coalesce(
            Subquery(
                TournamentRankPoints.objects.filter(
                    rank=OuterRef('user_highest_tournament_rank')
                ).values('match_win_multiplier')[:1],
                output_field=DecimalField()
            ),
            Value(1.0, output_field=DecimalField()) # Wartość domyślna
        ),
        set_win_multiplier_val=Coalesce(
            Subquery(
                TournamentRankPoints.objects.filter(
                    rank=OuterRef('user_highest_tournament_rank')
                ).values('set_win_multiplier')[:1],
                output_field=DecimalField()
            ),
            Value(0.5, output_field=DecimalField()) # Wartość domyślna
        ),
        set_loss_multiplier_val=Coalesce(
            Subquery(
                TournamentRankPoints.objects.filter(
                    rank=OuterRef('user_highest_tournament_rank')
                ).values('set_loss_multiplier')[:1],
                output_field=DecimalField()
            ),
            Value(-0.5, output_field=DecimalField()) # Wartość domyślna
        ),
        game_win_multiplier_val=Coalesce(
            Subquery(
                TournamentRankPoints.objects.filter(
                    rank=OuterRef('user_highest_tournament_rank')
                ).values('game_win_multiplier')[:1],
                output_field=DecimalField()
            ),
            Value(0.1, output_field=DecimalField()) # Wartość domyślna
        ),
        game_loss_multiplier_val=Coalesce(
            Subquery(
                TournamentRankPoints.objects.filter(
                    rank=OuterRef('user_highest_tournament_rank')
                ).values('game_loss_multiplier')[:1],
                output_field=DecimalField()
            ),
            Value(-0.1, output_field=DecimalField()) # Wartość domyślna
        ),
        participation_bonus_val=Coalesce(
            Subquery(
                TournamentRankPoints.objects.filter(
                    rank=OuterRef('user_highest_tournament_rank')
                ).values('participation_bonus')[:1],
                output_field=DecimalField()
            ),
            Value(0.0, output_field=DecimalField()) # Wartość domyślna
        ),
        total_points=(
            F('participation_bonus_val') +
            F('matches_won') * F('match_win_multiplier_val') +
            F('total_sets_won') * F('set_win_multiplier_val') +
            F('total_sets_lost') * F('set_loss_multiplier_val') +
            F('total_games_won') * F('game_win_multiplier_val') +
            F('total_games_lost') * F('game_loss_multiplier_val')
        )
    ).filter(
        # Pokaż tylko graczy, którzy rozegrali co najmniej jeden mecz
        matches_played__gt=0
    ).order_by('-total_points', '-matches_won')  # Sortuj po punktach, a następnie po liczbie wygranych

    # Pobierz wszystkie zdefiniowane zasady punktacji, aby wyświetlić je w szablonie
    scoring_rules = TournamentRankPoints.objects.order_by('rank')

    context = {
        'player_rankings': player_rankings,
        'available_years': available_years,
        'selected_year': selected_year,
        'selected_match_type': selected_match_type,
        'scoring_rules': scoring_rules,
    }
    return render(request, 'rankings/index.html', context)