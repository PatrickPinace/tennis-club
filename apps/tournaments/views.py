import math
import random
from django.shortcuts import redirect
from django.db.models import Q, Max, Count, Case, When, Value, IntegerField
from .models import TournamentsMatch

def redirect_to_tournaments(request, *args, **kwargs):
    return redirect('/astro/tournaments')

manage = redirect_to_tournaments
tournament_details_round_robin = redirect_to_tournaments
tournament_details_single_elimination = redirect_to_tournaments
tournament_details_double_elimination = redirect_to_tournaments
tournament_details_ladder = redirect_to_tournaments
tournament_details_swiss = redirect_to_tournaments
tournament_details_americano = redirect_to_tournaments
create_tournament = redirect_to_tournaments
edit_tournament = redirect_to_tournaments
edit_roundrobin_config = redirect_to_tournaments
edit_elimination_config = redirect_to_tournaments
edit_ladder_config = redirect_to_tournaments
edit_swiss_config = redirect_to_tournaments
edit_americano_config = redirect_to_tournaments
list_participants = redirect_to_tournaments
register_participant = redirect_to_tournaments
edit_participant = redirect_to_tournaments
add_team_member = redirect_to_tournaments
remove_team_member = redirect_to_tournaments
request_join = redirect_to_tournaments
approve_participant = redirect_to_tournaments
reject_participant = redirect_to_tournaments
remove_participant = redirect_to_tournaments
revert_to_draft = redirect_to_tournaments
open_registration = redirect_to_tournaments
close_registration = redirect_to_tournaments
start_tournament = redirect_to_tournaments
finish_tournament = redirect_to_tournaments
delete_tournament = redirect_to_tournaments
manage_matches = redirect_to_tournaments
generate_matches = redirect_to_tournaments
create_match = redirect_to_tournaments
edit_match = redirect_to_tournaments
live_match_view = redirect_to_tournaments
start_match = redirect_to_tournaments
delete_match = redirect_to_tournaments
reset_leaderboard_locks = redirect_to_tournaments
create_challenge_match = redirect_to_tournaments
cancel_challenge = redirect_to_tournaments
add_reaction = redirect_to_tournaments

# ── Restored match generation and pairing functions ─────────────────────────

PREDEFINED_SEEDING_ORDERS = {
    2: [1, 2],
    4: [1, 4, 3, 2],
    8: [1, 8, 5, 4, 3, 6, 7, 2],
    16: [1, 16, 9, 8, 5, 12, 13, 4, 3, 14, 11, 6, 7, 10, 15, 2],
    32: [1, 32, 17, 16, 9, 24, 25, 8, 5, 28, 21, 12, 13, 20, 29, 4, 3, 30, 19, 14, 11, 22, 27, 6, 7, 26, 23, 10, 15, 18, 31, 2]
}


def _generate_seed_to_slot_map(bracket_size):
    """
    Generuje mapowanie numeru rozstawienia (1-indeksowany) na indeks slotu w drabince (0-indeksowany)
    zgodnie ze standardowym schematem rozstawiania w profesjonalnym tenisie.
    """
    if bracket_size == 0:
        return {}
    if bracket_size == 1:
        return {1: 0}

    # Krok 1: Spróbuj użyć predefiniowanego schematu rozstawienia
    if bracket_size in PREDEFINED_SEEDING_ORDERS:
        slots = PREDEFINED_SEEDING_ORDERS[bracket_size]
    else:
        # Krok 2: Jeśli schemat nie jest zdefiniowany, oblicz go dynamicznie (fallback)
        # Inicjalizacja: Zaczynamy od drabinki dla 2 graczy
        slots = [1, 2]
        
        # Iteracyjnie podwajamy rozmiar drabinki, aż osiągniemy docelowy rozmiar.
        while len(slots) < bracket_size:
            new_slots = []
            # Dla każdego numeru rozstawienia w obecnej drabince, dodajemy go
            # oraz jego "lustrzane" odbicie w nowej, większej drabince.
            for seed in slots:
                new_slots.append(seed)
                new_slots.append(len(slots) * 2 + 1 - seed)
                slots = new_slots
    
    # Tworzymy słownik mapujący numer rozstawienia na pozycję w drabince
    return {seed: index for index, seed in enumerate(slots)}


