// ClubMatches.tsx — React island: mecze klubowe (scope club w /matches).

import { useState, useMemo, useCallback, useRef } from 'react';
import type { ClubMatchEntry, ClubMatchSource } from '@/lib/api';

function getApiBase(): string {
  return (window as any)._API ?? '';
}

type FormatFilter  = 'all' | 'SNG' | 'DBL';
type SortOrder     = 'desc' | 'asc';

const TOURNAMENT_TYPE_LABEL: Record<string, string> = {
  RND: 'Round Robin',
  SGL: 'Eliminacja',
  DBE: 'Elim. podwójna',
  LDR: 'Drabinka',
  AMR: 'Americano',
  SWS: 'Szwajcarski',
};

interface Props {
  matches: ClubMatchEntry[];
  tournamentsUrl: string;
  matchesUrl: string;
}

const SearchIcon = () => (
  <svg className="m-search__icon" width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
    <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
  </svg>
);

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso + 'T12:00:00');
  return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
}

function parseSet(s: string | null): [number, number] | null {
  if (!s) return null;
  const [a, b] = s.split(':').map(n => parseInt(n, 10));
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return [a, b];
}

// Agregat setów: zlicza wygrane sety per strona z set1/set2/set3.
// Zwraca "2:1" (p1:p2) + listę pojedynczych setów do podtytułu.
function aggregateSets(m: ClubMatchEntry): { aggregate: string; detail: string } {
  const sets = [parseSet(m.set1), parseSet(m.set2), parseSet(m.set3)].filter(
    (s): s is [number, number] => s !== null
  );
  if (sets.length === 0) return { aggregate: '—', detail: '' };
  let p1 = 0, p2 = 0;
  for (const [a, b] of sets) {
    if (a > b) p1++;
    else if (b > a) p2++;
  }
  return {
    aggregate: `${p1}:${p2}`,
    detail: sets.map(([a, b]) => `${a}:${b}`).join(', '),
  };
}

// "Marek Kowalski" → "M. Kowalski". Jeden segment (np. username) bez zmian.
function shortName(name: string | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return parts[0] ?? '?';
  return `${parts[0][0]}. ${parts.slice(1).join(' ')}`;
}

// Zwraca dwie strony osobno, do JSX (chcemy umieścić ikonkę przy zwycięskiej).
function teamNames(m: ClubMatchEntry): { teamA: string; teamB: string } {
  if (m.match_double) {
    const teamA = [m.p1, m.p3].filter(Boolean).map(shortName).join(' / ') || '?';
    const teamB = [m.p2, m.p4].filter(Boolean).map(shortName).join(' / ') || '?';
    return { teamA, teamB };
  }
  return { teamA: m.p1 ?? '?', teamB: m.p2 ?? '?' };
}

