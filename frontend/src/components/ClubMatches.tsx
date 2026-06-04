// ClubMatches.tsx — React island: mecze klubowe (scope club w /matches).
// Scope: tylko zakończone mecze turniejowe (COMPLETED, turniej ACT/FIN).
// Mecze towarzyskie innych użytkowników celowo poza zakresem — osobny v2.

import { useState, useMemo } from 'react';
import type { ClubMatchEntry } from '@/lib/api';

type FormatFilter = 'all' | 'SNG' | 'DBL';
type SortOrder   = 'desc' | 'asc';

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

function matchScore(m: ClubMatchEntry): string {
  return [m.set1, m.set2, m.set3].filter(Boolean).join(', ') || '—';
}

function matchup(m: ClubMatchEntry): string {
  if (m.match_double) {
    const team1 = [m.p1, m.p3].filter(Boolean).join(' / ') || '?';
    const team2 = [m.p2, m.p4].filter(Boolean).join(' / ') || '?';
    return `${team1} vs ${team2}`;
  }
  return `${m.p1 ?? '?'} vs ${m.p2 ?? '?'}`;
}

export default function ClubMatches({ matches, tournamentsUrl }: Props) {
  const [formatFilter, setFormatFilter] = useState<FormatFilter>('all');
  const [sortOrder,    setSortOrder]    = useState<SortOrder>('desc');
  const [search,       setSearch]       = useState('');

  const filtered = useMemo(() => {
    let result = matches;
    if (formatFilter === 'SNG') result = result.filter(m => !m.match_double);
    if (formatFilter === 'DBL') result = result.filter(m => m.match_double);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(m =>
        [m.p1, m.p2, m.p3, m.p4, m.tournament_name].some(v => v?.toLowerCase().includes(q))
      );
    }
    if (sortOrder === 'asc') {
      result = [...result].sort((a, b) => (a.match_date ?? '').localeCompare(b.match_date ?? ''));
    }
    return result;
  }, [matches, formatFilter, sortOrder, search]);

  return (
    <section className="dash-card m-table-card">

      {/* Rząd 1: nagłówek + search */}
      <div className="m-header-row">
        <div>
          <h2 className="dash-section-title">
            Mecze klubu
            <span className="section-badge">{filtered.length}</span>
          </h2>
          <p className="cm-scope-hint">Zakończone mecze turniejowe rozgrywane w klubie</p>
        </div>
        <div className="m-search-wrap">
          <SearchIcon />
          <input
            className="m-search"
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

      {/* Nagłówek tabeli */}
      <div className="m-table-head cm-table-head">
        <span>TURNIEJ</span>
        <span>MECZ</span>
        <span>WYNIK</span>
        <span className="m-th-right">DATA</span>
      </div>

      {filtered.length === 0 ? (
        <div className="dash-empty-block">
          <p className="dash-empty-block__title">Brak meczów</p>
          <p className="dash-empty-block__sub">
            {search.trim()
              ? 'Brak wyników dla podanej frazy.'
              : 'Żadne zakończone mecze turniejowe nie pasują do filtrów.'}
          </p>
          <div className="dash-empty-block__links">
            <a href={tournamentsUrl} className="dash-link-sm">Zobacz turnieje →</a>
          </div>
        </div>
      ) : (
        <ul className="m-table-body" role="list" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {filtered.map(m => (
            <li key={m.id} className="m-row cm-row">
              <div className="cm-row__tournament">
                <a href={`${tournamentsUrl}/${m.tournament_id}`} className="cm-row__tourn-link">
                  {m.tournament_name}
                </a>
                <span className="m-badge m-badge--type">
                  {TOURNAMENT_TYPE_LABEL[m.tournament_type] ?? m.tournament_type}
                </span>
              </div>
              <div className="cm-row__matchup">{matchup(m)}</div>
              <div className="cm-row__score">
                <span className="m-score">{matchScore(m)}</span>
                {m.winner && (
                  <span className="cm-row__winner">
                    <svg width="10" height="10" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style={{ color: 'var(--tc-accent)' }}>
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                    </svg>
                    {m.winner}
                  </span>
                )}
              </div>
              <div className="cm-row__date">{formatDate(m.match_date)}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
