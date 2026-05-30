"""
bracket.py — logika drabinki eliminacyjnej dla Tennis Club.

Obsługuje Single Elimination (SGL) i Double Elimination (DBE).

━━━ Single Elimination ━━━
Główna funkcja: advance_winner_in_bracket(match, tournament)
Wywoływana po każdym CMP lub WDR meczu turnieju typu SGL.

Algorytm drabinki:
  - Mecze rundy R mają round_number=R, match_index=1..N
  - Para meczów (2k-1, 2k) w rundzie R wyłania zwycięzcę do meczu k w rundzie R+1
    czyli: ceil(match_index / 2) w kolejnej rundzie
  - Slot w meczu kolejnej rundy:
      match_index nieparzyste → participant1
      match_index parzyste    → participant2
  - Jeśli mecz kolejnej rundy nie istnieje → tworzymy pusty mecz (lazy creation)
  - Jeśli obaj uczestnicy kolejnego meczu są już znani → mecz gotowy do rozegrania (WAI)
  - Mecz o 3. miejsce (opcjonalny): generowany osobno gdy obaj przegrani z półfinałów są znani

━━━ Double Elimination ━━━
Główna funkcja: advance_dbe_match(match, tournament)
Wywoływana po każdym CMP lub WDR meczu turnieju typu DBE.

Struktura DBE dla bracket_size B = 2^k (k = log2(B)):
  Winners Bracket (bracket_type='W'):  k rund, R1..Rk
  Losers Bracket (bracket_type='L'):   2*(k-1) rund, LR1..LR(2k-2)
  Grand Final (bracket_type='GF'):     1 mecz, round_number=1, match_index=1

Routing przegranych z WB do LB:
  WB_Rn loser → LB round = 2*n - 1, index obliczany z pozycji w WB
  Rundy LB "drop-in" (nieparzyste): przegrani WB wpadają z góry
  Rundy LB "konsolidacja" (parzyste): czysto wewnętrzne mecze LB

Indeksy LB:
  LB_R1: przegrani WB_R1 meczu 2k-1 i 2k → LB_R1 mecz k (p1/p2)
  LB parzyste (konsolidacja): zwycięzcy dwóch meczów → jeden mecz (ceil/2)
  LB nieparzyste (drop-in): zwycięzca LB poprzedniej + przegrany WB tej samej rundy

Grand Final:
  Zwycięzca WB Final (WB ostatnia runda) i zwycięzca LB Final (ostatnia runda LB)
  wchodzą do meczu GF. Bez bracket reset w MVP.

Edge case'y obsługiwane:
  - BYE (participant2=None, winner=participant1): traktowane jak normalny awans
  - Re-edycja wyniku: advance jest idempotentny — nadpisuje slot tylko jeśli zmiana winnera
  - Lazy creation: mecze LB i GF tworzone dopiero gdy obaj uczestnicy są znani
"""

import logging
import math
from django.db import transaction

logger = logging.getLogger(__name__)


def _participant_slot(match_index: int) -> str:
    """
    Zwraca nazwę pola uczestnika w meczu następnej rundy.
    Mecz o indeksie nieparzystym → participant1, parzystym → participant2.
    """
    return 'participant1' if match_index % 2 == 1 else 'participant2'


def _next_match_index(match_index: int) -> int:
    """Indeks meczu w następnej rundzie dla meczu o podanym indeksie."""
    return math.ceil(match_index / 2)


def _total_rounds(num_participants: int) -> int:
    """Liczba rund (bez meczu o 3. miejsce) dla danej liczby uczestników."""
    if num_participants < 2:
        return 1
    return math.ceil(math.log2(num_participants))