// Inicjały z imię+nazwisko (lub jednego słowa).
function initials(name: string | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function ClubMatches({ matches: initialMatches, tournamentsUrl, matchesUrl }: Props) {
  const [sourceFilter, setSourceFilter] = useState<ClubMatchSource>('tournament');
  const [formatFilter, setFormatFilter] = useState<FormatFilter>('all');
  const [sortOrder,    setSortOrder]    = useState<SortOrder>('desc');
  const [search,       setSearch]       = useState('');

  const [allMatches, setAllMatches]   = useState<ClubMatchEntry[]>(initialMatches);
  const [loading,    setLoading]      = useState(false);
  const [fetchError, setFetchError]   = useState(false);
  const sourceFetchedRef = useRef<Record<string, boolean>>({ tournament: true });

  const fetchSource = useCallback((src: ClubMatchSource) => {
    if (sourceFetchedRef.current[src]) return;
    sourceFetchedRef.current[src] = true;
    setLoading(true);
    setFetchError(false);
    fetch(`${getApiBase()}/api/matches/club/?limit=100&source=${src}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((data: ClubMatchEntry[]) => {
        setAllMatches(prev => {
          const ids = new Set(data.map(m => `${m.source}-${m.id}`));
          const kept = prev.filter(m => !ids.has(`${m.source}-${m.id}`));
          return [...kept, ...data];
        });
      })
      .catch(() => setFetchError(true))
      .finally(() => setLoading(false));
  }, []);

  const handleSourceChange = (src: ClubMatchSource) => {
    setSourceFilter(src);
    fetchSource(src);
  };

  const hasActiveFilters = formatFilter !== 'all' || search !== '';

  function clearFilters() {
    setFormatFilter('all');
    setSearch('');
  }

  const filtered = useMemo(() => {
    let result = allMatches.filter(m => {
      if (sourceFilter === 'tournament') return m.source === 'tournament';
      if (sourceFilter === 'friendly')   return m.source === 'friendly';
      return true;
    });
    if (formatFilter === 'SNG') result = result.filter(m => !m.match_double);
    if (formatFilter === 'DBL') result = result.filter(m => m.match_double);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(m =>
        [m.p1, m.p2, m.p3, m.p4, m.tournament_name].some(v => v?.toLowerCase().includes(q))
      );
    }
    result = [...result].sort((a, b) => {
      const cmp = (b.match_date ?? '').localeCompare(a.match_date ?? '');
      return sortOrder === 'asc' ? -cmp : cmp;
    });
    return result;
  }, [allMatches, sourceFilter, formatFilter, sortOrder, search]);

  const sourceMatchCount = allMatches.filter(m =>
    sourceFilter === 'all' || m.source === sourceFilter
  ).length;

  const scopeHint =
    sourceFilter === 'tournament' ? 'Zakończone mecze turniejowe rozgrywane w klubie' :
    sourceFilter === 'friendly'   ? 'Mecze towarzyskie wszystkich graczy klubu' :
                                    'Mecze turniejowe i towarzyskie rozgrywane w klubie';

  return (
    <section className="dash-card m-table-card">

      {/* Rząd 1: nagłówek + search */}
      <div className="m-header-row">
        <div>
          <h2 className="dash-section-title">
            Mecze klubu
            {loading
              ? <span className="section-badge cm-loading-badge">...</span>
              : <span className="section-badge">{filtered.length}</span>
            }
          </h2>
          <p className="cm-scope-hint">{scopeHint}</p>
        </div>
        <div className="m-search-wrap">
          <SearchIcon />
          <input
            className="m-search m-search--wide"
            type="search"
            placeholder="Szukaj gracza lub turnieju…"
            autoComplete="off"
            aria-label="Szukaj meczów klubowych"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Rząd 2: filtry + sort */}
      <div className="m-filters-row">
        <div className="m-filter-groups">
          <div className="m-labeled-filter">
            <span className="m-filter-label">Źródło</span>
            <div className="m-segmented" role="group" aria-label="Źródło meczów">
              {(['all', 'friendly', 'tournament'] as ClubMatchSource[]).map(s => (
                <button
                  key={s}
                  type="button"
                  className={`m-seg${sourceFilter === s ? ' m-seg--active' : ''}`}
                  onClick={() => handleSourceChange(s)}
                >
                  {s === 'tournament' ? 'Turniejowe' : s === 'friendly' ? 'Towarzyskie' : 'Wszystkie'}
                </button>
              ))}
            </div>
          </div>
          <div className="m-labeled-filter">
            <span className="m-filter-label">Format</span>
            <div className="m-segmented" role="group" aria-label="Format meczu">
              {(['all', 'SNG', 'DBL'] as FormatFilter[]).map(f => (
                <button
                  key={f}
                  type="button"
                  className={`m-seg${formatFilter === f ? ' m-seg--active' : ''}`}
                  onClick={() => setFormatFilter(f)}
                >
                  {f === 'all' ? 'Wszystkie' : f === 'SNG' ? 'Singiel' : 'Debel'}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="m-sort-group">
          <div className="m-labeled-filter">
            <span className="m-filter-label">Sortuj</span>
            <div className="m-segmented" role="group" aria-label="Sortowanie">
              {(['desc', 'asc'] as SortOrder[]).map(s => (
                <button
                  key={s}
                  type="button"
                  className={`m-seg${sortOrder === s ? ' m-seg--active' : ''}`}
                  onClick={() => setSortOrder(s)}
                >
                  {s === 'desc' ? 'Najnowsze' : 'Najstarsze'}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {fetchError && (
        <div className="cm-fetch-error">
          Nie udało się pobrać meczów. Odśwież stronę lub spróbuj ponownie.
        </div>
      )}

      {/* Nagłówek tabeli — identyczny układ jak mine */}
      <div className="m-table-head">
        <span>WYNIK</span>
        <span>MECZ</span>
        <span>SETY</span>
        <span>FORMAT</span>
        <span className="m-th-right">DATA</span>
      </div>

      {filtered.length === 0 && !loading ? (
        <div className="dash-empty-block">
          {sourceMatchCount === 0 ? (
            <>
              <p className="dash-empty-block__title">
                {sourceFilter === 'friendly' ? 'Brak meczów towarzyskich' : 'Brak meczów turniejowych'}
              </p>
              <p className="dash-empty-block__sub">
                {sourceFilter === 'friendly'
                  ? 'Nikt w klubie nie rozegrał jeszcze żadnego meczu towarzyskiego.'
                  : 'W klubie nie ma jeszcze żadnych zakończonych meczów turniejowych. Dołącz do turnieju, żeby zobaczyć wyniki.'}
              </p>
              {sourceFilter !== 'friendly' && (
                <div className="dash-empty-block__links">
                  <a href={tournamentsUrl} className="dash-link-sm">Przeglądaj turnieje →</a>
                </div>
              )}
            </>
          ) : (
            <>
              <p className="dash-empty-block__title">Brak wyników dla tych filtrów</p>
              <p className="dash-empty-block__sub">Żaden mecz nie pasuje do wybranych kryteriów.</p>
              {hasActiveFilters && (
                <div className="dash-empty-block__links">
                  <button className="dash-link-sm" style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={clearFilters}>
                    Wyczyść filtry
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="m-table-body">
          {filtered.map(m => {
            const { aggregate, detail } = aggregateSets(m);
            const fmt        = m.match_double ? 'Debel' : 'Singiel';
            const isFriendly = m.source === 'friendly';
            const typeLabel  = isFriendly ? 'Towarzyski' : (TOURNAMENT_TYPE_LABEL[m.tournament_type] ?? m.tournament_type);
            const subtitle   = isFriendly ? 'Mecz towarzyski' : (m.tournament_name ?? '');
            const rowHref    = isFriendly
              ? `${matchesUrl}/${m.id}`
              : `${tournamentsUrl}/${m.tournament_id}`;
            const winnerInitials = initials(m.winner);
            const { teamA, teamB } = teamNames(m);
            const winSide = m.winner_side;
            const [aggA, aggB] = aggregate.split(':');
            return (
              <a key={`${m.source}-${m.id}`} className="m-row" href={rowHref}>
                {/* kolumna 1: badge z inicjałami zwycięzcy */}
                <div
                  className="m-result-badge m-result-badge--neutral"
                  title={m.winner ? `Zwycięzca: ${m.winner}` : 'Brak zwycięzcy'}
                >
                  {winnerInitials}
                </div>
                {/* kolumna 2: team A vs team B z pucharkiem przy wygranej */}
                <div className="m-opponent">
                  <div className={`m-opponent__name${m.match_double ? ' m-opponent__name--dbl' : ''}`}>
                    <span className={winSide === 'p1' ? 'cm-team--win' : undefined}>
                      {teamA}
                      {winSide === 'p1' && <span className="cm-trophy" aria-label="zwycięzca" title="Zwycięzca">🏆</span>}
                    </span>
                    <span className="cm-vs"> vs </span>
                    <span className={winSide === 'p2' ? 'cm-team--win' : undefined}>
                      {teamB}
                      {winSide === 'p2' && <span className="cm-trophy" aria-label="zwycięzca" title="Zwycięzca">🏆</span>}
                    </span>
                  </div>
                  <div className="m-opponent__type">
                    {subtitle}
                    {typeLabel && !isFriendly && <span className="cm-type-sep"> · {typeLabel}</span>}
                    {isFriendly && <span className="cm-type-sep cm-type-friendly"> · Towarzyski</span>}
                  </div>
                </div>
                {/* kolumna 3: agregat setów z kolorem per strona + szczegóły */}
                <div className="m-sets">
                  {aggB !== undefined ? (
                    <span className="m-sets__score">
                      <span className={winSide === 'p1' ? 'cm-agg--win' : 'cm-agg--lose'}>{aggA}</span>
                      <span className="cm-agg-sep">:</span>
                      <span className={winSide === 'p2' ? 'cm-agg--win' : 'cm-agg--lose'}>{aggB}</span>
                    </span>
                  ) : (
                    <span className="m-sets__score m-sets__score--draw">{aggregate}</span>
                  )}
                  {detail && <span className="m-sets__detail">{detail}</span>}
                </div>
                {/* kolumna 4: format */}
                <div className="m-format">{fmt}</div>
                {/* kolumna 5: data */}
                <div className="m-date">{formatDate(m.match_date)}</div>
              </a>
            );
          })}
        </div>
      )}
    </section>
  );
}
