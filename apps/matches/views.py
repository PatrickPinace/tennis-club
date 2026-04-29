from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.models import User
from django.http import Http404
from apps.tournaments.models import TournamentsMatch

from . import tools
from apps.tournaments.tools import get_single_tournament_match_as_friendly

from .forms import MatchCreateForm
from .models import Match

import logging
logger = logging.getLogger(__name__)

@login_required()
def add_match(request):
    if request.method == 'POST':
        form = MatchCreateForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Mecz został dodany.")
            return redirect('matches:matches_add_match')
        else:
            logger.warning(f"Formularz dodawania meczu zawiera błędy: {form.errors}")
            messages.error(request, "Popraw błędy w formularzu.")
    else:
        form = MatchCreateForm(user=request.user, initial={'p1': request.user.pk})

    context = {"form": form}
    return render(request, 'matches/add_match.html', context)

@login_required()
def edit_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)

    # Sprawdzenie, czy użytkownik jest jednym z graczy
    if request.user not in match.get_players():
        messages.error(request, "Nie masz uprawnień do edycji tego meczu.")
        return redirect('matches:matches_results')

    if request.method == 'POST':
        form = MatchCreateForm(request.POST, instance=match, user=request.user)
        if form.is_valid():
            # Pola 'disabled' nie są przesyłane w POST. Musimy ręcznie przywrócić ich wartości.
            
            # 1. Przywrócenie wartości 'match_double'
            form.instance.match_double = match.match_double
                
            form.save()
            messages.success(request, "Wynik meczu został zaktualizowany.")
            return redirect('matches:matches_results')
        else:
            messages.error(request, "Popraw błędy w formularzu.")
    else:
        form = MatchCreateForm(instance=match, user=request.user)
        # Ustaw poprawny format daty dla pola input type="date"
        form.initial['match_date'] = match.match_date.isoformat()

    context = {"form": form, "match": match, "is_edit_match": True}
    return render(request, 'matches/edit_match.html', context)

@login_required()
def results(request):
    user_id = request.GET.get('user_id')
    target_user = request.user
    
    if user_id:
        try:
            target_user = User.objects.get(pk=user_id)
        except (ValueError, User.DoesNotExist):
            pass

    filters = tools.prepare_filters(request)
    # Important: prepare_filters returns filters like 'friend_id' (opponent). 
    # If the user switches profile, they might still have opponent_id in URL.
    # Logic should be: View target_user's matches against opponent_id. 
    # This seems consistent.

    results_obj = tools.Results(request, user=target_user, sort="match_date", **filters)
    summary_obj = tools.Summary(request, user=target_user, matches=results_obj.matches)

    players_for_opponent_filter = tools.get_played_with_players(request, user=target_user)
    doubles_partners_for_filter = tools.get_doubles_partners(request, user=target_user)
    doubles_opponents_for_filter = tools.get_doubles_opponents(request, user=target_user)
    
    all_players = tools.get_all_players_with_matches()

    context = {
        "matches": results_obj.matches,
        "summary": summary_obj.summary["all"]["stats"],
        "all_played_opponents": players_for_opponent_filter, # Dla filtra 'Przeciwnik' w trybie singla
        "doubles_partners": doubles_partners_for_filter, # Dla filtra 'Partner'
        "doubles_opponents": doubles_opponents_for_filter, # Dla filtra 'Partner przeciwnika'
        "years": tools.prepare_years(request, user=target_user),       
        "all_players": all_players,
        "target_user": target_user,
    }
    return render(request, 'matches/results.html', context)


@login_required()
def remove_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.user not in match.get_players():
        messages.error(request, "Nie masz uprawnień do usunięcia tego meczu.")
        return redirect('matches:matches_results')
    match.delete()
    messages.success(request, "Mecz został usunięty.")
    return redirect('matches:matches_results')

def match_detail(request, match_id):
    is_tournament_match = False
    # Sprawdzamy, czy ID dotyczy meczu turniejowego (np. 't_123')
    if str(match_id).startswith('t_'):
        is_tournament_match = True
        try:
            tournament_match_id = int(str(match_id).split('_')[1])
            # Używamy nowej funkcji do pobrania meczu turniejowego w formacie "przyjaznym"
            match = get_single_tournament_match_as_friendly(tournament_match_id)
            if not match:
                raise Http404("Mecz turniejowy nie został znaleziony.")
        except (IndexError, ValueError):
            raise Http404("Nieprawidłowy format ID meczu turniejowego.")
    else:
        # Standardowe pobieranie meczu towarzyskiego
        match = get_object_or_404(Match, id=match_id)
    
    # Określenie pozycji zalogowanego użytkownika w meczu
    owner_position = 0
    if request.user == getattr(match, 'p1', None) or (getattr(match, 'match_double', False) and request.user == getattr(match, 'p3', None)):
        owner_position = 1
    elif request.user == getattr(match, 'p2', None) or (getattr(match, 'match_double', False) and request.user == getattr(match, 'p4', None)):
        owner_position = 2

    context = {
        'match': match,
        'is_tournament_match': is_tournament_match,
    }
    return render(request, 'matches/match_detail.html', context)


@login_required()
def summary(request):
    user_id = request.GET.get('user_id')
    target_user = request.user
    
    if user_id:
        try:
            target_user = User.objects.get(pk=user_id)
        except (ValueError, User.DoesNotExist):
            pass

    filters = tools.prepare_filters(request)    
    results_obj = tools.Results(request, user=target_user, sort="match_date", **filters)
    summary_obj = tools.Summary(request, user=target_user, matches=results_obj.matches, sort="all_gem")    

    players_for_opponent_filter = tools.get_played_with_players(request, user=target_user)
    doubles_partners_for_filter = tools.get_doubles_partners(request, user=target_user)
    doubles_opponents_for_filter = tools.get_doubles_opponents(request, user=target_user)
    
    all_players = tools.get_all_players_with_matches()

    context = {
        "matches": results_obj.matches,
        "summary": summary_obj.summary,
        "years": tools.prepare_years(request, user=target_user),
        "all_played_opponents": players_for_opponent_filter,
        "doubles_partners": doubles_partners_for_filter,
        "doubles_opponents": doubles_opponents_for_filter,
        "all_players": all_players,
        "target_user": target_user,
    }
    # Jeśli wybrano konkretnego przeciwnika
    if filters.get("friend_id") not in [None, ""]:
        # Jeśli wybrano zakres dat "Wszystkie"
        if filters.get("last_days") == 0:
            # Pobierz podsumowanie roczne
            context["yearly_summary"] = summary_obj.get_yearly_summary(filters.get("friend_id"))
        # Jeśli wybrano niestandardowy zakres dat (rok)
        elif filters.get("last_days") not in [0, 7, 30]:
            context["months"] = summary_obj.get_months(filters.get("friend_id"), filters.get("last_days"))
    return render(request, 'matches/summary.html', context)


