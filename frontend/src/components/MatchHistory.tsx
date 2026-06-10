import { useState, useMemo, useEffect, type ReactNode } from 'react';
import AddMatchForm from './AddMatchForm';
import { matchesQuery, normalize, trigramSimilarity } from '@/lib/search';

interface MatchRow {
  id: number | string;
  href: string;
  result: 'win' | 'loss' | 'draw';
  resultLetter: string;
  opponentFull: string;
  isDouble: boolean;
  isTournament: boolean;
  date: string;
  rawDate: string;   // "YYYY-MM-DD" — do sortowania
  score: string;
  setsScore: string;
  formatLabel: string;
  format: 'SNG' | 'DBL';
  typeLabel: string;
  tournamentTypeCode: string | null;
}

interface Props {
  matches: MatchRow[];
  userDisplayName: string | null;
  addMatchUrl: string;
  myId?: number;
  today?: string;
}

type FormatFilter = 'all' | 'SNG' | 'DBL';
type ResultFilter = 'all' | 'win' | 'loss';
type TypeFilter  = 'all' | 'friendly' | 'tournament';
type SortOrder   = 'desc' | 'asc';

const TOURNAMENT_TYPE_LABEL: Record<string, string> = {
  RND: 'Round Robin',
  SGL: 'Eliminacja',
  DBE: 'Elim. podwójna',
  LDR: 'Drabinka',
  AMR: 'Americano',
  SWS: 'Szwajcarski',
};

// Dodatkowe synonimy do wyszukiwania po typie turnieju (np. "mexicano" = Americano,
// "eliminacja" = Elim. podwójna)
const TOURNAMENT_TYPE_SEARCH_ALIASES: Record<string, string[]> = {
  AMR: ['mexicano', 'americano'],
  SGL: ['eliminacja', 'eliminacje'],
  DBE: ['eliminacja', 'eliminacje', 'eliminacja podwójna'],
};

// Czy zapytanie `q` pasuje do typu turnieju (kod, etykieta PL lub alias)
function matchesTournamentType(tournamentType: string | null | undefined, q: string): boolean {
  return tournamentTypeMatchRank(tournamentType, q) !== null;
}

// Ranga trafności dopasowania `q` do typu turnieju — im niższa, tym trafniejsze
// dopasowanie (0 = dokładne dopasowanie kodu/etykiety, >0 = dopasowanie przez alias,
// fuzzy dla literówek). Zwraca null, gdy brak dopasowania.
function tournamentTypeMatchRank(tournamentType: string | null | undefined, q: string): number | null {
  if (!tournamentType) return null;
  const nq = normalize(q);
  const code = normalize(tournamentType);
  if (code.includes(nq) || matchesQuery(tournamentType, q)) return 0;
  const label = TOURNAMENT_TYPE_LABEL[tournamentType];
  if (label && (normalize(label).includes(nq) || matchesQuery(label, q))) return 0;
  const aliases = TOURNAMENT_TYPE_SEARCH_ALIASES[tournamentType] ?? [];
  for (let i = 0; i < aliases.length; i++) {
    const a = normalize(aliases[i]);
    if (a.includes(nq) || nq.includes(a) || matchesQuery(aliases[i], q)) return i + 1;
    if (trigramSimilarity(nq, a) >= 0.3) return i + 1;
  }
  return null;
}

const SearchIcon = () => (
  <svg className="m-search__icon" width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
    <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
  </svg>
);

const TennisIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="10" />
    <path d="M6.3 6.3c2.4 2.4 2.4 9 0 11.4M17.7 6.3c-2.4 2.4-2.4 9 0 11.4" strokeLinecap="round" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
  </svg>
);