def advance_winner_in_bracket(match, tournament) -> bool:
    """
    Po zakończeniu meczu SGL (CMP lub WDR) przesuwa zwycięzcę do kolejnej rundy.

    Zwraca True jeśli awans się odbył lub był już aktualny, False jeśli nic nie zrobiono
    (np. mecz nie ma zwycięzcy, lub to był finał).

    Uwagi:
    - Wywołana w obrębie istniejącej transakcji DB (save() meczu jest już zrobiony).
    - Idempotentna przy re-edycji — nadpisuje slot nawet jeśli był już wypełniony innym uczestnikiem
      (scenariusz: błędny wynik → korekta).
    - Nie tworzy rundy następnej jeśli to był finał (max_round).
    """
    from apps.tournaments.models import TournamentsMatch, EliminationConfig

    winner = match.winner
    if winner is None:
        return False

    current_round = match.round_number
    current_index = match.match_index

    # ── Oblicz rozmiar drabinki żeby wiedzieć ile rund ─────────────────────────
    # Liczymy uczestników nie-BYE w turnieju (status REG/ACT/OUT, nie WDN)
    # Używamy liczby meczów w rundzie 1 jako proxy (każdy mecz R1 = 2 sloty)
    r1_matches = TournamentsMatch.objects.filter(
        tournament=tournament, round_number=1
    ).count()
    # bracket_size = 2 * r1_matches (pary), total_rounds = log2(bracket_size)
    bracket_size = r1_matches * 2
    if bracket_size < 2:
        bracket_size = 2
    total_rounds = int(math.log2(bracket_size))  # np. 8 uczestników → 3 rundy

    # ── Sprawdź czy to był finał ────────────────────────────────────────────────
    if current_round >= total_rounds:
        # To był finał — nie awansujemy dalej; opcjonalnie triggerujemy mecz o 3. miejsce
        logger.info(
            '[bracket] Finał zakończony (turniej id=%d, mecz id=%d). Zwycięzca: %s.',
            tournament.pk, match.pk, winner.display_name
        )
        # Sprawdź mecz o 3. miejsce gdy półfinały (runda total_rounds-1) są kompletne
        if total_rounds >= 2:
            _ensure_third_place_match(tournament, total_rounds)
        return True

    # ── Oblicz pozycję w następnej rundzie ────────────────────────────────────
    next_round = current_round + 1
    next_index = _next_match_index(current_index)
    slot_field = _participant_slot(current_index)

    # ── Pobierz lub stwórz mecz następnej rundy ───────────────────────────────
    with transaction.atomic():
        next_match, created = TournamentsMatch.objects.select_for_update().get_or_create(
            tournament=tournament,
            bracket_type=TournamentsMatch.BracketType.WINNERS,
            round_number=next_round,
            match_index=next_index,
            defaults={
                'status': TournamentsMatch.Status.WAITING.value,
                slot_field: winner,
            }
        )

        if not created:
            # Mecz już istnieje — zaktualizuj odpowiedni slot
            current_value = getattr(next_match, slot_field)
            if current_value != winner:
                setattr(next_match, slot_field, winner)
                next_match.save(update_fields=[slot_field])
                logger.info(
                    '[bracket] Nadpisano %s meczu R%d/%d (turniej id=%d): %s → %s.',
                    slot_field, next_round, next_index, tournament.pk,
                    current_value.display_name if current_value else 'None',
                    winner.display_name,
                )
            else:
                logger.debug(
                    '[bracket] %s meczu R%d/%d (turniej id=%d) bez zmian (%s).',
                    slot_field, next_round, next_index, tournament.pk, winner.display_name,
                )
        else:
            logger.info(
                '[bracket] Utworzono mecz R%d/%d (turniej id=%d), %s=%s.',
                next_round, next_index, tournament.pk, slot_field, winner.display_name,
            )

        # Sprawdź czy mecz o 3. miejsce wymaga aktualizacji (półfinały)
        if current_round == total_rounds - 1 and total_rounds >= 2:
            _ensure_third_place_match(tournament, total_rounds)

    return True


def _get_loser(match) -> object | None:
    """Zwraca przegranego meczu (uczestnik który NIE jest winnerem)."""
    if match.winner is None:
        return None
    if match.participant1 and match.participant1 != match.winner:
        return match.participant1
    if match.participant2 and match.participant2 != match.winner:
        return match.participant2
    return None


def _ensure_third_place_match(tournament, total_rounds: int):
    """
    Tworzy lub aktualizuje mecz o 3. miejsce gdy obaj przegrani z półfinałów są znani.

    Mecz o 3. miejsce:
      round_number = total_rounds (ta sama runda co finał)
      match_index  = 2 (finał ma match_index=1)

    Generowany tylko jeśli EliminationConfig.third_place_match == True.
    """
    from apps.tournaments.models import TournamentsMatch, EliminationConfig

    try:
        config = tournament.elimination_config
        if not config.third_place_match:
            return
    except EliminationConfig.DoesNotExist:
        return  # Brak konfiguracji → nie generujemy

    semifinal_round = total_rounds - 1
    sf_matches = TournamentsMatch.objects.filter(
        tournament=tournament,
        round_number=semifinal_round,
    ).exclude(
        participant2__isnull=True  # Pomijaj bye
    )

    losers = []
    for sf in sf_matches:
        if sf.status in (
            TournamentsMatch.Status.COMPLETED.value,
            TournamentsMatch.Status.WITHDRAWN.value,
        ):
            loser = _get_loser(sf)
            if loser:
                losers.append(loser)

    if len(losers) < 2:
        return  # Jeszcze nie wszyscy przegrani z SF znani

    p1_loser, p2_loser = losers[0], losers[1]

    # Mecz o 3. miejsce: round_number=total_rounds, match_index=2
    third_match, created = TournamentsMatch.objects.get_or_create(
        tournament=tournament,
        bracket_type=TournamentsMatch.BracketType.WINNERS,
        round_number=total_rounds,
        match_index=2,
        defaults={
            'participant1': p1_loser,
            'participant2': p2_loser,
            'status': TournamentsMatch.Status.WAITING.value,
        }
    )

    if not created:
        # Aktualizuj jeśli losers się zmienili (re-edycja)
        changed = False
        if third_match.participant1 != p1_loser:
            third_match.participant1 = p1_loser
            changed = True
        if third_match.participant2 != p2_loser:
            third_match.participant2 = p2_loser
            changed = True
        if changed:
            third_match.save(update_fields=['participant1', 'participant2'])
            logger.info('[bracket] Zaktualizowano mecz o 3. miejsce (turniej id=%d).', tournament.pk)
    else:
        logger.info(
            '[bracket] Utworzono mecz o 3. miejsce (turniej id=%d): %s vs %s.',
            tournament.pk, p1_loser.display_name, p2_loser.display_name,
        )


