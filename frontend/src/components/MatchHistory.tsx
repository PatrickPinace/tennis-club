import { useState, useMemo, useEffect } from 'react';
import AddMatchForm from './AddMatchForm';

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
}

interface Props {
  matches: MatchRow[];
  userDisplayName: string | null;
  addMatchUrl: string;
  today?: string;
}

type FormatFilter = 'all' | 'SNG' | 'DBL';
type ResultFilter = 'all' | 'win' | 'loss';
type TypeFilter  = 'all' | 'friendly' | 'tournament';
type SortOrder   = 'desc' | 'asc';

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
    const q = search.toLowerCase();
    let result = matches.filter(m => {
      if (formatFilter !== 'all' && m.format !== formatFilter) return false;
      if (resultFilter !== 'all' && m.result !== resultFilter) return false;
      if (typeFilter === 'friendly'   && m.isTournament) return false;
      if (typeFilter === 'tournament' && !m.isTournament) return false;
      if (q && !m.opponentFull.toLowerCase().includes(q)) return false;
      return true;
    });
    if (sortOrder === 'asc') {
      result = [...result].sort((a, b) => a.rawDate.localeCompare(b.rawDate));
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
          <div className="m-stat-card__sub">ostatnie {streak} mecze</div>
        </div>
      </div>

      <section className="dash-card m-table-card">
        <div className="dash-section-header">
          <h2 className="dash-section-title">
            Historia meczów
            <span className="section-badge">{filtered.length}</span>
            {userDisplayName && <span className="m-my-chip">Twoja historia</span>}
          </h2>
          <div className="m-filter-groups">
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
            <SegmentedFilter
              label="Typ"
              options={[
                { value: 'all',        label: 'Wszystkie'   },
                { value: 'friendly',   label: 'Towarzyskie' },
                { value: 'tournament', label: 'Turniejowe'  },
              ]}
              active={typeFilter}
              onChange={v => setTypeFilter(v as TypeFilter)}
            />
            <SegmentedFilter
              label="Format"
              options={[
                { value: 'all', label: 'Wszystkie' },
                { value: 'SNG', label: 'Singiel' },
                { value: 'DBL', label: 'Debel' },
              ]}
              active={formatFilter}
              onChange={v => setFormatFilter(v as FormatFilter)}
            />
            <SegmentedFilter
              label="Wynik"
              options={[
                { value: 'all', label: 'Wszystkie' },
                { value: 'win', label: 'Wygrane' },
                { value: 'loss', label: 'Porażki' },
              ]}
              active={resultFilter}
              onChange={v => setResultFilter(v as ResultFilter)}
            />
            <SegmentedFilter
              label="Sortuj"
              options={[
                { value: 'desc', label: 'Najnowsze' },
                { value: 'asc',  label: 'Najstarsze' },
              ]}
              active={sortOrder}
              onChange={v => setSortOrder(v as SortOrder)}
            />
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
            <p className="dash-empty-block__title">Brak meczów</p>
            <p className="dash-empty-block__sub">
              {total === 0
                ? 'Nie rozegrałeś jeszcze żadnych meczów lub nie jesteś zalogowany.'
                : 'Brak meczów pasujących do wybranych filtrów.'}
            </p>
            {total === 0 && (
              <div className="dash-empty-block__links">
                <button
                  className="dash-btn-primary"
                  style={{ border: 'none', cursor: 'pointer' }}
                  onClick={() => myId ? setShowAddModal(true) : (window.location.href = addMatchUrl)}
                >
                  Dodaj pierwszy mecz
                </button>
              </div>
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
