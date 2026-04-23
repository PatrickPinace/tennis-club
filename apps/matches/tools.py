from django.utils import timezone
from datetime import timedelta
from .models import Match
from django.contrib.auth.models import User
from django.db import models

import logging
logger = logging.getLogger(__name__)

def _calculate_set_winner(p1_score, p2_score):
    """Określa zwycięzcę seta na podstawie wyników."""
    # Konwersja na liczby całkowite na początku
    p1_score, p2_score = int(p1_score), int(p2_score)

    # Warunki zwycięstwa dla gracza 1
    p1_wins_standard_set = (p1_score == 6 and p2_score < 5) or (p1_score == 7 and p2_score in [5, 6])
    # Warunki zwycięstwa dla gracza 1 w super tie-breaku (lub innym tie-breaku do 10)
    p1_wins_super_tiebreak = (p1_score >= 10 and (p1_score - p2_score) >= 2)

    if p1_wins_standard_set or p1_wins_super_tiebreak:
        return 'p1'

    # Warunki zwycięstwa dla gracza 2
    p2_wins_standard_set = (p2_score == 6 and p1_score < 5) or (p2_score == 7 and p1_score in [5, 6])
    p2_wins_super_tiebreak = (p2_score >= 10 and (p2_score - p1_score) >= 2)

    if p2_wins_standard_set or p2_wins_super_tiebreak:
        return 'p2'

    # Jeśli żaden z warunków zwycięstwa nie został spełniony, set jest nierozstrzygnięty
    return None