def build_bracket_data(tournament) -> list[dict]:
    """
    Buduje strukturę drabinki pogrupowaną po rundach dla endpointu GET /bracket/.

    Zwraca listę rund:
    [
      {
        "round": 1,
        "round_label": "Runda 1",   # lub "Finał", "Półfinał", "Ćwierćfinał", "Mecz o 3. miejsce"
        "matches": [ { match_data }, ... ]
      },
      ...
    ]

    match_data:
    {
      "id": int,
      "match_index": int,
      "status": str,
      "status_display": str,
      "is_bye": bool,
      "is_third_place": bool,
      "participant1": { "id", "display_name", "seed_number", "user_id" } | null,
      "participant2": { "id", "display_name", "seed_number", "user_id" } | null,
      "winner_id": int | null,
      "score": str | null,        # "6:4 7:5" lub null
      "scheduled_time": str | null,
    }
    """
    from apps.tournaments.models import TournamentsMatch

    matches_qs = (
        TournamentsMatch.objects
        .filter(tournament=tournament)
        .select_related(
            'participant1__user',
            'participant2__user',
            'winner',
        )
        .order_by('round_number', 'match_index')
    )

    # Oblicz total_rounds dla etykiet
    r1_count = sum(1 for m in matches_qs if m.round_number == 1)
    bracket_size = r1_count * 2
    if bracket_size >= 2:
        total_rounds = int(math.log2(bracket_size))
    else:
        total_rounds = 1

    def round_label(round_number: int, match_index: int, tr: int) -> str:
        # Mecz o 3. miejsce: ta sama runda co finał, match_index=2
        if round_number == tr and match_index == 2:
            return 'Mecz o 3. miejsce'
        if round_number == tr:
            return 'Finał'
        if round_number == tr - 1:
            return 'Półfinał'
        if round_number == tr - 2:
            return 'Ćwierćfinał'
        return f'Runda {round_number}'

    def participant_data(p) -> dict | None:
        if p is None:
            return None
        return {
            'id': p.pk,
            'display_name': p.display_name,
            'seed_number': p.seed_number,
            'user_id': p.user_id,
        }

    def score_str(m) -> str | None:
        parts = []
        for i in range(1, 4):
            s1 = getattr(m, f'set{i}_p1_score')
            s2 = getattr(m, f'set{i}_p2_score')
            if s1 is not None and s2 is not None:
                parts.append(f'{s1}:{s2}')
        return ' '.join(parts) if parts else None

    # Grupuj po round_number
    rounds_dict: dict[int, list] = {}
    for m in matches_qs:
        rounds_dict.setdefault(m.round_number, []).append(m)

    rounds_out = []
    seen_labels: dict[int, str] = {}

    for round_num in sorted(rounds_dict.keys()):
        round_matches = rounds_dict[round_num]
        match_list = []
        round_label_str = None

        for m in sorted(round_matches, key=lambda x: x.match_index):
            is_bye = m.participant2 is None
            is_third = (round_num == total_rounds and m.match_index == 2)
            lbl = round_label(round_num, m.match_index, total_rounds)
            if round_label_str is None:
                # Etykieta rundy — dla finału/SF etykieta na podstawie pierwszego meczu (index=1)
                if m.match_index == 1:
                    round_label_str = lbl

            match_list.append({
                'id': m.pk,
                'match_index': m.match_index,
                'status': m.status,
                'status_display': m.get_status_display(),
                'is_bye': is_bye,
                'is_third_place': is_third,
                'participant1': participant_data(m.participant1),
                'participant2': participant_data(m.participant2),
                'winner_id': m.winner_id,
                'score': score_str(m),
                'scheduled_time': m.scheduled_time.isoformat() if m.scheduled_time else None,
            })

        rounds_out.append({
            'round': round_num,
            'round_label': round_label_str or f'Runda {round_num}',
            'matches': match_list,
        })

    return rounds_out


