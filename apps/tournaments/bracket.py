"""
bracket.py — logika drabinki single elimination dla Tennis Club.

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

Edge case'y obsługiwane:
  - BYE (participant2=None, winner=participant1): traktowane jak normalny awans
  - Re-edycja wyniku: advance jest idempotentny — nadpisuje slot tylko jeśli zmiana winnera
  - Brak kolejnej rundy: tworzy pusty TournamentsMatch z WAI
  - Mecze o 3. miejsce: generowane przez ensure_third_place_match() gdy obaj przegrani z SF znani
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
            is_bye = m.participant2 is None and m.status == TournamentsMatch.Status.COMPLETED.value
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