export default function MatchHistory({ matches, userDisplayName, addMatchUrl, myId, today }: Props) {
  const [formatFilter, setFormatFilter] = useState<FormatFilter>('all');
  const [resultFilter, setResultFilter] = useState<ResultFilter>('all');
  const [typeFilter,   setTypeFilter]   = useState<TypeFilter>('all');
  const [sortOrder,    setSortOrder]    = useState<SortOrder>('desc');
  const [search, setSearch] = useState('');
  const [showBanner, setShowBanner] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const todayStr = today ?? new Date().toISOString().slice(0, 10);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('added') === '1') {
      setShowBanner(true);
      history.replaceState({}, '', window.location.pathname);
      const t = setTimeout(() => setShowBanner(false), 6000);
      return () => clearTimeout(t);
    }
  }, []);

  useEffect(() => {
    const handleOpen = () => setShowAddModal(true);
    window.addEventListener('open-add-match-modal', handleOpen);
    if (window.location.hash === '#add-match') {
      setShowAddModal(true);
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
    return () => window.removeEventListener('open-add-match-modal', handleOpen);
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim();
    let result = matches.filter(m => {
      if (formatFilter !== 'all' && m.format !== formatFilter) return false;
      if (resultFilter !== 'all' && m.result !== resultFilter) return false;
      if (typeFilter === 'friendly'   && m.isTournament) return false;
      if (typeFilter === 'tournament' && !m.isTournament) return false;
      if (q && !matchesQuery(m.opponentFull, q) && !matchesTournamentType(m.tournamentTypeCode, q)) return false;
      return true;
    });
    if (sortOrder === 'asc') {
      result = [...result].sort((a, b) => a.rawDate.localeCompare(b.rawDate));
    }
    if (q) {
      result = [...result].sort((a, b) => {
        const rankA = tournamentTypeMatchRank(a.tournamentTypeCode, q) ?? Infinity;
        const rankB = tournamentTypeMatchRank(b.tournamentTypeCode, q) ?? Infinity;
        return rankA - rankB;
      });
    }
    return result;
  }, [matches, formatFilter, resultFilter, typeFilter, sortOrder, search]);

  const total = matches.length;
  const wins = matches.filter(m => m.result === 'win').length;
  const losses = matches.filter(m => m.result === 'loss').length;
  const winRate = total > 0 ? Math.round(wins / total * 100) : 0;

  let streak = 0;
  let streakType = '';
  if (matches.length > 0) {
    streakType = matches[0].result;
    for (const m of matches) {
      if (m.result === streakType) streak++;
      else break;
    }
  }
  const streakLetter = streakType === 'win' ? 'W' : streakType === 'loss' ? 'P' : 'R';

  function pluralMecze(n: number): string {
    if (n === 1) return '1 mecz';
    if (n >= 2 && n <= 4) return `${n} mecze`;
    return `${n} meczów`;
  }

  const hasActiveFilters = typeFilter !== 'all' || resultFilter !== 'all' || formatFilter !== 'all' || search !== '';

  function clearFilters() {
    setTypeFilter('all');
    setResultFilter('all');
    setFormatFilter('all');
    setSearch('');
  }

  return (
    <>
      {showBanner && (
        <div className="m-added-banner" role="status">
          <CheckIcon />
          Mecz został zapisany i pojawił się na liście.
        </div>
      )}

      <div className="m-stats">
        <div className="m-stat-card">
          <div className="bento-label">ROZEGRANE</div>
          <div className="m-stat-card__value">{total}</div>
          <div className="m-stat-card__sub">w sezonie</div>
        </div>
        <div className="m-stat-card m-stat-card--accent">
          <div className="bento-label">WYGRANE</div>
          <div className="m-stat-card__value" style={{ color: 'var(--tc-accent)' }}>{wins}</div>
          <div className="m-stat-card__sub">{winRate}% wszystkich</div>
        </div>
        <div className="m-stat-card">
          <div className="bento-label">PORAŻKI</div>
          <div className="m-stat-card__value">{losses}</div>
          <div className="m-stat-card__sub">{total > 0 ? Math.round(losses / total * 100) : 0}% wszystkich</div>
        </div>
        <div className="m-stat-card">
          <div className="bento-label">AKTUALNA PASSA</div>
          <div className="m-stat-card__value">
            {streak}<span className="m-stat-card__streak-letter">{streakLetter}</span>
          </div>
          <div className="m-stat-card__sub">ostatnie {pluralMecze(streak)}</div>
        </div>
      </div>

      <section className="dash-card m-table-card">
        {/* Rząd 1: tytuł + meta + search */}
        <div className="m-header-row">
          <h2 className="dash-section-title">
            Historia meczów
            <span className="section-badge">{filtered.length}</span>
            {userDisplayName && <span className="m-my-chip">Twoja historia</span>}
          </h2>
          <div className="m-search-wrap">
            <SearchIcon />
            <input
              className="m-search"
              type="search"
              placeholder="Szukaj po nazwisku…"
              autoComplete="off"
              aria-label="Szukaj po przeciwniku"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        {/* Rząd 2: filtry treści + sortowanie odseparowane */}
        <div className="m-filters-row">
          <div className="m-filter-groups">
            <LabeledFilter label="Typ">
              <SegmentedFilter
                label="Typ meczu"
                options={[
                  { value: 'all',        label: 'Wszystkie'   },
                  { value: 'friendly',   label: 'Towarzyskie' },
                  { value: 'tournament', label: 'Turniejowe'  },
                ]}
                active={typeFilter}
                onChange={v => setTypeFilter(v as TypeFilter)}
              />
            </LabeledFilter>
            <LabeledFilter label="Wynik">
              <SegmentedFilter
                label="Wynik"
                options={[
                  { value: 'all',  label: 'Wszystkie' },
                  { value: 'win',  label: 'Wygrane'   },
                  { value: 'loss', label: 'Porażki'   },
                ]}
                active={resultFilter}
                onChange={v => setResultFilter(v as ResultFilter)}
              />
            </LabeledFilter>
            <LabeledFilter label="Format">
              <SegmentedFilter
                label="Format"
                options={[
                  { value: 'all', label: 'Wszystkie' },
                  { value: 'SNG', label: 'Singiel'   },
                  { value: 'DBL', label: 'Debel'     },
                ]}
                active={formatFilter}
                onChange={v => setFormatFilter(v as FormatFilter)}
              />
            </LabeledFilter>
          </div>
          <div className="m-sort-group">
            <LabeledFilter label="Sortuj">
              <SegmentedFilter
                label="Sortowanie"
                options={[
                  { value: 'desc', label: 'Najnowsze'  },
                  { value: 'asc',  label: 'Najstarsze' },
                ]}
                active={sortOrder}
                onChange={v => setSortOrder(v as SortOrder)}
              />
            </LabeledFilter>
          </div>
        </div>

        <div className="m-table-head">
          <span>WYNIK</span>
          <span>PRZECIWNIK</span>
          <span>SETY</span>
          <span>FORMAT</span>
          <span className="m-th-right">DATA</span>
        </div>

        {filtered.length === 0 ? (
          <div className="dash-empty-block">
            <div className="dash-empty-block__icon" aria-hidden="true">
              <TennisIcon />
            </div>
            {total === 0 ? (
              <>
                <p className="dash-empty-block__title">Brak historii meczów</p>
                <p className="dash-empty-block__sub">Nie masz jeszcze żadnych zapisanych meczów. Dodaj swój pierwszy mecz towarzyski lub dołącz do turnieju.</p>
                <div className="dash-empty-block__links">
                  <button
                    className="dash-btn-primary"
                    style={{ border: 'none', cursor: 'pointer' }}
                    onClick={() => myId ? setShowAddModal(true) : (window.location.href = addMatchUrl)}
                  >
                    Dodaj pierwszy mecz
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="dash-empty-block__title">Brak wyników dla tych filtrów</p>
                <p className="dash-empty-block__sub">Żaden z Twoich {pluralMecze(total)} nie pasuje do wybranych kryteriów.</p>
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
            {filtered.map(m => (
              <a key={m.id} className="m-row" href={m.href}>
                <div className={`m-result-badge m-result-badge--${m.result}`}>{m.resultLetter}</div>
                <div className="m-opponent">
                  <div className={`m-opponent__name${m.isDouble ? ' m-opponent__name--dbl' : ''}`}>{m.opponentFull}</div>
                  <div className="m-opponent__type">{m.typeLabel}</div>
                </div>
                <div className="m-sets">
                  <span className={`m-sets__score m-sets__score--${m.result}`}>{m.setsScore}</span>
                  <span className="m-sets__detail">{m.score}</span>
                </div>
                <div className="m-format">{m.formatLabel}</div>
                <div className="m-date">{m.date}</div>
              </a>
            ))}
          </div>
        )}
      </section>

      {showAddModal && myId && (
        <div className="res-popup-backdrop" role="dialog" aria-modal="true"
          onClick={e => { if (e.target === e.currentTarget) setShowAddModal(false); }}>
          <div className="res-popup" style={{ maxWidth: 620 }}>
            <div className="res-popup__header">
              <div>
                <div className="res-popup__title">Dodaj mecz towarzyski</div>
                <div className="res-popup__subtitle">Zapisz wynik rozegranego meczu</div>
              </div>
              <button className="res-popup__close" aria-label="Zamknij" onClick={() => setShowAddModal(false)}>
                <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
                </svg>
              </button>
            </div>
            <div className="res-popup__body">
              <AddMatchForm
                myId={myId}
                today={todayStr}
                matchesUrl={addMatchUrl.replace(/\/add\/?$/, '')}
                isModal={true}
                onClose={() => setShowAddModal(false)}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function LabeledFilter({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="m-labeled-filter">
      <span className="m-filter-label">{label}</span>
      {children}
    </div>
  );
}

function SegmentedFilter({
  label,
  options,
  active,
  onChange,
}: {
  label: string;
  options: { value: string; label: string }[];
  active: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="m-segmented" role="group" aria-label={label}>
      {options.map(o => (
        <button
          key={o.value}
          type="button"
          className={`m-seg${active === o.value ? ' m-seg--active' : ''}`}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