class Results:
    def __init__(self, request, user=None, **kwargs):        
        self.matches = []
        self.qs = Match.objects.none()
        self.user = user or request.user
        self.get_matches(request, **kwargs)

        # Jeśli nie ma meczów, nie ma potrzeby dalszego przetwarzania
        if not self.matches:
            return

        self.add_statistics(request)

        if kwargs.get("sort"):
            if kwargs["sort"] == "match_date":
                self.matches.sort(key=lambda x: x.get("match_date"), reverse=True)
                self.add_row_no(reverse=True)
                    
    def add_row_no(self, **kwargs):
        if kwargs.get("reverse"):
            row_no = len(self.matches)
            for row in self.matches:
                row["row_no"] = row_no
                row_no -= 1
        else:
            row_no = 1
            for row in self.matches:
                row["row_no"] = row_no
                row_no += 1        

    def add_statistics(self, request, **kwargs):
        for row in self.matches:
            row["user"] = ""
            row["win"] = ""
            p1_win_point = 0
            p2_win_point = 0
            p1_win_gem = 0
            p2_win_gem = 0
            p1_win_set = 0
            p2_win_set = 0
            for i in [1, 2, 3]:
                p1_score = int(row.get(f'p1_set{i}') or 0)
                p2_score = int(row.get(f'p2_set{i}') or 0)

                if p1_score > 7 or p2_score > 7:
                    p1_win_point += p1_score
                    p2_win_point += p2_score
                else:
                    p1_win_gem += p1_score
                    p2_win_gem += p2_score
                
                set_winner = _calculate_set_winner(p1_score, p2_score)
                if set_winner == 'p1':
                    p1_win_set += 1
                elif set_winner == 'p2':
                    p2_win_set += 1

            # Ujednolicona i poprawiona logika określania zwycięzcy meczu
            # Mecz jest wygrany, jeśli jeden z graczy wygrał co najmniej 2 sety i ma więcej wygranych setów niż przeciwnik.
            if p1_win_set >= 2 and p1_win_set > p2_win_set:
                row['win'] = "p1"
                # Sprawdzenie, czy docelowy użytkownik jest w zwycięskiej drużynie
                if self.user.pk in [row.get("p1_id"), row.get("p3_id")]:
                    row["user"] = "user-win"
                else:
                    row["user"] = "user-loss"
            elif p2_win_set >= 2 and p2_win_set > p1_win_set:
                row['win'] = "p2"
                # Sprawdzenie, czy docelowy użytkownik jest w zwycięskiej drużynie
                if self.user.pk in [row.get("p2_id"), row.get("p4_id")]:
                    row["user"] = "user-win"
                else:
                    row["user"] = "user-loss"
            else:
                row['win'] = 'draw'
                row["user"] = "user-draw"

            row['p1_win_point'] = p1_win_point
            row['p2_win_point'] = p2_win_point
            row['p1_win_gem'] = p1_win_gem
            row['p2_win_gem'] = p2_win_gem
            row['p1_win_set'] = p1_win_set
            row['p2_win_set'] = p2_win_set
                    
    def get_matches(self, request, **kwargs):
        from apps.tournaments.tools import get_tournament_matches_as_friendly
        from apps.utils import tools
        from django.db import models
        # Base queryset: matches where any player is the user or in friends set (controlled by views)
        qs = Match.objects.all()
        if kwargs.get("match_double") in [0, 1]:
            qs = qs.filter(match_double=bool(kwargs["match_double"]))
        
        if kwargs.get("last_days") in prepare_years(request, user=self.user):
            qs = qs.filter(match_date__year=kwargs.get("last_days"))
        elif kwargs.get("this_year"):
            qs = qs.filter(match_date__year=timezone.now().year)
        # friend filter
        friend_id = kwargs.get("friend_id")
        # uid = request.user.pk -> Używamy self.user.pk
        uid = self.user.pk

        # Zawsze filtruj mecze wybranego użytkownika
        user_q = models.Q(p1=uid) | models.Q(p2=uid) | models.Q(p3=uid) | models.Q(p4=uid)
        qs = qs.filter(user_q)
        
        if friend_id:
            fid = int(friend_id)
            opponent_q = models.Q(p1=fid) | models.Q(p2=fid) | models.Q(p3=fid) | models.Q(p4=fid)
            qs = qs.filter(opponent_q)

        # Filtrowanie po partnerach w deblu
        if kwargs.get("match_double") == 1:
            partner_id = kwargs.get("partner_id")
            opponent_partner_id = kwargs.get("opponent_partner_id")

            if partner_id:
                pid = int(partner_id)
                # Upewnij się, że partner jest w tej samej drużynie co zalogowany użytkownik
                qs = qs.filter( (models.Q(p1=uid) & (models.Q(p3=pid))) | (models.Q(p3=uid) & (models.Q(p1=pid))) | (models.Q(p2=uid) & (models.Q(p4=pid))) | (models.Q(p4=uid) & (models.Q(p2=pid))) )

            if opponent_partner_id and friend_id:
                opid = int(opponent_partner_id)
                fid = int(friend_id)
                # Upewnij się, że partner przeciwnika jest w tej samej drużynie co przeciwnik
                qs = qs.filter( (models.Q(p1=fid) & (models.Q(p3=opid))) | (models.Q(p3=fid) & (models.Q(p1=opid))) | (models.Q(p2=fid) & (models.Q(p4=opid))) | (models.Q(p4=fid) & (models.Q(p2=opid))) )

        self.qs = qs.order_by('-match_date')

        rows = list(qs.values(
            'id', 'p1', 'p2', 'p3', 'p4',
            'p1_set1', 'p1_set2', 'p1_set3',
            'p2_set1', 'p2_set2', 'p2_set3', 'match_double', 'description', 'match_date'
        ))

        # Pobierz mecze turniejowe
        tournament_matches = get_tournament_matches_as_friendly(self.user, filters=kwargs)

        # Połącz obie listy, posortuj po dacie, a następnie zastosuj limit
        self.matches = rows + tournament_matches
        self.matches.sort(key=lambda x: x.get("match_date"), reverse=True)

        if kwargs.get("limit_matches"):
            self.matches = self.matches[:kwargs["limit_matches"]]

        tools.convert_user_id_to_names(request, self.matches)
        # Uzupełnienie brakujących nazw użytkownika (username)
        for match in self.matches:
            for p_key in ['p1', 'p2', 'p3', 'p4']:
                if user_obj := User.objects.filter(id=match.get(f'{p_key}_id')).first():
                    match[f'{p_key}_username'] = user_obj.username