def build_dbe_bracket_data(tournament) -> dict:
    """
    Buduje strukturę drabinki DBE dla endpointu GET /bracket/.

    Zwraca słownik:
    {
      "type": "dbe",
      "winners": [ { "round": int, "round_label": str, "matches": [...] }, ... ],
      "losers":  [ { "round": int, "round_label": str, "matches": [...] }, ... ],
      "grand_final": { "round": 1, "round_label": "Wielki Finał", "matches": [...] } | null,
    }

    match shape identyczny jak w build_bracket_data() (dla SGL).
    """
    from apps.tournaments.models import TournamentsMatch
    BT = TournamentsMatch.BracketType

    all_matches = (
        TournamentsMatch.objects
        .filter(tournament=tournament)
        .select_related('participant1__user', 'participant2__user', 'winner')
        .order_by('bracket_type', 'round_number', 'match_index')
    )

    def participant_data(p):
        if p is None:
            return None
        return {
            'id': p.pk,
            'display_name': p.display_name,
            'seed_number': p.seed_number,
            'user_id': p.user_id,
        }

    def score_str(m):
        parts = []
        for i in range(1, 4):
            s1 = getattr(m, f'set{i}_p1_score')
            s2 = getattr(m, f'set{i}_p2_score')
            if s1 is not None and s2 is not None:
                parts.append(f'{s1}:{s2}')
        return ' '.join(parts) if parts else None

    def match_dict(m):
        is_bye = m.participant2 is None and m.status == TournamentsMatch.Status.COMPLETED.value
        return {
            'id': m.pk,
            'match_index': m.match_index,
            'bracket_type': m.bracket_type,
            'status': m.status,
            'status_display': m.get_status_display(),
            'is_bye': is_bye,
            'is_third_place': False,
            'participant1': participant_data(m.participant1),
            'participant2': participant_data(m.participant2),
            'winner_id': m.winner_id,
            'score': score_str(m),
            'scheduled_time': m.scheduled_time.isoformat() if m.scheduled_time else None,
        }

    # Oblicz wb_total_rounds dla etykiet WB
    wb_r1_count = sum(1 for m in all_matches if m.bracket_type == BT.WINNERS and m.round_number == 1)
    bracket_size = wb_r1_count * 2 if wb_r1_count > 0 else 2
    wb_total = int(math.log2(bracket_size)) if bracket_size >= 2 else 1
    lb_total = 2 * (wb_total - 1)

    def wb_round_label(rn: int) -> str:
        if rn == wb_total:
            return 'Finał WB'
        if rn == wb_total - 1:
            return 'Półfinał WB'
        return f'WB Runda {rn}'

    def lb_round_label(rn: int) -> str:
        if rn == lb_total:
            return 'Finał LB'
        return f'LB Runda {rn}'

    # Grupuj po bracket_type i round_number
    wb_rounds: dict[int, list] = {}
    lb_rounds: dict[int, list] = {}
    gf_matches: list = []

    for m in all_matches:
        if m.bracket_type == BT.WINNERS:
            wb_rounds.setdefault(m.round_number, []).append(m)
        elif m.bracket_type == BT.LOSERS:
            lb_rounds.setdefault(m.round_number, []).append(m)
        elif m.bracket_type == BT.GRAND_FINAL:
            gf_matches.append(m)

    def build_rounds(rounds_dict: dict, label_fn) -> list[dict]:
        result = []
        for rn in sorted(rounds_dict.keys()):
            matches = sorted(rounds_dict[rn], key=lambda x: x.match_index)
            result.append({
                'round': rn,
                'round_label': label_fn(rn),
                'matches': [match_dict(m) for m in matches],
            })
        return result

    gf_section = None
    if gf_matches:
        gf_section = {
            'round': 1,
            'round_label': 'Wielki Finał',
            'matches': [match_dict(m) for m in gf_matches],
        }

    return {
        'type': 'dbe',
        'winners': build_rounds(wb_rounds, wb_round_label),
        'losers': build_rounds(lb_rounds, lb_round_label),
        'grand_final': gf_section,
    }


# ── Double Elimination — advance logic ────────────────────────────────────────

def _wb_total_rounds(tournament) -> int:
    """
    Liczba rund Winners Bracket = log2(bracket_size).
    bracket_size = 2 * (liczba meczów R1 WB).
    """
    from apps.tournaments.models import TournamentsMatch
    r1_count = TournamentsMatch.objects.filter(
        tournament=tournament,
        bracket_type=TournamentsMatch.BracketType.WINNERS,
        round_number=1,
    ).count()
    if r1_count < 1:
        return 1
    bracket_size = r1_count * 2
    return int(math.log2(bracket_size))


def _lb_round_for_wb_drop(wb_round: int) -> int:
    """
    Runda LB do której trafia przegrany z danej rundy WB.

    Standard DBE mapping:
      WB_R1 → LB_R1  (2*1 - 1 = 1)
      WB_R2 → LB_R3  (2*2 - 1 = 3)
      WB_R3 → LB_R5  (2*3 - 1 = 5)
      WB_Rn → LB_R(2n-1)
    """
    return 2 * wb_round - 1


def _lb_drop_index(wb_index: int, wb_round: int, wb_total_rounds: int) -> int:
    """
    Indeks meczu w LB dla przegranego z meczu WB.

    W WB_R1: pary (1,2)→LB_1, (3,4)→LB_2 itd.
      lb_index = ceil(wb_index / 2)

    W WB_Rn (n>1): jeden przegrany z każdego meczu WB wchodzi do LB
      jako participant2 (z góry) w meczu o tym samym indeksie co WB.
      lb_index = wb_index
    """
    if wb_round == 1:
        return math.ceil(wb_index / 2)
    return wb_index