def generate_round_robin_matches_initial(tournament, participants_qs):
    """
    Generuje wszystkie mecze dla turnieju "każdy z każdym" (Round Robin)
    i zapisuje je w bazie danych.

    SNG (singiel):
      - Każdy uczestnik gra z każdym innym dokładnie raz.
      - Mecze mają obsadę: participant1 vs participant2.
      - Wymagane: co najmniej 2 uczestników.

    DBL (debel):
      - Uczestnicy tworzą stałe pary drużyn (sorted by pk: [0,1], [2,3], …).
      - Każda drużyna gra z każdą inną drużyną dokładnie raz.
      - Obsada meczu: participant1+participant4 vs participant2+participant3
        (konwencja spójna z AMR DBL).
      - Wymagane: parzysta liczba uczestników, co najmniej 4.
    """
    from itertools import combinations

    is_doubles = tournament.match_format == 'DBL'
    participants = list(participants_qs.order_by('pk'))
    n = len(participants)

    if is_doubles:
        if n < 4:
            return 0, f"Za mało uczestników ({n}). RR debel wymaga co najmniej 4."
        if n % 2 != 0:
            return 0, f"RR debel wymaga parzystej liczby uczestników (masz {n}). Dodaj lub usuń jednego gracza."

        # Sparuj graczy w stałe drużyny: (p0,p1), (p2,p3), ...
        teams = [(participants[i], participants[i + 1]) for i in range(0, n, 2)]

        TournamentsMatch.objects.filter(tournament=tournament).delete()

        matches_to_create = []
        for i, ((ta1, ta2), (tb1, tb2)) in enumerate(combinations(teams, 2), 1):
            # Team A = ta1 (p1) + ta2 (p4),  Team B = tb1 (p2) + tb2 (p3)
            # Konwencja: participant1+participant4 vs participant2+participant3
            matches_to_create.append(
                TournamentsMatch(
                    tournament=tournament,
                    participant1=ta1, participant2=tb1,
                    participant3=tb2, participant4=ta2,
                    round_number=1,
                    match_index=i,
                    status=TournamentsMatch.Status.WAITING.value,
                )
            )

        created = TournamentsMatch.objects.bulk_create(matches_to_create)
        return len(created), f"Wygenerowano {len(created)} meczów deblowych (RR DBL)."

    # SNG — każdy z każdym
    if n < 2:
        return 0, "Za mało uczestników (wymagane co najmniej 2), aby wygenerować mecze."

    TournamentsMatch.objects.filter(tournament=tournament).delete()

    matches_to_create = [
        TournamentsMatch(
            tournament=tournament,
            participant1=p1,
            participant2=p2,
            round_number=1,
            match_index=i,
            status=TournamentsMatch.Status.WAITING.value,
        )
        for i, (p1, p2) in enumerate(combinations(participants, 2), 1)
    ]

    created = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created), f"Wygenerowano {len(created)} meczów."