class MatchCounter:
    def __init__(self, request, **kwargs):
        from apps.friends.tools import get_friends_id, convert_auth_user_id_to_name
        self.counters = {}
        friends_id = get_friends_id(request)
        
        for friend_id in friends_id:
            self.counters[friend_id] = {
                "user_name": convert_auth_user_id_to_name(request, friend_id),
                "single": {"period": {}},
                "double": {"period": {}},
            }
            for match_double in [False, True]:
                for period in [{"last_days": 7}, {"last_days": 30}, {"this_year": True}, {"all": True}]:
                    qs = Match.objects.filter(match_double=match_double)
                    
                    # Filtrowanie po graczu (znajomy lub zalogowany użytkownik)
                    player_id = friend_id if friend_id is not None else request.user.id
                    qs = qs.filter(
                        models.Q(p1_id=player_id) | models.Q(p2_id=player_id) |
                        models.Q(p3_id=player_id) | models.Q(p4_id=player_id)
                    )

                    # Filtrowanie po okresie
                    if "last_days" in period and period["last_days"] in [7, 30]:
                        since = timezone.now().date() - timedelta(days=period["last_days"])
                        qs = qs.filter(match_date__gte=since)
                    elif "this_year" in period:
                        qs = qs.filter(match_date__year=timezone.now().year)
                    
                    counter = qs.count()
                    key_name = list(period.keys())[0]
                    bucket = "single" if not match_double else "double"
                    
                    if "last_days" in period:
                        self.counters[friend_id][bucket]["period"][period["last_days"]] = counter
                    else:
                        self.counters[friend_id][bucket]["period"][key_name] = counter
        
        if kwargs.get("sort"):
            sort_key = kwargs["sort"]
            if sort_key == "user_name":
                self.counters = dict(sorted(self.counters.items(), key=lambda item: item[1]["user_name"]))
            elif sort_key == "this_year":
                self.counters = dict(sorted(self.counters.items(), key=lambda item: item[1]["single"]["period"].get("this_year", 0), reverse=True))