def _lb_drop_slot(wb_index: int, wb_round: int) -> str:
    """
    Który slot (participant1/participant2) zajmuje przegrany wpadający do LB.

    W LB rundy drop-in (2n-1 dla n>1): przegrani WB zawsze wchodzą jako participant2
    (zwycięzcy z poprzedniej rundy LB są już w participant1).

    W LB_R1: para (wb_1,wb_2) → lb_1 — wb_index nieparzyste=p1, parzyste=p2.
    """
    if wb_round == 1:
        return 'participant1' if wb_index % 2 == 1 else 'participant2'
    return 'participant2'


def _get_or_create_bracket_match(tournament, bracket_type, round_number, match_index, **defaults):
    """
    Lazy-create meczu w podanej drabince. Idempotentny.
    Zwraca (match, created).
    """
    from apps.tournaments.models import TournamentsMatch
    with transaction.atomic():
        match, created = TournamentsMatch.objects.select_for_update().get_or_create(
            tournament=tournament,
            bracket_type=bracket_type,
            round_number=round_number,
            match_index=match_index,
            defaults={
                'status': TournamentsMatch.Status.WAITING.value,
                **defaults,
            },
        )
    return match, created


def _set_match_slot(match, slot_field: str, participant) -> bool:
    """
    Ustaw slot uczestnika w meczu. Zwraca True jeśli nastąpiła zmiana.
    Wywołujący musi zapisać mecz jeśli True.
    """
    current = getattr(match, slot_field)
    if current != participant:
        setattr(match, slot_field, participant)
        return True
    return False


def _auto_complete_if_bye(bracket_match, tournament):
    """
    Jeśli jeden ze slotów meczu to BYE (None), auto-zakończ mecz i wywołaj advance.

    Przypadki:
    - participant1=None, participant2=X → winner=X, status=CMP
    - participant1=X, participant2=None → winner=X, status=CMP
    - oboje None → błąd logiczny, pomijamy
    - oboje znani → normalny mecz, nic nie robimy

    Po auto-CMP wywołuje advance_dbe_match rekurencyjnie, aby dalej propagować awans.
    """
    from apps.tournaments.models import TournamentsMatch
    p1 = bracket_match.participant1
    p2 = bracket_match.participant2

    if p1 is not None and p2 is not None:
        return  # Oboje znani — normalny mecz
    if p1 is None and p2 is None:
        return  # Brak obu — mecz jeszcze nie gotowy

    winner = p1 if p1 is not None else p2
    if bracket_match.status == TournamentsMatch.Status.COMPLETED.value and bracket_match.winner == winner:
        # Już auto-zakończony — idempotentny
        return

    bracket_match.status = TournamentsMatch.Status.COMPLETED.value
    bracket_match.winner = winner
    bracket_match.save(update_fields=['status', 'winner'])

    logger.info(
        '[dbe] Auto-BYE: mecz [%s] R%d/M%d → CMP, winner=%s (turniej id=%d).',
        bracket_match.bracket_type, bracket_match.round_number, bracket_match.match_index,
        winner.display_name, tournament.pk,
    )

    # Propaguj awans rekurencyjnie
    advance_dbe_match(bracket_match, tournament)


