import { useState, useMemo, useEffect } from 'react';

interface MatchRow {
  id: number | string;
  href: string;
  result: 'win' | 'loss' | 'draw';
  resultLetter: string;
  opponentFull: string;
  isDouble: boolean;
  date: string;
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
}

type FormatFilter = 'all' | 'SNG' | 'DBL';
type ResultFilter = 'all' | 'win' | 'loss';

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

export default function MatchHistory({ matches, userDisplayName, addMatchUrl }: Props) {
  const [formatFilter, setFormatFilter] = useState<FormatFilter>('all');
  const [resultFilter, setResultFilter] = useState<ResultFilter>('all');
  const [search, setSearch] = useState('');
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('added') === '1') {
      setShowBanner(true);
      history.replaceState({}, '', window.location.pathname);
      const t = setTimeout(() => setShowBanner(false), 6000);
      return () => clearTimeout(t);
    }
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return matches.filter(m => {
      if (formatFilter !== 'all' && m.format !== formatFilter) return false;
      if (resultFilter !== 'all' && m.result !== resultFilter) return false;
      if (q && !m.opponentFull.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [matches, formatFilter, resultFilter, search]);

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
                <a href={addMatchUrl} className="dash-btn-primary">Dodaj pierwszy mecz</a>
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
