import random
from types import SimpleNamespace
from django.db.models import Count, Q, F, Max
from django.utils import timezone
from .models import TournamentsMatch, Tournament, Participant
import math

PREDEFINED_SEEDING_ORDERS = {
    2: [1, 2],
    4: [1, 4, 3, 2],
    8: [1, 8, 5, 4, 3, 6, 7, 2],
    16: [1, 16, 9, 8, 5, 12, 13, 4, 3, 14, 11, 6, 7, 10, 15, 2],
    32: [1, 32, 17, 16, 9, 24, 25, 8, 5, 28, 21, 12, 13, 20, 29, 4, 3, 30, 19, 14, 11, 22, 27, 6, 7, 26, 23, 10, 15, 18, 31, 2]
}

def _generate_seed_to_slot_map(bracket_size):
    """
    Generuje mapowanie numeru rozstawienia (1-indeksowany) na indeks slotu w drabince (0-indeksowany).
    Kopia z views.py aby uniknąć importów cyklicznych.
    """
    if bracket_size == 0:
        return {}
    if bracket_size == 1:
        return {1: 0}

    if bracket_size in PREDEFINED_SEEDING_ORDERS:
        slots = PREDEFINED_SEEDING_ORDERS[bracket_size]
    else:
        slots = [1, 2]
        while len(slots) < bracket_size:
            new_slots = []
            for seed in slots:
                new_slots.append(seed)
                new_slots.append(len(slots) * 2 + 1 - seed)
            slots = new_slots
    
    return {seed: index for index, seed in enumerate(slots)}


def generate_swiss_playoffs(tournament, qualified_players, start_round):
    """
    Generuje drabinkę pucharową (Single Elimination) dla zakwalifikowanych graczy.
    """
    num_participants = len(qualified_players)
    if num_participants < 2:
        return 0, "Za mało zakwalifikowanych graczy do fazy pucharowej."

    # 1. Sortowanie graczy zostało wykonane wcześniej (przekazana lista jest już posortowana),
    # ale dla pewności przypiszmy im tymczasowe seedy 1..N
    # qualified_players[0] ma seed 1, qualified_players[1] ma seed 2 itd.
    
    bracket_size = 2**math.ceil(math.log2(num_participants))
    num_byes = bracket_size - num_participants
    
    final_bracket_slots = [None] * bracket_size
    seed_to_slot_map = _generate_seed_to_slot_map(bracket_size)
    
    # 2. Rozmieszczenie graczy w slotach
    for i, player_data in enumerate(qualified_players):
        seed_num = i + 1
        slot_idx = seed_to_slot_map.get(seed_num)
        if slot_idx is not None and slot_idx < bracket_size:
            final_bracket_slots[slot_idx] = player_data['participant']
            
    # 3. Generowanie meczów
    matches_to_create = []
    match_index = 1 # Indeks meczu w drabince pucharowej (można resetować lub kontynuować)
    
    # Dla odróżnienia meczów playoff od swiss, używamy round_number > swiss_rounds.
    # W Single Elimination runda 1 ma N/2 meczów.
    
    for i in range(0, bracket_size, 2):
        p1_slot = final_bracket_slots[i]
        p2_slot = final_bracket_slots[i+1]

        if p1_slot is None:
            # p2 ma wolny los
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p2_slot, participant2=None,
                round_number=start_round, match_index=match_index, 
                status=TournamentsMatch.Status.COMPLETED.value, winner=p2_slot
            ))
        elif p2_slot is None:
            # p1 ma wolny los
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p1_slot, participant2=None,
                round_number=start_round, match_index=match_index, 
                status=TournamentsMatch.Status.COMPLETED.value, winner=p1_slot
            ))
        else:
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p1_slot, participant2=p2_slot,
                round_number=start_round, match_index=match_index, 
                status=TournamentsMatch.Status.WAITING.value
            ))
        match_index += 1
        
    created = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created), f"Faza grupowa zakończona! Wygenerowano drabinkę pucharową ({len(created)} meczów) dla {num_participants} graczy."

