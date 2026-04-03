from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.contenttypes.models import ContentType
from apps.activities.models import Activity
from django.db import models # Dodaj ten import
from django.contrib.auth.models import User
from django.http import Http404
from apps.utils.tennis_stats_parser import TennisStatsParser
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

    # Używamy nowego, scentralizowanego parsera
    parsed_player_stats = TennisStatsParser.parse_match_activities(match, owner_position)
    
    context = {
        'match': match,
        'player_stats': parsed_player_stats,
        'owner_position': owner_position,
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

@login_required
def assign_activity(request, match_id):
    is_tournament_match = str(match_id).startswith('t_')

    if is_tournament_match:
        try:
            tournament_match_id = int(str(match_id).split('_')[1])
            match = get_object_or_404(TournamentsMatch, id=tournament_match_id)
            # Używamy adaptera, aby obiekt turniejowy wyglądał jak towarzyski dla szablonu
            match_for_template = get_single_tournament_match_as_friendly(tournament_match_id)
        except (IndexError, ValueError):
            raise Http404("Nieprawidłowy format ID meczu turniejowego.")
    else:
        match = get_object_or_404(Match, id=match_id)
        match_for_template = match
    
    # Sprawdzenie, czy zalogowany użytkownik jest jednym z graczy
    players = match_for_template.get_players()
    if request.user not in players:
        messages.error(request, "Nie możesz zarządzać aktywnościami dla meczu, w którym nie bierzesz udziału.")
        return redirect('matches:match_detail', match_id=match_id)

    if request.method == 'POST':
        activity_id = request.POST.get('activity')
        stats_owner_side = request.POST.get('stats_owner_side') # 'L' or 'P'

        # Pobierz wybraną aktywność, jeśli istnieje
        selected_activity = None
        
        # Logika odpinania aktywności
        if 'unassign' in request.POST:
            activity_to_unassign_id = request.POST.get('unassign')
            try:
                activity_to_unassign = Activity.objects.get(id=activity_to_unassign_id, user=request.user)
                if activity_to_unassign.content_object == match:
                    activity_to_unassign.content_object = None
                    activity_to_unassign.save()
                    messages.success(request, f"Pomyślnie odpięto aktywność '{activity_to_unassign.activity_name}'.")
            except Activity.DoesNotExist:
                messages.error(request, "Nie znaleziono aktywności do odpięcia.")
            return redirect('matches:assign_activity', match_id=match_id)

        # Logika przypinania aktywności
        if activity_id:
            try:
                selected_activity = Activity.objects.get(id=activity_id, user=request.user)

                # Sprawdzenie, czy aktywność jest tenisowa i ma dane deweloperskie
                is_tennis_activity_with_data = (
                    selected_activity.activity_type_key == 'tennis_v2' and
                    selected_activity.tennis_data_fetched
                )

                if is_tennis_activity_with_data:
                    if stats_owner_side not in ['L', 'P']:
                        messages.error(request, "Wybierz, czy Twoje statystyki są po lewej (L) czy prawej (P) stronie danych Garmin.")
                        return redirect('matches:assign_activity', match_id=match_id)

                selected_activity.content_object = match
                selected_activity.save()
                messages.success(request, f"Pomyślnie przypisano aktywność '{selected_activity.activity_name}'.")

                if is_tennis_activity_with_data:
                    try:
                        tennis_data = selected_activity.tennis_data
                        tennis_data.owner_stats_side = stats_owner_side
                        tennis_data.save()
                    except Activity.tennis_data.RelatedObjectDoesNotExist:
                        messages.warning(request, "Aktywność tenisowa, ale brak powiązanych danych Tennis Studio do aktualizacji graczy.")
                    except Exception as e:
                        logger.error(f"Błąd podczas aktualizacji TennisData dla aktywności {activity_id}: {e}")
                        messages.error(request, "Wystąpił błąd podczas aktualizacji danych tenisowych.")
            except Activity.DoesNotExist:
                messages.error(request, "Wybrana aktywność nie istnieje lub nie masz do niej uprawnień.")
        else:
            messages.warning(request, "Nie wybrano żadnej aktywności do przypisania.")
        return redirect('matches:assign_activity', match_id=match_id)

    # GET
    match_date = match.match_date if isinstance(match, Match) else match.scheduled_time.date()
    
    # Aktywności zalogowanego użytkownika z dnia meczu, które nie są jeszcze przypisane do ŻADNEGO meczu
    candidate_activities = Activity.objects.filter(
        user=request.user,
        start_time__date=match_date,
        object_id__isnull=True # Aktywności, które nie są jeszcze przypisane do żadnego obiektu
    ).annotate(
        has_tennis_data=models.Exists(
            Activity.objects.filter(pk=models.OuterRef('pk'), tennis_data__isnull=False)
        )
    ).select_related('user')

    # Aktywności już przypisane do tego meczu (przez zalogowanego użytkownika)
    assigned_activities = match.activities.filter(user=request.user).select_related('tennis_data')

    context = {
        'match': match_for_template,
        'candidate_activities': candidate_activities,
        'assigned_activities': assigned_activities,
    }
    return render(request, 'matches/assign_activity.html', context)