class Summary:    
    def __init__(self, request, user=None, **kwargs):   
        """
        Inicjalizuje klasę Summary.
        Pobiera mecze i oblicza podsumowania statystyk.
        """
        self.user = user or request.user
        if kwargs.get("matches") is not None:
            self.request = request
            self.matches = kwargs.get("matches")
        else:
            self.matches = Results(request, user=self.user, **kwargs).matches
        self.summary = {
            "all": {},
            "opponents": {}
        }
        self.init_stats(self.summary["all"])        
        self.user_id = self.user.id        
        self.add_summary()           

        self.sort_opponets(**kwargs)    

    def add_summary(self, **kwargs):
        """
        Dodaje podsumowanie statystyk dla każdego meczu.
        """
        for row in self.matches:                      
            opponent = self.init_opponent(row)         
            if not opponent:
                continue            
            self.calc_winner(row, opponent)
            self.calc_set(row, opponent)
            self.calc_gem(row, opponent)

    def add_to_stats(self, summary, key, win, lose):
        """
        Aktualizuje statystyki w podsumowaniu.
        :param summary: Słownik z podsumowaniem statystyk.
        :param key: Klucz statystyki (np. "match", "set", "gem").
        :param win: Liczba wygranych.
        :param lose: Liczba przegranych.
        """
        summary["stats"][key]["win"] += win
        summary["stats"][key]["lose"] += lose
        summary["stats"][key]["all"] = summary["stats"][key]["win"] + summary["stats"][key]["lose"]  
        summary["stats"][key]["per"] = round((summary["stats"][key]["win"] / summary["stats"][key]["all"]) * 100) if summary["stats"][key]["all"] > 0 else 0 
        if key == "match" and win == 0 and lose == 0:
            summary["stats"][key]["draw"] += 1

    def calc_gem(self, match, opponent):
        """
        Oblicza statystyki gemów dla meczu i przeciwnika.
        :param match: Słownik z danymi meczu.
        :param opponent: Nazwa przeciwnika.
        """
        win = 0
        lose = 0
        if match['p1_id'] == 0:
            win = match['p1_win_gem']
            lose = match['p2_win_gem']
        elif self.user_id in [match['p1_id'], match['p3_id']]:
            win = match['p1_win_gem']
            lose = match['p2_win_gem']
        elif self.user_id in [match['p2_id'], match['p4_id']]:
            win = match['p2_win_gem']
            lose = match['p1_win_gem']
        else:
            return
        self.add_to_stats(self.summary["opponents"][opponent], "gem", win, lose)
        self.add_to_stats(self.summary["all"], "gem", win, lose)
        match_year = str(match["match_date"].year)
        self.add_to_stats(self.summary["opponents"][opponent]["years"][match_year], "gem", win, lose)
        if match.get("match_date"):
            match_month = decode_match_month(match)
            self.add_to_stats(self.summary["opponents"][opponent]["years"][match_year]["months"][match_month], "gem", win, lose)

    def calc_set(self, match, opponent):
        """
        Oblicza statystyki setów dla meczu i przeciwnika.
        :param match: Słownik z danymi meczu.
        :param opponent: Nazwa przeciwnika.
        """
        win = 0
        lose = 0
        if match['p1_id'] == 0:
            win = match['p1_win_set']
            lose = match['p2_win_set']
        elif self.user_id in [match['p1_id'], match['p3_id']]:
            win = match['p1_win_set']
            lose = match['p2_win_set']
        elif self.user_id in [match['p2_id'], match['p4_id']]:
            win = match['p2_win_set']
            lose = match['p1_win_set']
        else:
            return
        self.add_to_stats(self.summary["opponents"][opponent], "set", win, lose)
        self.add_to_stats(self.summary["all"], "set", win, lose)
        match_year = str(match["match_date"].year)
        self.add_to_stats(self.summary["opponents"][opponent]["years"][match_year], "set", win, lose)
        if match.get("match_date"):
            match_month = decode_match_month(match)
            self.add_to_stats(self.summary["opponents"][opponent]["years"][match_year]["months"][match_month], "set", win, lose)
        
    def calc_winner(self, match, opponent):
        """
        Oblicza statystyki zwycięstw dla meczu i przeciwnika.
        :param match: Słownik z danymi meczu.
        :param opponent: Nazwa przeciwnika.
        """
        win = 0
        lose = 0
        draw = 0
        if match['p1_id'] == 0:
            if match['win'] == 'p1':
                win = 1
            else:
                lose = 1
        elif match['win'] == 'p1' and self.user_id in [match['p1_id'], match['p3_id']]:
            win = 1
        elif match['win'] == 'p2' and self.user_id in [match['p2_id'], match['p4_id']]:
            win = 1
        elif match['win'] == 'draw':
            draw = 1
            return
        else:
            lose = 1
        self.add_to_stats(self.summary["opponents"][opponent], "match", win, lose)
        self.add_to_stats(self.summary["all"], "match", win, lose)
        match_year = str(match["match_date"].year)
        self.add_to_stats(self.summary["opponents"][opponent]["years"][match_year], "match", win, lose)
        if match.get("match_date"):
            match_month = decode_match_month(match)
            self.add_to_stats(self.summary["opponents"][opponent]["years"][match_year]["months"][match_month], "match", win, lose)        

    def init_months(self, year_summary):
        """
        Inicjalizuje statystyki dla każdego miesiąca w roku.
        :param year_summary: Słownik z podsumowaniem rocznym.
        """
        if not year_summary.get("months"):
            year_summary["months"] = {}
        for month in prepare_months():
            if not year_summary["months"].get(month):
                year_summary["months"][month] = {}
            self.init_stats(year_summary["months"][month])

    def get_opponent(self, opponent_id):
        """
        Pobiera dane przeciwnika na podstawie jego ID.
        :param opponent_id: ID przeciwnika.
        :return: Słownik z danymi przeciwnika.
        """
        for key, value in self.summary["opponents"].items():
            if opponent_id in value["team"]["opponent_id"]:
                return value

    def get_years(self, opponent_id):
        """
        Pobiera lata, w których gracz grał z danym przeciwnikiem.
        :param opponent_id: ID przeciwnika.
        :return: Słownik z latami.
        """
        opponent = self.get_opponent(opponent_id)        
        if opponent:
            return opponent.get("years", {})
        
    def get_months(self, opponent_id, year):
        years = self.get_years(opponent_id)
        if years and years.get(year):
            return years[year].get("months", {})

    def get_yearly_summary(self, opponent_id):
        """
        Generuje podsumowanie meczów z podziałem na lata dla danego przeciwnika.
        """
        from collections import defaultdict
        from itertools import groupby
        # Inicjalizacja słownika do przechowywania meczów pogrupowanych po roku
        yearly_matches = defaultdict(list)

        # Sortuj mecze po dacie (malejąco), aby poprawnie zgrupować je po roku
        sorted_matches = sorted(self.matches, key=lambda m: m['match_date'], reverse=True)

        # Grupuj mecze po roku
        for year, matches_in_year in groupby(sorted_matches, key=lambda m: m['match_date'].year):
            yearly_matches[year] = list(matches_in_year)

        final_summary = {}
        for year, matches in yearly_matches.items():
            temp_summary_obj = Summary(self.request, matches=matches, sort="all_gem")
            final_summary[year] = temp_summary_obj.summary
        return final_summary

    def init_years(self, opponent):
        """
        Inicjalizuje lata dla danego przeciwnika.
        :param opponent: Słownik z danymi przeciwnika.
        """
        if not opponent.get("years"):
            opponent["years"] = {}
        for year in prepare_years(self.request, user=self.user):
            if not opponent["years"].get(year):
                opponent["years"][year] = {}
            self.init_stats(opponent["years"][year])
            self.init_months(opponent["years"][year])

    def init_opponent(self, match):        
        """
        Inicjalizuje dane przeciwnika na podstawie danych meczu.
        :param match: Słownik z danymi meczu.
        :return: Nazwa przeciwnika.
        """
        if match['match_double']:
            players = 4
            if match['p1_id'] == 0:
                team = self.prepare_team(match, my=('p1', 'p3'), opponent=('p2', 'p4'))                
            elif self.user_id in [match['p1_id'], match['p3_id']]:
                if not self.summary["opponents"].get(f"{match['p4_id']}_{match['p2_id']}"):
                    team = self.prepare_team(match, my=('p1', 'p3'), opponent=('p2', 'p4'))
                else:
                    team = self.prepare_team(match, my=('p1', 'p3'), opponent=('p4', 'p2'))
            elif self.user_id in [match['p2_id'], match['p4_id']]:
                if not self.summary["opponents"].get(f"{match['p3_id']}_{match['p1_id']}"):
                    team = self.prepare_team(match, my=('p2', 'p4'), opponent=('p1', 'p3'))
                else:
                    team = self.prepare_team(match, my=('p2', 'p4'), opponent=('p3', 'p1'))
            else:
                return   
        else:
            players = 2
            if match['p1_id'] == 0 or match['p1_id'] == self.user_id:
                team = self.prepare_team(match, my=('p1',), opponent=('p2',))
            elif match['p2_id'] == self.user_id:
                team = self.prepare_team(match, my=('p2',), opponent=('p1',))
            else:
                return
        if not self.is_in_summary(team):
            self.summary["opponents"][team["unique_name"]] = {
                "players": players,
                "team": team
            }
            self.init_stats(self.summary["opponents"][team["unique_name"]])
            self.init_years(self.summary["opponents"][team["unique_name"]])            
        return team["unique_name"]

    def init_stats(self, summary):
        """
        Inicjalizuje statystyki w podsumowaniu.
        :param summary: Słownik z podsumowaniem.
        """
        if not summary.get("stats"):
            summary["stats"] = {
                "match": {"win": 0, "lose": 0, "draw": 0, "all": 0},
                "set": {"win": 0, "lose": 0, "all": 0},
                "gem": {"win": 0, "lose": 0, "all": 0},
                "point": {"win": 0, "lose": 0, "all": 0},
            }

    def is_in_summary(self, team: dict):
        """
        Sprawdza, czy dany zespół jest już w podsumowaniu.
        :param team: Słownik z danymi zespołu.
        :return: True, jeśli zespół jest w podsumowaniu, False w przeciwnym razie.
        """
        if not self.summary["opponents"].get(team["unique_name"]):
            return False
        s_my_team = self.summary["opponents"][team["unique_name"]]["team"]["my_id"]
        s_opponent_team = self.summary["opponents"][team["unique_name"]]["team"]["opponent_id"]
        for player in team["my_id"]:
            if player not in s_my_team:
                return False
        for player in team["opponent_id"]:
            if player not in s_opponent_team:
                return False
        return True

    def prepare_team(self, match, my, opponent):
        """
        Przygotowuje dane zespołu na podstawie danych meczu.
        :param match: Słownik z danymi meczu.
        :param my: Tuple z kluczami graczy w mojej drużynie.
        :param opponent: Tuple z kluczami graczy w drużynie przeciwnika.
        :return: Słownik z danymi zespołu.
        """
        team = {
            "my": [],
            "my_id": [],
            "opponent": [],
            "opponent_id": [],
        }
        for player in my:  
            team["my"].append(match[player])
            team["my_id"].append(match[f'{player}_id'])

        for player in opponent:
            team["opponent"].append(match[player])
            team["opponent_id"].append(match[f'{player}_id'])
        
        team["my_id"].sort()
        team["opponent_id"].sort()
        team["unique_name"] = ""
        for player_id in team["my_id"]:
            team["unique_name"] += str(player_id)
        for player_id in team["opponent_id"]:
            team["unique_name"] += str(player_id)
        return team    
    
    def sort_opponets(self, **kwargs):
        """
        Sortuje przeciwników na podstawie różnych kryteriów.
        """
        if kwargs.get("sort"):
            sort_key = kwargs["sort"]
            reverse = True  # domyślnie malejąco
            if sort_key == "win_gem":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["gem"]["win"],
                    reverse=reverse
                ))
            elif sort_key == "win_gem_per":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["gem"]["per"],
                    reverse=reverse
                ))
            elif sort_key == "win_set":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["set"]["win"],
                    reverse=reverse
                ))
            elif sort_key == "win_set_per":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["set"]["per"],
                    reverse=reverse
                ))
            elif sort_key == "win_match":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["match"]["win"],
                    reverse=reverse
                ))
            elif sort_key == "win_match_per":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["match"]["per"],
                    reverse=reverse
                ))
            elif sort_key == "all_match":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["match"]["all"],
                    reverse=reverse
                ))
            elif sort_key == "all_gem":
                self.summary["opponents"] = dict(sorted(
                    self.summary["opponents"].items(),
                    key=lambda item: item[1]["stats"]["gem"]["all"],
                    reverse=reverse
                ))


