"""
Ranking calculator — precomputed snapshot logic.

Extracted from apps/rankings/views.py (the original "query hell" live calculation).
Produces identical results but runs once and saves to PlayerRanking table.
"""
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum, F, Case, When, IntegerField, Value, Subquery, OuterRef, DecimalField
from django.db.models.functions import Coalesce, ExtractYear

from apps.tournaments.models import Tournament, TournamentsMatch, Participant
from apps.rankings.models import TournamentRankPoints, PlayerRanking


def _build_filters(match_type, season):
    """Return (finished_tournament_filter, completed_match_filter) Q objects."""
    ft = (
        Q(tournament__status=Tournament.Status.FINISHED.value) &
        Q(tournament__end_date__isnull=False) &
        Q(tournament__match_format=match_type)
    )
    if season:
        ft &= Q(tournament__end_date__year=season)
    cm = Q(status=TournamentsMatch.Status.COMPLETED.value)
    return ft, cm


def calculate_rankings(match_type='SNG', season=None):
    """
    Calculate ranking for all players for a given match_type + season.
    Returns a list of dicts ready to upsert into PlayerRanking.
    """
    ft, cm = _build_filters(match_type, season)

    # --- Stats subqueries (same logic as original views.py) ---

    def _sum_scores(role, p1_fields, p2_fields, extra_filter=Q()):
        """Sum score fields for a player in a given role (participant1 or participant2)."""
        user_filter = Q(**{f'{role}__user': OuterRef('pk')})
        fields = p1_fields if role == 'participant1' else p2_fields
        return Subquery(
            TournamentsMatch.objects.filter(ft & cm & user_filter & extra_filter)
            .order_by().values(f'{role}__user')
            .annotate(total=Sum(Coalesce(F(fields[0]), 0) + Coalesce(F(fields[1]), 0) + Coalesce(F(fields[2]), 0)))
            .values('total')[:1],
            output_field=IntegerField()
        )

    def _count_sets(role, win, extra_filter=Q()):
        """Count sets won or lost for a player in a given role."""
        user_filter = Q(**{f'{role}__user': OuterRef('pk')})
        if role == 'participant1':
            conds = [
                (Q(set1_p1_score__gt=F('set1_p2_score')) if win else Q(set1_p1_score__lt=F('set1_p2_score'))),
                (Q(set2_p1_score__gt=F('set2_p2_score')) if win else Q(set2_p1_score__lt=F('set2_p2_score'))),
                (Q(set3_p1_score__gt=F('set3_p2_score')) if win else Q(set3_p1_score__lt=F('set3_p2_score'))),
            ]
        else:
            conds = [
                (Q(set1_p2_score__gt=F('set1_p1_score')) if win else Q(set1_p2_score__lt=F('set1_p1_score'))),
                (Q(set2_p2_score__gt=F('set2_p1_score')) if win else Q(set2_p2_score__lt=F('set2_p1_score'))),
                (Q(set3_p2_score__gt=F('set3_p1_score')) if win else Q(set3_p2_score__lt=F('set3_p1_score'))),
            ]
        return Subquery(
            TournamentsMatch.objects.filter(ft & cm & user_filter & extra_filter)
            .order_by().values(f'{role}__user')
            .annotate(total=Sum(
                Case(When(conds[0], then=1), default=0, output_field=IntegerField()) +
                Case(When(conds[1], then=1), default=0, output_field=IntegerField()) +
                Case(When(conds[2], then=1), default=0, output_field=IntegerField())
            ))
            .values('total')[:1],
            output_field=IntegerField()
        )

    def _count_matches(role):
        user_filter = Q(**{f'{role}__user': OuterRef('pk')})
        return Subquery(
            TournamentsMatch.objects.filter(ft & cm & user_filter)
            .order_by().values(f'{role}__user')
            .annotate(count=Count('id')).values('count')[:1],
            output_field=IntegerField()
        )

    # Games
    gw_p1 = _sum_scores('participant1', ['set1_p1_score', 'set2_p1_score', 'set3_p1_score'], [])
    gw_p2 = _sum_scores('participant2', [], ['set1_p2_score', 'set2_p2_score', 'set3_p2_score'])
    gl_p1 = _sum_scores('participant1', ['set1_p2_score', 'set2_p2_score', 'set3_p2_score'], [])
    gl_p2 = _sum_scores('participant2', [], ['set1_p1_score', 'set2_p1_score', 'set3_p1_score'])

    # Sets
    sw_p1 = _count_sets('participant1', win=True)
    sw_p2 = _count_sets('participant2', win=True)
    sl_p1 = _count_sets('participant1', win=False)
    sl_p2 = _count_sets('participant2', win=False)

    # Matches played
    mp1 = _count_matches('participant1')
    mp2 = _count_matches('participant2')

    # Matches won (via Participant.won_matches relation)
    matches_won_sq = Count(
        'tournament_participations__won_matches',
        filter=Q(tournament_participations__won_matches__in=Subquery(
            TournamentsMatch.objects.filter(ft).values('pk')
        )),
        distinct=True
    )

    # Highest tournament rank for multiplier lookup
    trp_filter = dict(
        tournament__status=Tournament.Status.FINISHED.value,
        tournament__end_date__isnull=False,
        tournament__match_format=match_type,
    )
    if season:
        trp_filter['tournament__end_date__year'] = season

    highest_rank_sq = Subquery(
        Participant.objects.filter(user=OuterRef('pk'), **trp_filter)
        .order_by('-tournament__rank').values('tournament__rank')[:1],
        output_field=IntegerField()
    )

    def _multiplier(field, default):
        return Coalesce(
            Subquery(
                TournamentRankPoints.objects.filter(rank=OuterRef('user_highest_rank')).values(field)[:1],
                output_field=DecimalField()
            ),
            Value(default, output_field=DecimalField())
        )

    qs = (
        User.objects
        .annotate(matches_won=matches_won_sq)
        .annotate(
            matches_played=Coalesce(mp1, 0) + Coalesce(mp2, 0),
            _gw1=Coalesce(gw_p1, 0), _gw2=Coalesce(gw_p2, 0),
            _gl1=Coalesce(gl_p1, 0), _gl2=Coalesce(gl_p2, 0),
            _sw1=Coalesce(sw_p1, 0), _sw2=Coalesce(sw_p2, 0),
            _sl1=Coalesce(sl_p1, 0), _sl2=Coalesce(sl_p2, 0),
        )
        .annotate(
            total_games_won=F('_gw1') + F('_gw2'),
            total_games_lost=F('_gl1') + F('_gl2'),
            total_sets_won=F('_sw1') + F('_sw2'),
            total_sets_lost=F('_sl1') + F('_sl2'),
        )
        .annotate(
            matches_lost=F('matches_played') - F('matches_won'),
            user_highest_rank=highest_rank_sq,
        )
        .annotate(
            _mul_win=_multiplier('match_win_multiplier', 1.0),
            _mul_sw=_multiplier('set_win_multiplier', 0.5),
            _mul_sl=_multiplier('set_loss_multiplier', -0.5),
            _mul_gw=_multiplier('game_win_multiplier', 0.1),
            _mul_gl=_multiplier('game_loss_multiplier', -0.1),
            _mul_bonus=_multiplier('participation_bonus', 0.0),
        )
        .annotate(
            total_points=(
                F('_mul_bonus') +
                F('matches_won') * F('_mul_win') +
                F('total_sets_won') * F('_mul_sw') +
                F('total_sets_lost') * F('_mul_sl') +
                F('total_games_won') * F('_mul_gw') +
                F('total_games_lost') * F('_mul_gl')
            )
        )
        .filter(matches_played__gt=0)
        .order_by('-total_points', '-matches_won')
        .values(
            'pk', 'total_points', 'matches_won', 'matches_lost', 'matches_played',
            'total_sets_won', 'total_sets_lost', 'total_games_won', 'total_games_lost',
        )
    )

    results = []
    for pos, row in enumerate(qs, start=1):
        results.append({
            'user_id': row['pk'],
            'match_type': match_type,
            'season': season,
            'position': pos,
            'points': row['total_points'] or 0,
            'matches_won': row['matches_won'] or 0,
            'matches_lost': row['matches_lost'] or 0,
            'matches_played': row['matches_played'] or 0,
            'sets_won': row['total_sets_won'] or 0,
            'sets_lost': row['total_sets_lost'] or 0,
            'games_won': row['total_games_won'] or 0,
            'games_lost': row['total_games_lost'] or 0,
        })
    return results