def _advance_loser_to_lb(match, loser, wb_total_rounds: int):
    """
    Umieszcza przegranego z meczu WB w odpowiednim meczu losers bracket.

    Przypadki:
    - WB Final (round == wb_total_rounds): przegrany trafia do LB Final
      (ostatnia runda LB = 2*(wb_total_rounds-1), match_index=1, slot=p2)
    - Pozostałe rundy WB: oblicz LB round i index z mapowania standardowego DBE
    """
    from apps.tournaments.models import TournamentsMatch
    BT = TournamentsMatch.BracketType

    wb_round = match.round_number
    wb_index = match.match_index

    if wb_round == wb_total_rounds:
        # WB Final loser → LB Final (slot participant2, zwycięzca LB konsolidacji już w p1)
        lb_final_round = 2 * (wb_total_rounds - 1)
        if lb_final_round < 1:
            # Edge case: bracket_size=2 (1 mecz WB, brak LB) → brak LB
            return
        lb_match, created = _get_or_create_bracket_match(
            tournament=match.tournament,
            bracket_type=BT.LOSERS,
            round_number=lb_final_round,
            match_index=1,
        )
        changed = _set_match_slot(lb_match, 'participant2', loser)
        if not created and changed:
            lb_match.save(update_fields=['participant2'])
        elif created:
            lb_match.save(update_fields=['participant2'])
        logger.info(
            '[dbe] WB Final przegrany %s → LB Final (R%d/M1, slot p2), turniej id=%d.',
            loser.display_name, lb_final_round, match.tournament.pk,
        )
        return

    lb_round = _lb_round_for_wb_drop(wb_round)
    lb_index = _lb_drop_index(wb_index, wb_round, wb_total_rounds)
    lb_slot = _lb_drop_slot(wb_index, wb_round)

    lb_match, created = _get_or_create_bracket_match(
        tournament=match.tournament,
        bracket_type=BT.LOSERS,
        round_number=lb_round,
        match_index=lb_index,
    )
    changed = _set_match_slot(lb_match, lb_slot, loser)
    if not created and changed:
        lb_match.save(update_fields=[lb_slot])
    elif created:
        lb_match.save(update_fields=[lb_slot])

    logger.info(
        '[dbe] WB_R%d/M%d przegrany %s → LB_R%d/M%d (slot %s), turniej id=%d.',
        wb_round, wb_index, loser.display_name,
        lb_round, lb_index, lb_slot, match.tournament.pk,
    )

    # Structural BYE in LB drop-in rounds: when WB BYEs reduce the effective bracket size,
    # some LB matches never receive one of their participants.
    # For LB R1: p2 slot may be empty if the partner WB R1 match was a BYE.
    # For LB R3+: p1 slot may be empty if the corresponding LB consolidation match never existed.
    # In both cases, auto-complete the LB match so the single player can advance.
    lb_match.refresh_from_db()
    if lb_round == 1:
        # LB R1: check if partner WB R1 loser will ever arrive (other slot)
        _auto_complete_if_bye(lb_match, match.tournament)
    else:
        # LB R3+ (odd drop-in): p1 comes from LB (lb_round-1)/same_index.
        # If that consolidation match doesn't exist, p1 will never arrive.
        feeder_exists = TournamentsMatch.objects.filter(
            tournament=match.tournament,
            bracket_type=BT.LOSERS,
            round_number=lb_round - 1,
            match_index=lb_index,
        ).exists()
        if not feeder_exists:
            _auto_complete_if_bye(lb_match, match.tournament)


def _advance_winner_in_lb(match, winner, wb_total_rounds: int):
    """
    Przesuwa zwycięzcę meczu losers bracket do następnej rundy LB lub do Grand Final.

    LB ma 2*(wb_total_rounds-1) rund.
    Rundy LB parzyste (konsolidacja): ceil(index/2) w następnej rundzie, p1/p2 z indeksu
    Rundy LB nieparzyste (drop-in): indeks zachowany → następna runda parzysta

    Jeśli to była ostatnia runda LB → zwycięzca wchodzi do Grand Final jako p2.
    """
    from apps.tournaments.models import TournamentsMatch
    BT = TournamentsMatch.BracketType

    tournament = match.tournament
    lb_round = match.round_number
    lb_index = match.match_index
    lb_final_round = 2 * (wb_total_rounds - 1)

    if lb_round >= lb_final_round:
        # LB Final zakończony → zwycięzca do Grand Final
        _try_create_grand_final(tournament, winner_from_lb=winner, wb_total_rounds=wb_total_rounds)
        return

    # Awans w LB
    next_lb_round = lb_round + 1

    if lb_round % 2 == 0:
        # Runda parzysta (konsolidacja) → następna runda nieparzysta (drop-in)
        # Indeks zachowany — czekamy na przegranego WB
        next_lb_index = lb_index
        next_lb_slot = 'participant1'
    else:
        # Runda nieparzysta (drop-in lub R1) → następna parzysta (konsolidacja)
        next_lb_index = math.ceil(lb_index / 2)
        next_lb_slot = _participant_slot(lb_index)

    lb_next, created = _get_or_create_bracket_match(
        tournament=tournament,
        bracket_type=BT.LOSERS,
        round_number=next_lb_round,
        match_index=next_lb_index,
    )
    changed = _set_match_slot(lb_next, next_lb_slot, winner)
    if not created and changed:
        lb_next.save(update_fields=[next_lb_slot])
    elif created:
        lb_next.save(update_fields=[next_lb_slot])

    logger.info(
        '[dbe] LB_R%d/M%d zwycięzca %s → LB_R%d/M%d (slot %s), turniej id=%d.',
        lb_round, lb_index, winner.display_name,
        next_lb_round, next_lb_index, next_lb_slot, tournament.pk,
    )

    # Structural BYE propagation: when advancing into a consolidation round (even LB round),
    # the other slot is fed by the partner LB match from the previous odd round.
    # If that partner match never existed (because its WB R1 feeders were all BYEs),
    # the slot will never be filled → auto-complete the next LB match now.
    if next_lb_round % 2 == 0:
        # Determine which LB match feeds the other slot
        if next_lb_slot == 'participant1':
            partner_lb_index = lb_index + 1  # even index partner
        else:
            partner_lb_index = lb_index - 1  # odd index partner
        partner_exists = TournamentsMatch.objects.filter(
            tournament=tournament,
            bracket_type=BT.LOSERS,
            round_number=lb_round,
            match_index=partner_lb_index,
        ).exists()
        if not partner_exists:
            lb_next.refresh_from_db()
            _auto_complete_if_bye(lb_next, tournament)