def decode_match_month(match):
    """
    Dekoduje numer miesiąca na jego nazwę.
    :param match: Słownik z danymi meczu.
    :return: Nazwa miesiąca.
    """
    months = prepare_months()
    if match.get("match_date"):
        return months[match["match_date"].month - 1]


def prepare_filters(request):
    """Przygotowuje filtry na podstawie parametrów zapytania."""
    match_double = request.GET.get("match_double")
    opponent_id = request.GET.get("opponent_id")
    date_range = request.GET.get("date_range")
    partner_id = request.GET.get("partner_id")
    opponent_partner_id = request.GET.get("opponent_partner_id")

    # Przekazanie filtrów do klasy Results
    filters = {}
    if match_double in ['1', 'true']:
        filters["match_double"] = 1
    else:
        filters["match_double"] = 0

    if opponent_id:
        filters["friend_id"] = int(opponent_id)
    if partner_id:
        filters["partner_id"] = int(partner_id)
    if opponent_partner_id:
        filters["opponent_partner_id"] = int(opponent_partner_id)

    if date_range == "all":
        filters["last_days"] = 0  # bez ograniczenia
    elif date_range == "last_15":
        filters["limit_matches"] = 15
    elif date_range: # Obsługa lat
        filters["last_days"] = date_range
    else: # Domyślny filtr
        filters["limit_matches"] = 15
    return filters