def rebuild_rankings(match_type=None, season=None):
    """
    Rebuild precomputed PlayerRanking snapshots.

    If match_type/season are None, rebuilds ALL combinations found in finished tournaments.
    """
    from django.db.models.functions import ExtractYear as EY

    combos = set()

    if match_type and season is not None:
        combos.add((match_type, season))
    elif match_type:
        years = (
            Tournament.objects
            .filter(status=Tournament.Status.FINISHED.value, end_date__isnull=False, match_format=match_type)
            .annotate(yr=EY('end_date')).values_list('yr', flat=True).distinct()
        )
        combos.add((match_type, None))  # all-time
        for y in years:
            combos.add((match_type, y))
    else:
        for mt in ('SNG', 'DBL'):
            years = (
                Tournament.objects
                .filter(status=Tournament.Status.FINISHED.value, end_date__isnull=False, match_format=mt)
                .annotate(yr=EY('end_date')).values_list('yr', flat=True).distinct()
            )
            combos.add((mt, None))
            for y in years:
                combos.add((mt, y))

    total = 0
    for mt, yr in combos:
        rows = calculate_rankings(match_type=mt, season=yr)
        for row in rows:
            lookup = {
                'user_id': row['user_id'],
                'match_type': row['match_type'],
                'season': row['season'],
            }
            defaults = {k: v for k, v in row.items() if k not in ('user_id', 'match_type', 'season')}
            try:
                obj = PlayerRanking.objects.get(**lookup)
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.save()
            except PlayerRanking.DoesNotExist:
                PlayerRanking.objects.create(**lookup, **defaults)
        total += len(rows)

    return total
