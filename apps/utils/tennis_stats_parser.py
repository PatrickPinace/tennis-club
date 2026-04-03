from typing import Dict, Any, List, Optional
from django.apps import apps
import re
from collections import OrderedDict
from django.db.models import Model

class TennisStatsParser:
    """
    Parsuje obiekt modelu TennisData na ustrukturyzowany słownik
    gotowy do prezentacji w szablonie.
    """

    def __init__(self, tennis_data_instance: Optional[Any]):
        """
        Inicjalizuje parser z instancją modelu TennisData.
        Używamy 'Any' dla uniknięcia cyklicznego importu, ale oczekujemy modelu TennisData.

        :param tennis_data_instance: Instancja modelu activities.TennisData.
        :param match_instance: Opcjonalna instancja modelu matches.Match.
        """
        if tennis_data_instance is None:
            raise ValueError("Instancja TennisData nie może być None.")

        # Sprawdzenie, czy przekazany obiekt jest instancją modelu TennisData
        TennisData = apps.get_model('activities', 'TennisData')
        if not isinstance(tennis_data_instance, TennisData):
            raise TypeError(f"Oczekiwano instancji modelu TennisData, otrzymano {type(tennis_data_instance).__name__}")

        self.tennis_data = tennis_data_instance

    def get_parsed_stats(self, owner_position: int) -> List[Dict[str, Any]]:
        """
        Zwraca listę statystyk dla określonej pozycji gracza.

        :return: Lista słowników reprezentujących poszczególne statystyki.
        """
        if not self.tennis_data:
            return []

        # Definicje statystyk: klucz to pole w modelu TennisData
        # Używamy OrderedDict, aby zachować kolejność wyświetlania statystyk
        stats_definitions = OrderedDict([
            ('points', {'label': 'Zdobyte punkty', 'unit': 'pkt'}),
            ('games', {'label': 'Wygrane gemy', 'unit': 'gemy'}),
            ('aces', {'label': 'Asy serwisowe', 'unit': ''}),
            ('double_faults', {'label': 'Podwójne błędy', 'unit': ''}),
            ('first_serve_percentage', {'label': 'Skuteczność 1. serwisu', 'unit': '%'}),
            ('win_percentage_on_first_serve', {'label': 'Wygrane po 1. serwisie', 'unit': '%'}),
            ('win_percentage_on_second_serve', {'label': 'Wygrane po 2. serwisie', 'unit': '%'}),
            ('serving_points', {'label': 'Punkty zdobyte przy serwisie', 'unit': 'pkt'}),
            ('receiving_points', {'label': 'Punkty zdobyte przy odbiorze', 'unit': 'pkt'}),
            ('winners', {'label': 'Uderzenia wygrywające', 'unit': ''}),
            ('unforced_errors', {'label': 'Niewymuszone błędy', 'unit': ''}),
            ('breakpoints', {'label': 'Wykorzystane break pointy', 'unit': ''}),
        ])

        parsed_stats = []

        for field_name, definition in stats_definitions.items():
            original_value = getattr(self.tennis_data, field_name, None)
            value = original_value

            # Specjalna obsługa dla pola 'points', aby wyświetlić 'zdobyte (suma) %'
            if field_name == 'points' and owner_position and isinstance(value, str) and ':' in value:
                parts = value.split(':')
                if len(parts) == 2:
                    try:
                        p1_points = int(parts[0].strip())
                        p2_points = int(parts[1].strip())
                        total_points = p1_points + p2_points

                        player_points = p1_points if owner_position == 1 else p2_points

                        if total_points > 0:
                            percentage = round((player_points / total_points) * 100)
                            display_value = f"{player_points} / {total_points} ({percentage}%)"
                        else:
                            display_value = f"{player_points} / 0 (0%)"

                        parsed_stats.append({
                            'label': definition['label'],
                            'value': display_value,
                        })
                        continue  # Przechodzimy do następnej statystyki
                    except (ValueError, IndexError):
                        # W razie błędu parsowania, wracamy do domyślnej logiki
                        value = self._parse_dual_value(value, owner_position)

            # Jeśli mamy właściciela i wartość jest w formacie "X:Y", parsujemy ją
            elif owner_position and isinstance(value, str) and ':' in value:
                value = self._parse_dual_value(value, owner_position)

            # Pomijamy statystyki, które nie mają wartości (są None lub pustym stringiem)
            if value is None or value == '':
                continue

            display_value = f"{value}{definition['unit']}" if definition['unit'] else str(value)

            parsed_stats.append({
                'label': definition['label'],
                'value': display_value,
            })

        return parsed_stats

    @staticmethod
    def _parse_dual_value(value: str, owner_position: int) -> Optional[str]:
        """
        Parsuje wartość w formacie 'value1:value2' i zwraca odpowiednią część.
        :param value: Wartość do sparsowania (np. "78:60").
        :param owner_position: Pozycja właściciela (1 lub 2).
        :return: Wybrana wartość jako string lub None, jeśli format jest nieprawidłowy.
        """
        parts = value.split(':')
        if len(parts) == 2:
            try:
                if owner_position == 1:
                    return parts[0].strip()
                elif owner_position == 2:
                    return parts[1].strip()
            except (ValueError, IndexError):
                return None
        return None

    @staticmethod
    def _adjust_games_for_tiebreaks(games_str: Optional[str], score_str: Optional[str]) -> Optional[str]:
        """
        Analizuje pole 'score' w poszukiwaniu tie-breaków i dodaje 1 gem dla zwycięzcy każdego z nich.
        Przykład: score '6/6(10:8) 6/1' i games '12:7' -> zwycięzca tie-breaka (lewa strona) dostaje gema -> '13:7'.
        """
        if not games_str or not score_str or ':' not in games_str:
            return games_str

        try:
            left_games, right_games = map(int, games_str.split(':'))
        except (ValueError, TypeError):
            return games_str  # Zwróć oryginał, jeśli format jest nieprawidłowy

        # Znajdź wszystkie wyniki tie-breaków w formacie (X:Y)
        tie_breaks = re.findall(r'\((\d+):(\d+)\)', score_str)

        for tb_left, tb_right in tie_breaks:
            if int(tb_left) == 0 and int(tb_right) == 0:
                continue
            if int(tb_left) > int(tb_right):
                left_games += 1
            else:
                right_games += 1

        return f"{left_games}:{right_games}"

    @staticmethod
    def _format_dual_stat(value_str: Optional[str], player_map: Dict[Any, int], activity_owner_team: int, owner_stats_side: str) -> Optional[Dict[Any, str]]:
        """Formatuje statystykę w formacie 'X:Y' na 'X / Suma (Procent%)' dla każdego gracza."""
        if not value_str or ':' not in value_str:
            return None
        
        left_val_str, right_val_str = value_str.split(':')
        left_val = int(left_val_str.strip())
        right_val = int(right_val_str.strip())

        # Ustal, która wartość (lewa/prawa) należy do właściciela aktywności
        owner_val = left_val if owner_stats_side == 'L' else right_val
        opponent_val = right_val if owner_stats_side == 'L' else left_val

        # Przypisz wartości do drużyn na podstawie przynależności właściciela aktywności
        if activity_owner_team == 1:
            p1_val = owner_val
            p2_val = opponent_val
        else: # activity_owner_team == 2
            p1_val = opponent_val
            p2_val = owner_val

        total_val = p1_val + p2_val
        
        result = {}
        for player, position in player_map.items():
            player_val = p1_val if position == 1 else p2_val
            percentage = round((player_val / total_val) * 100) if total_val > 0 else 0
            result[player] = f"{player_val} / {total_val} ({percentage}%)"
        return result

    @staticmethod
    def _format_simple_dual_stat(value_str: Optional[str], player_map: Dict[Any, int], activity_owner_team: int, owner_stats_side: str) -> Optional[Dict[Any, str]]:
        """Formatuje prostą statystykę w formacie 'X:Y' przypisując wartość do każdego gracza."""
        if not value_str or ':' not in value_str:
            return None
        try:
            left_val_str, right_val_str = value_str.split(':')
            left_val = left_val_str.strip()
            right_val = right_val_str.strip()

            # Ustal, która wartość (lewa/prawa) należy do właściciela aktywności
            owner_val = left_val if owner_stats_side == 'L' else right_val
            opponent_val = right_val if owner_stats_side == 'L' else left_val

            # Przypisz wartości do drużyn na podstawie przynależności właściciela aktywności
            if activity_owner_team == 1:
                p1_val = owner_val
                p2_val = opponent_val
            else: # activity_owner_team == 2
                p1_val = opponent_val
                p2_val = owner_val

            result = {}
            for player, position in player_map.items():
                result[player] = p1_val if position == 1 else p2_val
            return result
        except (ValueError, TypeError, IndexError):
            return None

    @staticmethod
    def _format_fraction_dual_stat(value_str: Optional[str], player_map: Dict[Any, int], activity_owner_team: int, owner_stats_side: str) -> Optional[Dict[Any, str]]:
        """Formatuje statystykę w formacie 'X/Y : A/B' na 'X / Y (Procent%)' dla każdego gracza."""
        if not value_str or ':' not in value_str:
            return None

        try:
            left_str, right_str = [s.strip() for s in value_str.split(':')]
            left_won, left_total = [int(p.strip()) for p in left_str.split('/')]
            right_won, right_total = [int(p.strip()) for p in right_str.split('/')]

            # Ustal, które wartości (lewa/prawa) należą do właściciela aktywności
            owner_won, owner_total = (left_won, left_total) if owner_stats_side == 'L' else (right_won, right_total)
            opponent_won, opponent_total = (right_won, right_total) if owner_stats_side == 'L' else (left_won, left_total)

            # Przypisz wartości do drużyn na podstawie przynależności właściciela aktywności
            if activity_owner_team == 1:
                p1_won, p1_total = owner_won, owner_total
                p2_won, p2_total = opponent_won, opponent_total
            else: # activity_owner_team == 2
                p1_won, p1_total = opponent_won, opponent_total
                p2_won, p2_total = owner_won, owner_total

            result = {}
            for player, position in player_map.items():
                won, total = (p1_won, p1_total) if position == 1 else (p2_won, p2_total)
                percentage = round((won / total) * 100) if total > 0 else 0
                result[player] = f"{won} / {total} ({percentage}%)"
            return result
        except (ValueError, TypeError, IndexError):
            # W razie błędu parsowania (np. zły format), zwracamy None
            return None

    @staticmethod
    def _parse_fraction(value: Any) -> tuple[int, int]:
        """
        Parsuje wartość w formacie 'X/Y' na krotkę liczb (X, Y).
        Jeśli format jest inny, zwraca (wartość, 0) lub (0, 0) w przypadku błędu.
        """
        if isinstance(value, str) and '/' in value:
            try:
                parts = value.split('/')
                return int(parts[0].strip()), int(parts[1].strip())
            except (ValueError, TypeError, IndexError):
                return 0, 0
        
        return TennisStatsParser._to_int(value), 0

    @staticmethod
    def _to_int(value: Any) -> int:
        """Bezpiecznie konwertuje wartość na int. Zwraca 0 w przypadku błędu."""
        if value is None:
            return 0
        
        # Jeśli wartość jest stringiem w formacie 'X/Y', weź tylko część 'X'
        if isinstance(value, str) and '/' in value:
            value = value.split('/')[0].strip()

        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    @staticmethod
    def _process_stats(raw_stats: Dict[Any, Dict[str, Any]], player_map: Dict[Any, int], owner_position: int = 0) -> Dict[str, Dict[Any, Any]]:
        """
        Przetwarza zagregowane, surowe dane statystyczne i formatuje je do ostatecznej postaci.
        :param raw_stats: Surowe statystyki zebrane z aktywności.
        :param player_map: Mapowanie obiektów User na pozycje (1 lub 2).
        :param owner_position: Pozycja zalogowanego użytkownika (1 lub 2), 0 jeśli nie jest graczem.
        """
        processed_stats = {}
        stats_definitions = OrderedDict([
            ('games', {'label': 'Wygrane gemy', 'unit': 'gemy'}),
            ('points', {'label': 'Zdobyte punkty', 'unit': 'pkt'}),
            ('aces', {'label': 'Asy serwisowe', 'unit': ''}),
            ('double_faults', {'label': 'Podwójne błędy', 'unit': ''}),
            ('first_serve_percentage', {'label': 'Skuteczność 1. serwisu', 'unit': ''}),
            ('win_percentage_on_first_serve', {'label': 'Wygrane po 1. serwisie', 'unit': ''}),
            ('win_percentage_on_second_serve', {'label': 'Wygrane po 2. serwisie', 'unit': ''}),
            ('serving_points', {'label': 'Punkty zdobyte przy serwisie', 'unit': 'pkt'}),
            ('receiving_points', {'label': 'Punkty zdobyte przy odbiorze', 'unit': ''}),
            ('winners', {'label': 'Uderzenia wygrywające', 'unit': ''}),
            ('unforced_errors', {'label': 'Niewymuszone błędy', 'unit': ''}),
            ('breakpoints', {'label': 'Wykorzystane break pointy', 'unit': ''}),
            ('set_points', {'label': 'Wykorzystane piłki setowe', 'unit': ''}),
            ('match_points', {'label': 'Wykorzystane piłki meczowe', 'unit': ''}),
        ])

        for field_name, definition in stats_definitions.items():
            label = definition['label']
            processed_stats[label] = {}

            # Specjalna obsługa dla statystyk w formacie 'X:Y'
            if field_name in ['points', 'games', 'breakpoints', 'aces', 'double_faults', 'winners', 'unforced_errors', 'first_serve_percentage', 'win_percentage_on_first_serve', 'win_percentage_on_second_serve', 'set_points', 'match_points']:
                try:
                    # Bierzemy dane z pierwszego napotkanego gracza
                    activity_owner = next(iter(raw_stats))
                    value_str = raw_stats[activity_owner].get(field_name)

                    # Sprawdzamy, do której drużyny należy właściciel aktywności i którą stronę statystyk wybrał (L/P)
                    activity_owner_team = player_map.get(activity_owner, 0)
                    owner_stats_side = raw_stats[activity_owner].get('owner_stats_side', 'L') # Domyślnie 'L'
                    
                    # Dodatkowa logika dla gemów - uwzględnienie tie-breaków ze score
                    if field_name == 'games':
                        score_str = raw_stats[activity_owner].get('score')
                        value_str = TennisStatsParser._adjust_games_for_tiebreaks(value_str, score_str)


                    if field_name in ['breakpoints', 'set_points', 'match_points']:
                        formatted_values = TennisStatsParser._format_fraction_dual_stat(value_str, player_map, activity_owner_team, owner_stats_side)
                    elif field_name in ['points', 'games']:
                        formatted_values = TennisStatsParser._format_dual_stat(value_str, player_map, activity_owner_team, owner_stats_side)
                    else: # aces, double_faults, winners, unforced_errors, first_serve_percentage, win_percentage_on_first_serve, win_percentage_on_second_serve
                        formatted_values = TennisStatsParser._format_simple_dual_stat(value_str, player_map, activity_owner_team, owner_stats_side)

                    if formatted_values:
                        processed_stats[label] = formatted_values
                        continue  # Przejdź do następnej statystyki
                except (StopIteration, ValueError, IndexError, TypeError):
                    # W razie błędu, przechodzimy do standardowego przetwarzania
                    pass

            # Specjalna, zaawansowana obsługa dla 'serving_points' i 'receiving_points'
            if field_name in ['serving_points', 'receiving_points']:
                try:
                    # Zbierz graczy dla każdej pozycji (obsługuje singiel i debel)
                    p1_users = [player for player, pos in player_map.items() if pos == 1]
                    p2_users = [player for player, pos in player_map.items() if pos == 2]

                    # Pobierz surowe statystyki dla pierwszego gracza z każdej drużyny (zakładamy, że mają te same dane)
                    p1_stats = raw_stats.get(p1_users[0], {}) if p1_users else {}
                    p2_stats = raw_stats.get(p2_users[0], {}) if p2_users else {}

                    # Pobieramy wartości, upewniając się, że są to liczby całkowite
                    if p1_stats:
                        p1_serve_won, p1_serve_total = TennisStatsParser._parse_fraction(p1_stats.get('serving_points'))
                        p1_return_won, p1_return_total = TennisStatsParser._parse_fraction(p1_stats.get('receiving_points'))
                        p2_serve_won, p2_serve_total = p1_return_total - p1_return_won,  p1_return_total
                        p2_return_won, p2_return_total = p1_serve_total - p1_serve_won, p1_serve_total
                    elif p2_stats:
                        p2_serve_won, p2_serve_total = TennisStatsParser._parse_fraction(p2_stats.get('serving_points'))
                        p2_return_won, p2_return_total = TennisStatsParser._parse_fraction(p2_stats.get('receiving_points'))
                        p1_serve_won, p1_serve_total = p2_return_total - p2_return_won,  p2_return_total
                        p1_return_won, p1_return_total = p2_serve_total - p2_serve_won, p2_serve_total
                    else:
                        p1_serve_won, p1_serve_total = 0, 0
                        p1_return_won, p1_return_total = 0, 0
                        p2_serve_won, p2_serve_total = p1_return_total - p1_return_won, p1_return_total
                        p2_return_won, p2_return_total = p1_serve_total - p1_serve_won, p1_serve_total

                    if field_name == 'serving_points':
                        # Punkty na serwisie P1 (serwujący P1 vs returnujący P2)
                        p1_total_serve_points = p1_serve_total
                        if p1_total_serve_points > 0:
                            percentage = round((p1_serve_won / p1_total_serve_points) * 100) if p1_total_serve_points > 0 else 0
                            for user in p1_users:
                                processed_stats[label][user] = f"{p1_serve_won} / {p1_total_serve_points} ({percentage}%)"

                        # Punkty na serwisie P2 (serwujący P2 vs returnujący P1)
                        p2_total_serve_points = p2_serve_total
                        if p2_total_serve_points > 0:
                            percentage = round((p2_serve_won / p2_total_serve_points) * 100) if p2_total_serve_points > 0 else 0
                            for user in p2_users:
                                processed_stats[label][user] = f"{p2_serve_won} / {p2_total_serve_points} ({percentage}%)"

                    elif field_name == 'receiving_points':
                        # Punkty na returnie P1 (przeciwko serwisowi P2) - te same co p2_total_serve_points
                        total_points_on_p2_serve = p1_return_total
                        if total_points_on_p2_serve > 0:
                            percentage = round((p1_return_won / total_points_on_p2_serve) * 100) if total_points_on_p2_serve > 0 else 0
                            for user in p1_users:
                                processed_stats[label][user] = f"{p1_return_won} / {total_points_on_p2_serve} ({percentage}%)"

                        # Punkty na returnie P2 (przeciwko serwisowi P1) - te same co p1_total_serve_points
                        total_points_on_p1_serve = p2_return_total
                        if total_points_on_p1_serve > 0:
                            percentage = round((p2_return_won / total_points_on_p1_serve) * 100) if total_points_on_p1_serve > 0 else 0
                            for user in p2_users:
                                processed_stats[label][user] = f"{p2_return_won} / {total_points_on_p1_serve} ({percentage}%)"

                    continue
                except (StopIteration, ValueError, TypeError):
                    # W razie błędu (np. braku danych dla jednego z graczy), przechodzimy do standardowego przetwarzania
                    pass

            # Standardowe przetwarzanie dla pozostałych statystyk
            for player, stats in raw_stats.items():
                # Jeśli statystyka nie została przetworzona w specjalnych blokach,
                # po prostu przypisz jej wartość, jeśli istnieje.
                value = stats.get(field_name) 
                if value is not None and value != '' and label not in processed_stats: # Sprawdź, czy statystyka nie została już przetworzona
                    unit = definition.get('unit', '')
                    processed_stats[label][player] = f"{value}{unit}" if unit else str(value)

        return {label: values for label, values in processed_stats.items() if values}

    @staticmethod
    def parse_match_activities(match: Model, owner_position: int = 0) -> Dict[str, Dict[Any, Any]]:
        """
        Przetwarza wszystkie aktywności powiązane z meczem i zwraca statystyki
        pogrupowane według etykiet statystyk, aby ułatwić porównanie.

        :param match: Instancja modelu matches.Match.
        :param owner_position: Pozycja zalogowanego użytkownika (1 lub 2), 0 jeśli nie jest graczem.
        :return: Słownik, gdzie kluczem jest etykieta statystyki (np. 'Zdobyte punkty'), 
                 a wartością jest słownik z graczami i ich wynikami dla tej statystyki.
                 Np. {'Zdobyte punkty': {<User1>: '58', <User2>: '62'}}
        """
        raw_player_stats = {}
        activities_with_stats = match.activities.filter(tennis_data__isnull=False).select_related('user', 'tennis_data')

        # 1. Mapowanie graczy na pozycje
        player_map = {
            match.p1: 1,
            match.p2: 2,
        }
        if match.match_double:
            player_map[match.p3] = 1
            player_map[match.p4] = 2

        # 2. Zebranie surowych danych od wszystkich graczy
        for activity in activities_with_stats:
            user = activity.user
            if user in player_map:
                if user not in raw_player_stats:
                    raw_player_stats[user] = {}
                # Pobieramy wszystkie pola z obiektu tennis_data jako słownik
                for field in activity.tennis_data._meta.get_fields():
                    if not field.is_relation:
                        raw_player_stats[user][field.name] = getattr(activity.tennis_data, field.name)

        # 3. Przetworzenie zebranych danych
        return TennisStatsParser._process_stats(raw_player_stats, player_map, owner_position)