def prepare_years(request, user=None):
    """
    Przygotowuje listę lat, w których użytkownik (lub zalogowany) grał mecze.
    """
    from django.db.models import Q
    target_user = user or request.user
    user_id = target_user.id
    # Pobierz daty meczów, w których brał udział użytkownik
    match_years = Match.objects.filter(
        Q(p1_id=user_id) | Q(p2_id=user_id) | Q(p3_id=user_id) | Q(p4_id=user_id)
    ).values_list('match_date__year', flat=True).distinct().order_by('-match_date__year')
    
    # Pobierz daty meczów turniejowych, w których brał udział użytkownik
    from apps.tournaments.models import TournamentsMatch
    tournament_match_years = TournamentsMatch.objects.filter(
        Q(participant1__user_id=user_id) | Q(participant2__user_id=user_id) | Q(participant3__user_id=user_id) | Q(participant4__user_id=user_id),
        status=TournamentsMatch.Status.COMPLETED.value
    ).values_list('scheduled_time__year', flat=True).distinct().order_by('-scheduled_time__year')

    # Połącz obie listy lat, usuń duplikaty i posortuj malejąco
    combined_years = set(match_years).union(tournament_match_years)
    # Usuń None z listy i posortuj
    all_years = sorted([year for year in combined_years if year is not None], reverse=True)

    return [str(year) for year in all_years]



def prepare_months():
    """Przygotowuje listę nazw miesięcy."""
    return ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]