def generate_elimination_matches_initial(tournament, participants_qs, config, bracket_type=None):
    """
    Generuje mecze pierwszej rundy dla turnieju pucharowego (Single lub Double Elimination).
    Parametr bracket_type określa typ drabinki ('W' dla Winners, domyślnie).
    Uwzględnia rozstawienie (seeding) i wolne losy (byes).
    """
    from apps.tournaments.models import TournamentsMatch as _TM
    if bracket_type is None:
        bracket_type = _TM.BracketType.WINNERS
    num_participants = participants_qs.count()
    if num_participants < 2:
        return 0, "Za mało uczestników (wymagane co najmniej 2), aby wygenerować drabinkę."

    TournamentsMatch.objects.filter(tournament=tournament).delete()

    # Oblicz rozmiar drabinki (najbliższa potęga dwójki) i liczbę wolnych losów
    bracket_size = 2**math.ceil(math.log2(num_participants))
    num_byes = bracket_size - num_participants

    # Sprawdź, czy używać rozstawienia
    use_seeding = (config.initial_seeding == 'SEEDING') and any(p.seed_number is not None for p in participants_qs)

    # Ta lista będzie przechowywać obiekty Participant lub None (dla wolnych losów) w odpowiednich slotach drabinki
    final_bracket_slots = [None] * bracket_size

    if use_seeding:
        # Dzielimy uczestników na rozstawionych i nierozstawionych
        seeded_participants = {p.seed_number: p for p in participants_qs if p.seed_number is not None}
        unseeded_participants = [p for p in participants_qs if p.seed_number is None]
        random.shuffle(unseeded_participants) # Mieszamy nierozstawionych graczy

        # Wygeneruj mapowanie numeru rozstawienia na slot w drabince
        seed_to_slot_map = _generate_seed_to_slot_map(bracket_size)
        
        # Krok 1: Umieść rozstawionych graczy w ich dedykowanych slotach
        for seed_num, participant in seeded_participants.items():
            slot_idx = seed_to_slot_map.get(seed_num)
            if slot_idx is not None and slot_idx < bracket_size:
                final_bracket_slots[slot_idx] = participant

        # Krok 2: Wypełnij pozostałe wolne sloty nierozstawionymi graczami
        empty_slots_indices = [i for i, slot in enumerate(final_bracket_slots) if slot is None]
        
        for i, slot_idx in enumerate(empty_slots_indices):
            if i < len(unseeded_participants):
                final_bracket_slots[slot_idx] = unseeded_participants[i]
            else:
                break
            
    else: # Losowe rozmieszczenie
        all_participants = list(participants_qs)
        random.shuffle(all_participants)

        # Rozmieszaj BYE tak, żeby żadna para (i, i+1) nie miała obu slotów None
        final_bracket_slots = [None] * bracket_size
        num_pairs = bracket_size // 2
        pairs_with_bye = set(range(num_pairs - num_byes, num_pairs))
        player_idx = 0
        for pair in range(num_pairs):
            slot_a = pair * 2
            slot_b = pair * 2 + 1
            final_bracket_slots[slot_a] = all_participants[player_idx]
            player_idx += 1
            if pair not in pairs_with_bye:
                final_bracket_slots[slot_b] = all_participants[player_idx]
                player_idx += 1

    matches_to_create = []
    match_index = 1

    # Twórz mecze pierwszej rundy, parując sąsiednie sloty
    for i in range(0, bracket_size, 2):
        p1_slot = final_bracket_slots[i]
        p2_slot = final_bracket_slots[i+1]

        if p1_slot is None and p2_slot is None:
            continue
        elif p1_slot is None:
            # p2_slot otrzymuje wolny los (bye)
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p2_slot, participant2=None,
                bracket_type=bracket_type,
                round_number=1, match_index=match_index, status=TournamentsMatch.Status.COMPLETED.value, winner=p2_slot
            ))
        elif p2_slot is None:
            # p1_slot otrzymuje wolny los (bye)
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p1_slot, participant2=None,
                bracket_type=bracket_type,
                round_number=1, match_index=match_index, status=TournamentsMatch.Status.COMPLETED.value, winner=p1_slot
            ))
        else:
            # Obaj gracze są obecni, utwórz standardowy mecz
            matches_to_create.append(TournamentsMatch(
                tournament=tournament, participant1=p1_slot, participant2=p2_slot,
                bracket_type=bracket_type,
                round_number=1, match_index=match_index, status=TournamentsMatch.Status.WAITING.value
            ))
        match_index += 1

    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)

    # Advance graczy z meczów BYE (participant2=None, status=CMP) do R2.
    if num_byes > 0:
        from apps.tournaments.models import TournamentsMatch as _TM2
        if tournament.tournament_type == 'SGL':
            from apps.tournaments.bracket import advance_winner_in_bracket
            for m in _TM2.objects.filter(tournament=tournament, round_number=1, participant2=None, status=_TM2.Status.COMPLETED):
                advance_winner_in_bracket(m, tournament)
        elif tournament.tournament_type == 'DBE':
            from apps.tournaments.bracket import advance_dbe_match
            for m in _TM2.objects.filter(tournament=tournament, round_number=1, participant2=None, status=_TM2.Status.COMPLETED):
                advance_dbe_match(m, tournament)

    return len(created_matches), f"Wygenerowano drabinkę dla {num_participants} uczestników ({len(matches_to_create)} meczów, {num_byes} wolnych losów)."