def generate_swiss_matches_initial(tournament, participants_qs, config):
    """
    Generuje mecze pierwszej rundy dla systemu szwajcarskiego.
    """
    participants = list(participants_qs)
    num_participants = len(participants)
    
    if num_participants < 4:
        return 0, "Za mało uczestników (wymagane co najmniej 4 dla sensownego systemu szwajcarskiego)."
    
    if num_participants % 2 != 0:
        # Obsługa nieparzystej liczby - dodanie BYE
        # W tym systemie BYE to wirtualny uczestnik lub po prostu wolny los. 
        # Najprościej: jeden z graczy dostaje punkty za darmo.
        # W 1. rundzie zazwyczaj najwyżej rozstawiony (lub losowo) dostaje bye? 
        # Nie, zazwyczaj najniżej.
        pass # Na razie załóżmy parzystą liczbę, dodanie logiki BYE wymagałoby zmian w Participant

    TournamentsMatch.objects.filter(tournament=tournament).delete()

    matches_to_create = []
    
    if config.initial_seeding == 'SEEDING':
        # Sortowanie po seedzie (zakładamy, że niższy seed = lepszy)
        # Traktujemy brak seeda jako wysoki numer
        participants.sort(key=lambda p: (p.seed_number is None, p.seed_number))
        
        # Parowanie: 1 vs N/2+1, 2 vs N/2+2 itd. (Standardowe szwajcarskie)
        # Czy może 1 vs N (najlepszy z najgorszym)?
        # W opisie użytkownika: "1 z 16, 2 z 15". To jest pairing "Fold" (or Slaughter).
        
        # Sprawdź, czy liczba uczestników jest potęgą 2 (dla poprawnego odwzorowania drabinki)
        is_power_of_two = (num_participants & (num_participants - 1) == 0) and num_participants != 0
        
        if is_power_of_two:
            # Algorytm drabinkowy - identyczny układ par jak w Single Elimination
            seed_to_slot_map = _generate_seed_to_slot_map(num_participants)
            slots = [None] * num_participants
            
            # Przypisz graczy do slotów bazując na ich pozycji na liście (1. gracz = Seed 1)
            for i, participant in enumerate(participants):
                seed_num = i + 1
                slot_idx = seed_to_slot_map.get(seed_num)
                if slot_idx is not None and slot_idx < num_participants:
                    slots[slot_idx] = participant
            
            # Generuj mecze parując sąsiednie sloty
            for i in range(0, num_participants, 2):
                p1 = slots[i]
                p2 = slots[i+1]
                
                matches_to_create.append(TournamentsMatch(
                    tournament=tournament,
                    participant1=p1,
                    participant2=p2,
                    round_number=1,
                    match_index=(i // 2) + 1,
                    status=TournamentsMatch.Status.WAITING.value
                ))
        else:
            # Standardowe parowanie High-Low (dla liczb niebędących potęgą 2)
            # 1 vs N, 2 vs N-1...
            half = num_participants // 2
            for i in range(half):
                p1 = participants[i]
                p2 = participants[num_participants - 1 - i]
                
                matches_to_create.append(TournamentsMatch(
                    tournament=tournament,
                    participant1=p1,
                    participant2=p2,
                    round_number=1,
                    match_index=i+1,
                    status=TournamentsMatch.Status.WAITING.value
                ))
            
    else:
        # Losowe
        random.shuffle(participants)
        for i in range(0, num_participants, 2):
            if i + 1 < num_participants:
                matches_to_create.append(TournamentsMatch(
                    tournament=tournament,
                    participant1=participants[i],
                    participant2=participants[i+1],
                    round_number=1,
                    match_index=(i//2)+1,
                    status=TournamentsMatch.Status.WAITING.value
                ))

    created = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created), f"Wygenerowano {len(created)} meczów 1. rundy."


def get_participant_standings_swiss(tournament):
    """
    Oblicza bilans każdego gracza: (wygrane, przegrane).
    """
    participants = tournament.participants.filter(status__in=['ACT', 'REG'])
    standings = {p.id: {'participant': p, 'wins': 0, 'losses': 0, 'played_opponents': set()} for p in participants}
    
    matches = tournament.matches.filter(status=TournamentsMatch.Status.COMPLETED.value)
    
    for match in matches:
        if match.winner:
            w = match.winner_id
            l = match.participant1_id if match.participant1_id != w else match.participant2_id
            
            if w in standings:
                standings[w]['wins'] += 1
                standings[w]['played_opponents'].add(l)
            if l in standings:
                standings[l]['losses'] += 1
                standings[l]['played_opponents'].add(w)
                
    return standings


def generate_next_swiss_round(tournament, config):
    """
    Generuje pary dla kolejnej rundy w systemie szwajcarskim.
    Zasady:
    1. Gracze grupowani wg bilansu wygranych (Score Groups).
    2. Wewnątrz grupy próba parowania wg schematu drabinkowego (jeśli możliwe i brak konfliktów).
    3. Fallback do parowania High-Low (z unikaniem powtórzeń).
    4. Obsługa 'spadkowiczów' (floaters) do niższych grup.
    """
    last_round = tournament.matches.aggregate(Max('round_number'))['round_number__max'] or 0
    next_round = last_round + 1

    standings = get_participant_standings_swiss(tournament)
    
    active_players = []     # Gracze nadal w grze (swiss stage)
    qualified_players = []  # Gracze, którzy awansowali (do playoff)
    
    # Kwalifikacja graczy
    for pid, data in standings.items():
        if data['wins'] >= config.wins_to_qualify:
            qualified_players.append(data)
        elif data['losses'] >= config.losses_to_eliminate:
            pass # Odpadli
        else:
            active_players.append(data)
            
    # SPRAWDZENIE LIMITU RUND SWISS
    if next_round > config.number_of_rounds:
        active_players = [] # Wymuś koniec fazy grupowej
            
    # START PLAYOFF LUB KONIEC
    if not active_players:
        if last_round > config.number_of_rounds: 
            return 0, "Play-offy już trwają lub zakończone."
            
        # Generowanie Playoff
        qualified_players.sort(
            key=lambda x: (
                x['wins'] - x['losses'], 
                -(x['participant'].seed_number if x['participant'].seed_number is not None else 9999)
            ), 
            reverse=True
        )
        return generate_swiss_playoffs(tournament, qualified_players, next_round)
            
    # GRUPOWANIE WG WYNIKÓW (WINS)
    # Tworzymy słownik {score: [players...]}
    score_groups = {}
    for p_data in active_players:
        w = p_data['wins']
        if w not in score_groups:
            score_groups[w] = []
        score_groups[w].append(p_data)
        
    scores_sorted = sorted(score_groups.keys(), reverse=True) # np. [2, 1, 0]
    
    matches_to_create = []
    floaters = [] # Gracze, którzy spadli z wyższej grupy
    
    current_match_index = 1
    
    for score in scores_sorted:
        group = score_groups[score]
        
        # Dodaj spadkowiczów z wyższej grupy na początek (żeby mieli priorytet lub byli traktowani równo)
        # Zwyczajowo floaters grają z najsłabszymi z grupy lub wg seeda.
        # Dodajemy ich do puli grupy.
        group.extend(floaters)
        floaters = []
        
        # Sortowanie grupy wg seeda (dla determinizmu i logiki drabinkowej)
        # seed 1 (najlepszy) na początku
        group.sort(key=lambda x: (x['participant'].seed_number if x['participant'].seed_number is not None else 9999))
        
        # Jeśli liczba graczy nieparzysta, przenieś najgorszego (ostatniego) do floaters
        # Chyba że to ostatnia grupa (najniższa), wtedy ten gracz dostanie BYE
        if len(group) % 2 != 0:
            if score == scores_sorted[-1]:
                # Ostatnia grupa - nieparzysta liczba ogółem - BYE
                bye_player = group.pop() # Najgorszy seed dostaje BYE
                matches_to_create.append(TournamentsMatch(
                    tournament=tournament,
                    participant1=bye_player['participant'],
                    participant2=None,
                    winner=bye_player['participant'],
                    round_number=next_round,
                    match_index=current_match_index,
                    status=TournamentsMatch.Status.COMPLETED.value
                ))
                current_match_index += 1
            else:
                # Przenieś do niższej grupy
                floater = group.pop()
                floaters.append(floater)
        
        # Jeśli grupa pusta (bo wszyscy spadli), idź dalej
        if not group:
            continue
            
        # PRÓBA PAROWANIA DRABINKOWEGO (Bracket)
        # Tylko jeśli liczba graczy w grupie to potęga 2 (np. 8, 4) I włączone 'SEEDING'
        # Oraz brak konfliktów historii.
        is_power_of_two = (len(group) & (len(group) - 1) == 0)
        bracket_success = False
        
        if is_power_of_two and config.initial_seeding == 'SEEDING':
            # Symulacja parowania
            seed_to_slot = _generate_seed_to_slot_map(len(group))
            temp_slots = [None] * len(group)
            
            # Gracz z indexem 0 w grupie traktowany jako 'Seed 1' w tej małej drabince
            for i, p_data in enumerate(group):
                local_seed = i + 1
                slot_idx = seed_to_slot.get(local_seed)
                if slot_idx is not None:
                    temp_slots[slot_idx] = p_data
            
            # Sprawdź pary
            temp_pairs = []
            conflict_found = False
            for k in range(0, len(group), 2):
                p1_d = temp_slots[k]
                p2_d = temp_slots[k+1]
                
                # Walidacja historii
                if p2_d['participant'].id in p1_d['played_opponents']:
                    conflict_found = True
                    break
                temp_pairs.append((p1_d, p2_d))
            
            if not conflict_found:
                # Zastosuj pary drabinkowe
                for p1_d, p2_d in temp_pairs:
                    matches_to_create.append(TournamentsMatch(
                        tournament=tournament,
                        participant1=p1_d['participant'],
                        participant2=p2_d['participant'],
                        round_number=next_round,
                        match_index=current_match_index,
                        status=TournamentsMatch.Status.WAITING.value
                    ))
                    current_match_index += 1
                bracket_success = True
        
        if not bracket_success:
            # FALLBACK: Algorytm High-Low Greedy (Najlepszy z Najgorszym Dostępnym)
            # group jest posortowana po seedzie (High -> Low)
            
            while len(group) >= 2:
                p1_data = group.pop(0) # Najlepszy dostępny (High)
                
                opponent_idx = -1
                # Szukamy od końca (Low) pierwszego pasującego
                for i in range(len(group) - 1, -1, -1):
                    p2_candidate = group[i]
                    if p2_candidate['participant'].id not in p1_data['played_opponents']:
                        opponent_idx = i
                        break
                
                if opponent_idx != -1:
                    p2_data = group.pop(opponent_idx)
                else:
                    # Brak pasującego rywala (wszyscy grali).
                    # W desperacji bierzemy najgorszego (Low), godząc się na rewanż
                    # (Lepszy rewanż niż brak gry, w amatorskim turnieju)
                    p2_data = group.pop(-1)
                
                matches_to_create.append(TournamentsMatch(
                    tournament=tournament,
                    participant1=p1_data['participant'],
                    participant2=p2_data['participant'],
                    round_number=next_round,
                    match_index=current_match_index,
                    status=TournamentsMatch.Status.WAITING.value
                ))
                current_match_index += 1
                
    # Zapisz mecze
    if matches_to_create:
        TournamentsMatch.objects.bulk_create(matches_to_create)
        return len(matches_to_create), f"Wygenerowano rundę {next_round} ({len(matches_to_create)} meczów)."
    else:
         # Sytuacja rzadka: brak meczów (np. sami floaterzy bez par?) 
         # Powinno być obsłużone w logice floaters.
         return 0, "Brak par do wygenerowania (koniec turnieju?)."