def get_played_with_players(request, user=None):
    """
    Zwraca listę graczy, z którymi użytkownik (lub zalogowany) rozegrał mecze.
    """
    target_user = user or request.user
    user_matches = Match.objects.filter(
        models.Q(p1=target_user) | models.Q(p2=target_user) |
        models.Q(p3=target_user) | models.Q(p4=target_user)
    )


    from apps.tournaments.models import TournamentsMatch, Tournament
    user_participant_ids = list(target_user.tournament_participations.values_list('id', flat=True))
    user_tournament_matches = TournamentsMatch.objects.filter(
        models.Q(participant1_id__in=user_participant_ids) |
        models.Q(participant2_id__in=user_participant_ids) |
        models.Q(participant3_id__in=user_participant_ids) |
        models.Q(participant4_id__in=user_participant_ids),
        status=TournamentsMatch.Status.COMPLETED.value,
    )
    user_tournament_matches = user_tournament_matches.exclude(tournament__tournament_type=Tournament.TournamentType.AMERICANO.value)

    player_ids = set()
    # Przetwarzanie meczów towarzyskich
    for match in user_matches.values('p1_id', 'p2_id', 'p3_id', 'p4_id'):
        player_ids.add(match['p1_id'])
        player_ids.add(match['p2_id'])
        if match.get('p3_id'): player_ids.add(match['p3_id'])
        if match.get('p4_id'): player_ids.add(match['p4_id'])

    # Przetwarzanie meczów turniejowych
    for match in user_tournament_matches.values('participant1__user_id', 'participant2__user_id', 'participant3__user_id', 'participant4__user_id'):
        if match.get('participant1__user_id'): player_ids.add(match['participant1__user_id'])
        if match.get('participant2__user_id'): player_ids.add(match['participant2__user_id'])
        if match.get('participant3__user_id'): player_ids.add(match['participant3__user_id'])
        if match.get('participant4__user_id'): player_ids.add(match['participant4__user_id'])

    player_ids.discard(target_user.id)
    return User.objects.filter(pk__in=player_ids).order_by('first_name', 'last_name')


def get_doubles_partners(request, user=None):
    """
    Zwraca listę graczy, z którymi użytkownik grał w debla jako partner.
    """
    target_user = user or request.user
    user_id = target_user.id
    partner_ids = set()

    # Zapytania o partnerów w zależności od pozycji użytkownika w drużynie
    queries = [
        models.Q(p1_id=user_id),
        models.Q(p3_id=user_id),
        models.Q(p2_id=user_id),
        models.Q(p4_id=user_id),
    ]

    from apps.tournaments.models import TournamentsMatch
    user_participant_ids = list(target_user.tournament_participations.values_list('id', flat=True))
    tournament_queries = [
        models.Q(participant1_id__in=user_participant_ids),
        models.Q(participant2_id__in=user_participant_ids),
        models.Q(participant3_id__in=user_participant_ids),
        models.Q(participant4_id__in=user_participant_ids),
    ]

    for query in queries:
        matches = Match.objects.filter(models.Q(match_double=True) & query)
        for match in matches.values('p1_id', 'p2_id', 'p3_id', 'p4_id'):
            if match['p1_id'] == user_id and match['p3_id']: partner_ids.add(match['p3_id'])
            if match['p3_id'] == user_id and match['p1_id']: partner_ids.add(match['p1_id'])
            if match['p2_id'] == user_id and match['p4_id']: partner_ids.add(match['p4_id'])
            if match['p4_id'] == user_id and match['p2_id']: partner_ids.add(match['p2_id'])

    # Logika dla meczów turniejowych - uproszczona, ponieważ `tournament_queries` jest zbyt szerokie
    # Zakładamy standardowe parowanie: p1 z p3, p2 z p4
    from apps.tournaments.models import Tournament
    tournament_matches_as_p1_p3 = TournamentsMatch.objects.filter(models.Q(participant1_id__in=user_participant_ids) | models.Q(participant3_id__in=user_participant_ids), tournament__match_format=Tournament.MatchFormat.DOUBLES.value, status=TournamentsMatch.Status.COMPLETED.value).exclude(tournament__tournament_type=Tournament.TournamentType.AMERICANO.value)
    for match in tournament_matches_as_p1_p3.values('participant1__user_id', 'participant3__user_id'):
        if match['participant1__user_id'] == user_id and match.get('participant3__user_id'): partner_ids.add(match['participant3__user_id'])
        if match['participant3__user_id'] == user_id and match.get('participant1__user_id'): partner_ids.add(match['participant1__user_id'])

    tournament_matches_as_p2_p4 = TournamentsMatch.objects.filter(models.Q(participant2_id__in=user_participant_ids) | models.Q(participant4_id__in=user_participant_ids), tournament__match_format=Tournament.MatchFormat.DOUBLES.value, status=TournamentsMatch.Status.COMPLETED.value).exclude(tournament__tournament_type=Tournament.TournamentType.AMERICANO.value)
    for match in tournament_matches_as_p2_p4.values('participant2__user_id', 'participant4__user_id'):
        if match['participant2__user_id'] == user_id and match.get('participant4__user_id'): partner_ids.add(match['participant4__user_id'])
        if match['participant4__user_id'] == user_id and match.get('participant2__user_id'): partner_ids.add(match['participant2__user_id'])

    return User.objects.filter(pk__in=partner_ids).order_by('first_name', 'last_name')