def generate_americano_matches(tournament, participants_qs, config):
    """
    Generuje mecze dla turnieju Americano na podstawie liczby graczy i rund.
    Używa algorytmu "circle method" do rotacji graczy.
    Obsługuje SNG (singiel) i DBL (debel).
    """
    num_participants = participants_qs.count()
    is_doubles = tournament.match_format == 'DBL'

    if num_participants < 4:
        return 0, f"Nieprawidłowa liczba uczestników ({num_participants}). Wymagane co najmniej 4."
    if is_doubles and num_participants % 4 != 0:
        return 0, f"Americano debel wymaga wielokrotności 4 uczestników (masz {num_participants})."
    if not is_doubles and num_participants % 2 != 0:
        return 0, f"Americano singiel wymaga parzystej liczby uczestników (masz {num_participants})."

    TournamentsMatch.objects.filter(tournament=tournament).delete()

    matches_to_create = []

    if config.scheduling_type == 'DYNAMIC':
        # Tryb Mexicano: generujemy tylko rundę 1 na podstawie seed
        participants = list(participants_qs.order_by('seed_number'))
        if is_doubles:
            num_matches = num_participants // 4
            message = f"Wygenerowano 1. rundę ({num_matches} meczów debel) dla trybu Mexicano."
            for i in range(num_matches):
                p1, p2, p3, p4 = participants[i * 4:(i + 1) * 4]
                matches_to_create.append(
                    TournamentsMatch(
                        tournament=tournament,
                        participant1=p1, participant2=p4,
                        participant3=p2, participant4=p3,
                        round_number=1,
                        match_index=i + 1,
                        status=TournamentsMatch.Status.WAITING.value,
                    )
                )
        else:
            num_matches = num_participants // 2
            message = f"Wygenerowano 1. rundę ({num_matches} meczów singiel) dla trybu Mexicano."
            for i in range(num_matches):
                p1 = participants[i * 2]
                p2 = participants[i * 2 + 1]
                matches_to_create.append(
                    TournamentsMatch(
                        tournament=tournament,
                        participant1=p1, participant2=p2,
                        participant3=None, participant4=None,
                        round_number=1,
                        match_index=i + 1,
                        status=TournamentsMatch.Status.WAITING.value,
                    )
                )
    else:
        # Tryb Americano (STATIC): generujemy wszystkie rundy losowo — tylko DBL
        participants = list(participants_qs)
        random.shuffle(participants)
        num_rounds = config.number_of_rounds
        num_courts = num_participants // 4
        message = f"Wygenerowano losowo {num_rounds} rund ({num_rounds * num_courts} meczów) dla trybu Americano."

        p_last = participants[-1]
        p_others = participants[:-1]

        for r in range(num_rounds):
            round_number = r + 1
            current_round_players = p_others + [p_last]

            for i in range(num_courts):
                match_index = i + 1
                p1 = current_round_players[i]
                p2 = current_round_players[i + num_courts]
                p3 = current_round_players[i + 2 * num_courts]
                p4 = current_round_players[i + 3 * num_courts]

                matches_to_create.append(
                    TournamentsMatch(
                        tournament=tournament,
                        participant1=p1, participant2=p4,
                        participant3=p2, participant4=p3,
                        round_number=round_number,
                        match_index=match_index,
                        status=TournamentsMatch.Status.WAITING.value,
                    )
                )
            p_others = [p_others[-1]] + p_others[:-1]

    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)
    return len(created_matches), message


def generate_next_mexicano_round(tournament, config, standings_list):
    """
    Generuje następną rundę dla turnieju w trybie Mexicano na podstawie aktualnej tabeli.
    Obsługuje SNG (singiel) i DBL (debel).
    """
    current_max_round = tournament.matches.aggregate(max_round=Max('round_number')).get('max_round') or 0
    next_round_number = current_max_round + 1

    if next_round_number > config.number_of_rounds:
        return 0, "Osiągnięto maksymalną liczbę rund. Turniej można zakończyć."

    participants = [s['participant'] for s in standings_list]
    num_participants = len(participants)
    is_doubles = tournament.match_format == 'DBL'

    if num_participants < 4:
        return 0, f"Za mało uczestników ({num_participants}) — potrzeba co najmniej 4."

    if is_doubles:
        if num_participants % 4 != 0:
            return 0, f"Mexicano debel wymaga wielokrotności 4 uczestników (masz {num_participants})."
        num_matches = num_participants // 4
    else:
        if num_participants % 2 != 0:
            return 0, f"Mexicano singiel wymaga parzystej liczby uczestników (masz {num_participants})."
        num_matches = num_participants // 2

    matches_to_create = []

    if is_doubles:
        # Debel: grupy po 4, konwencja Team A = (p1,p4) vs Team B = (p2,p3)
        for i in range(num_matches):
            p1, p2, p3, p4 = participants[i * 4:(i + 1) * 4]
            matches_to_create.append(
                TournamentsMatch(
                    tournament=tournament,
                    participant1=p1, participant2=p4,
                    participant3=p2, participant4=p3,
                    round_number=next_round_number,
                    match_index=i + 1,
                    status=TournamentsMatch.Status.WAITING.value,
                )
            )
    else:
        # Singiel: parowanie 1v2, 3v4, ...
        for i in range(num_matches):
            p1 = participants[i * 2]
            p2 = participants[i * 2 + 1]
            matches_to_create.append(
                TournamentsMatch(
                    tournament=tournament,
                    participant1=p1, participant2=p2,
                    participant3=None, participant4=None,
                    round_number=next_round_number,
                    match_index=i + 1,
                    status=TournamentsMatch.Status.WAITING.value,
                )
            )

    created_matches = TournamentsMatch.objects.bulk_create(matches_to_create)
    message = f"Automatycznie wygenerowano {len(created_matches)} meczów dla rundy {next_round_number}."
    return len(created_matches), message