def _try_create_grand_final(tournament, winner_from_lb=None, winner_from_wb=None, wb_total_rounds: int = 0):
    """
    Tworzy lub aktualizuje mecz Grand Final.
    Wywołana gdy znany jest zwycięzca WB Final lub LB Final.

    Grand Final: bracket_type='GF', round_number=1, match_index=1
      participant1 = zwycięzca WB
      participant2 = zwycięzca LB
    """
    from apps.tournaments.models import TournamentsMatch
    BT = TournamentsMatch.BracketType

    gf_match, created = _get_or_create_bracket_match(
        tournament=tournament,
        bracket_type=BT.GRAND_FINAL,
        round_number=1,
        match_index=1,
    )

    changed = False
    if winner_from_wb is not None:
        if _set_match_slot(gf_match, 'participant1', winner_from_wb):
            changed = True
    if winner_from_lb is not None:
        if _set_match_slot(gf_match, 'participant2', winner_from_lb):
            changed = True

    if created or changed:
        update_fields = []
        if winner_from_wb is not None:
            update_fields.append('participant1')
        if winner_from_lb is not None:
            update_fields.append('participant2')
        if update_fields:
            gf_match.save(update_fields=update_fields)

    logger.info(
        '[dbe] Grand Final: p1=%s, p2=%s (turniej id=%d).',
        gf_match.participant1.display_name if gf_match.participant1 else '?',
        gf_match.participant2.display_name if gf_match.participant2 else '?',
        tournament.pk,
    )


def advance_dbe_match(match, tournament):
    """
    Obsługuje awans po zakończeniu meczu DBE (CMP lub WDR).

    Routing:
    - bracket_type='W' (Winners Bracket):
        zwycięzca → następny mecz WB (lub GF jeśli WB Final)
        przegrany → odpowiedni mecz LB (lub LB Final jeśli WB Final)
    - bracket_type='L' (Losers Bracket):
        zwycięzca → następny mecz LB (lub GF jeśli LB Final)
        przegrany → odpada (koniec turnieju dla tego uczestnika)
    - bracket_type='GF' (Grand Final):
        turniej zakończony — brak dalszego routingu

    Idempotentna: może być wywołana wielokrotnie przy re-edycji wyniku.
    """
    from apps.tournaments.models import TournamentsMatch
    BT = TournamentsMatch.BracketType

    winner = match.winner
    if winner is None:
        return

    loser = _get_loser(match)
    wb_total = _wb_total_rounds(tournament)

    if match.bracket_type == BT.GRAND_FINAL:
        # Turniej zakończony — brak dalszego routingu
        logger.info(
            '[dbe] Grand Final zakończony. Zwycięzca: %s (turniej id=%d).',
            winner.display_name, tournament.pk,
        )
        return

    if match.bracket_type == BT.WINNERS:
        wb_round = match.round_number
        wb_index = match.match_index

        if wb_round >= wb_total:
            # WB Final: zwycięzca → GF, przegrany → LB Final
            _try_create_grand_final(tournament, winner_from_wb=winner, wb_total_rounds=wb_total)
            if loser:
                _advance_loser_to_lb(match, loser, wb_total)
        else:
            # Zwykły mecz WB: zwycięzca → następny WB, przegrany → LB
            next_round = wb_round + 1
            next_index = _next_match_index(wb_index)
            slot_field = _participant_slot(wb_index)

            wb_next, created = _get_or_create_bracket_match(
                tournament=tournament,
                bracket_type=BT.WINNERS,
                round_number=next_round,
                match_index=next_index,
            )
            changed = _set_match_slot(wb_next, slot_field, winner)
            if not created and changed:
                wb_next.save(update_fields=[slot_field])
            elif created:
                wb_next.save(update_fields=[slot_field])

            logger.info(
                '[dbe] WB_R%d/M%d zwycięzca %s → WB_R%d/M%d (slot %s), turniej id=%d.',
                wb_round, wb_index, winner.display_name,
                next_round, next_index, slot_field, tournament.pk,
            )

            if loser:
                _advance_loser_to_lb(match, loser, wb_total)

    elif match.bracket_type == BT.LOSERS:
        # LB: zwycięzca idzie dalej w LB lub do GF, przegrany odpada
        _advance_winner_in_lb(match, winner, wb_total)
        if loser:
            logger.info(
                '[dbe] LB_R%d/M%d przegrany %s odpada z turnieju id=%d.',
                match.round_number, match.match_index, loser.display_name, tournament.pk,
            )


# ── Americano STATIC — generowanie meczów ─────────────────────────────────────