def get_doubles_opponents(request, user=None):
    """
    Zwraca listę graczy, przeciwko którym użytkownik grał w debla.
    """
    target_user = user or request.user
    user_id = target_user.id
    opponent_ids = set()

    # Mecze, w których użytkownik jest w drużynie 1 (p1 lub p3)
    team1_matches = Match.objects.filter(match_double=True).filter(models.Q(p1_id=user_id) | models.Q(p3_id=user_id))
    for match in team1_matches.values('p2_id', 'p4_id'):
        opponent_ids.add(match['p2_id'])
        if match['p4_id']: opponent_ids.add(match['p4_id'])

    from apps.tournaments.models import TournamentsMatch
    from apps.tournaments.models import Tournament
    user_participant_ids = list(target_user.tournament_participations.values_list('id', flat=True))
    tournament_team1_matches = TournamentsMatch.objects.filter(models.Q(participant1_id__in=user_participant_ids) | models.Q(participant3_id__in=user_participant_ids), tournament__match_format=Tournament.MatchFormat.DOUBLES.value, status=TournamentsMatch.Status.COMPLETED.value).exclude(tournament__tournament_type=Tournament.TournamentType.AMERICANO.value)
    for match in tournament_team1_matches.values('participant2__user_id', 'participant4__user_id'):
        if match.get('participant2__user_id'): opponent_ids.add(match['participant2__user_id'])
        if match.get('participant4__user_id'): opponent_ids.add(match['participant4__user_id'])

    # Mecze, w których użytkownik jest w drużynie 2 (p2 lub p4)
    team2_matches = Match.objects.filter(match_double=True).filter(models.Q(p2_id=user_id) | models.Q(p4_id=user_id))
    for match in team2_matches.values('p1_id', 'p3_id'):
        opponent_ids.add(match['p1_id'])
        if match['p3_id']: opponent_ids.add(match['p3_id'])

    tournament_team2_matches = TournamentsMatch.objects.filter(models.Q(participant2_id__in=user_participant_ids) | models.Q(participant4_id__in=user_participant_ids), tournament__match_format=Tournament.MatchFormat.DOUBLES.value, status=TournamentsMatch.Status.COMPLETED.value).exclude(tournament__tournament_type=Tournament.TournamentType.AMERICANO.value)
    for match in tournament_team2_matches.values('participant1__user_id', 'participant3__user_id'):
        if match.get('participant1__user_id'): opponent_ids.add(match['participant1__user_id'])
        if match.get('participant3__user_id'): opponent_ids.add(match['participant3__user_id'])

    return User.objects.filter(pk__in=opponent_ids).order_by('first_name', 'last_name')


def get_all_players_with_matches():
    """
    Zwraca listę wszystkich zawodników, którzy rozegrali przynajmniej 1 spotkanie (towarzyskie lub turniejowe).
    """
    from django.db.models import Q
    from apps.tournaments.models import TournamentsMatch

    # IDs from Friendly Matches
    friendly_player_ids = set()
    matches = Match.objects.all().values('p1_id', 'p2_id', 'p3_id', 'p4_id')
    for m in matches:
        if m['p1_id']: friendly_player_ids.add(m['p1_id'])
        if m['p2_id']: friendly_player_ids.add(m['p2_id'])
        if m['p3_id']: friendly_player_ids.add(m['p3_id'])
        if m['p4_id']: friendly_player_ids.add(m['p4_id'])

    # IDs from Tournament Matches (Completed)
    tournament_matches = TournamentsMatch.objects.filter(status=TournamentsMatch.Status.COMPLETED).values(
        'participant1__user_id', 'participant2__user_id', 'participant3__user_id', 'participant4__user_id'
    )
    
    tournament_player_ids = set()
    for m in tournament_matches:
        if m['participant1__user_id']: tournament_player_ids.add(m['participant1__user_id'])
        if m['participant2__user_id']: tournament_player_ids.add(m['participant2__user_id'])
        if m['participant3__user_id']: tournament_player_ids.add(m['participant3__user_id'])
        if m['participant4__user_id']: tournament_player_ids.add(m['participant4__user_id'])

    all_ids = friendly_player_ids.union(tournament_player_ids)
    
    return User.objects.filter(id__in=all_ids).order_by('first_name', 'last_name', 'username')