def generate_americano_matches_static(tournament, participants_qs, config) -> tuple[int, str]:
    """
    Generuje mecze dla turnieju Americano w trybie STATIC (stały harmonogram).

    Algorytm round-robin z rotacją (rotation algorithm), dwa warianty:

    SNG (singiel):
      - n uczestników, każda runda = n/2 meczów (p1 vs p2)
      - Gracz 0 "kotwica" (stały), pozostali rotują w prawo co rundę
      - Para: circle[i] vs circle[n-1-i]
      - Guardy: n % 2 == 0, n >= 4, rounds <= n-1

    DBL (debel):
      - n uczestników (każdy = indywidualny gracz), każda runda = n/4 meczów (2v2)
      - Ta sama rotacja co SNG; mecz bierze 4 kolejne sloty po n/4 przesunięciu
      - Team A = circle[i] + circle[i + 3*k],  Team B = circle[i + k] + circle[i + 2*k]
        gdzie k = n // 4 (liczba kortów)
      - Konwencja spójna z resztą AMR debla: participant1+participant4 vs participant2+participant3
      - Guardy: n % 4 == 0, n >= 4, rounds <= n-1

    Zwraca: (liczba_meczów, komunikat)
    """
    from apps.tournaments.models import TournamentsMatch

    is_doubles = tournament.match_format == 'DBL'
    participants = list(participants_qs.order_by('pk'))
    n = len(participants)

    # ── Guardy ────────────────────────────────────────────────────────────────
    if n < 4:
        raise ValueError(f'Americano wymaga co najmniej 4 uczestników (masz {n}).')

    if is_doubles:
        if n % 4 != 0:
            raise ValueError(
                f'Americano debel wymaga liczby uczestników będącej wielokrotnością 4 (masz {n}). '
                f'Dodaj lub usuń gracza tak, aby było 4, 8, 12... uczestników.'
            )
    else:
        if n % 2 != 0:
            raise ValueError(
                f'Americano wymaga parzystej liczby uczestników (masz {n}). '
                f'Dodaj lub usuń jednego gracza.'
            )

    max_rounds = n - 1
    requested_rounds = config.number_of_rounds
    if requested_rounds < 1:
        raise ValueError('Liczba rund musi wynosić co najmniej 1.')
    if requested_rounds > max_rounds:
        raise ValueError(
            f'Przy {n} uczestnikach można rozegrać maksymalnie {max_rounds} rund. '
            f'Zmniejsz liczbę rund w konfiguracji.'
        )

    # ── Rotation algorithm ────────────────────────────────────────────────────
    # Gracz 0 stały ("kotwica"), pozostali rotują o 1 w prawo co rundę.
    # circle = [anchor] + rotate_right(players[1:], round_idx)

    players = list(range(n))
    rotating = players[1:]
    anchor = players[0]

    matches_to_create = []
    match_count = 0

    for round_idx in range(requested_rounds):
        rotated = rotating[-round_idx:] + rotating[:-round_idx] if round_idx > 0 else rotating[:]
        circle = [anchor] + rotated

        round_number = round_idx + 1
        match_index = 1

        if is_doubles:
            # Debel: n/4 meczów na rundę, każdy mecz angażuje 4 graczy.
            # k = liczba kortów = n // 4
            # Slot i-ty meczu: indeksy circle[i], circle[i+k], circle[i+2k], circle[i+3k]
            # Team A = p[circle[i]] + p[circle[i+3k]]  (participant1 + participant4)
            # Team B = p[circle[i+k]] + p[circle[i+2k]] (participant2 + participant3)
            # Konwencja spójna z generate_next_mexicano_round i generate_americano_matches.
            k = n // 4
            for i in range(k):
                pa1 = participants[circle[i]]
                pa2 = participants[circle[i + k]]
                pa3 = participants[circle[i + 2 * k]]
                pa4 = participants[circle[i + 3 * k]]
                matches_to_create.append(TournamentsMatch(
                    tournament=tournament,
                    participant1=pa1, participant2=pa4,  # Team A
                    participant3=pa2, participant4=pa3,  # Team B
                    round_number=round_number,
                    match_index=match_index,
                    status=TournamentsMatch.Status.WAITING.value,
                ))
                match_index += 1
                match_count += 1
        else:
            # Singiel: n/2 meczów na rundę, para circle[i] vs circle[n-1-i]
            for i in range(n // 2):
                p1 = participants[circle[i]]
                p2 = participants[circle[n - 1 - i]]
                matches_to_create.append(TournamentsMatch(
                    tournament=tournament,
                    participant1=p1,
                    participant2=p2,
                    round_number=round_number,
                    match_index=match_index,
                    status=TournamentsMatch.Status.WAITING.value,
                ))
                match_index += 1
                match_count += 1

    TournamentsMatch.objects.bulk_create(matches_to_create)
    fmt = 'debel' if is_doubles else 'singiel'
    logger.info(
        '[americano] Wygenerowano %d meczów (%d rund, %d graczy, %s) dla turnieju id=%d.',
        match_count, requested_rounds, n, fmt, tournament.pk,
    )
    return match_count, f'Wygenerowano {match_count} meczów Americano ({requested_rounds} rund, {n} graczy, {fmt}).'
