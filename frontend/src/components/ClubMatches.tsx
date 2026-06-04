// ClubMatches.tsx — React island: mecze klubowe (scope club w /matches).
// Pokazuje tylko zakończone mecze turniejowe — wyniki są z definicji publiczne.
// Mecze towarzyskie innych użytkowników celowo poza zakresem.

import { useState, useMemo } from 'react';
import type { ClubMatchEntry } from '@/lib/api';

type FormatFilter = 'all' | 'SNG' | 'DBL';

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
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    let result = matches;
    if (formatFilter === 'SNG') result = result.filter(m => !m.match_double);
    if (formatFilter === 'DBL') result = result.filter(m => m.match_double);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(m =>
        [m.p1, m.p2, m.p3, m.p4, m.tournament_name].some(
          v => v?.toLowerCase().includes(q)
        )
      );
    }
    return result;
  }, [matches, formatFilter, search]);

  return (
    <div className="cm-wrap">
      {/* Toolbar */}
      <div className="m-toolbar">
        <div className="m-seg" role="group" aria-label="Format meczu">
          {(['all', 'SNG', 'DBL'] as FormatFilter[]).map(f => (
            <button
              key={f}
              type="button"
              className={`m-seg__btn${formatFilter === f ? ' m-seg__btn--active' : ''}`}
              onClick={() => setFormatFilter(f)}
            >
              {f === 'all' ? 'Wszystkie' : f === 'SNG' ? 'Singiel' : 'Debel'}
            </button>
          ))}
        </div>
        <div className="m-search">
          <svg className="m-search__icon" width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
          </svg>
          <input
            className="m-search__input"
            type="text"
            placeholder="Szukaj gracza lub turnieju…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Szukaj meczów klubowych"
          />
        </div>
      </div>

      {/* Informacja o zakresie */}
      <p className="cm-scope-note">
        Zakończone mecze turniejowe w klubie · {filtered.length} wyników
      </p>

      {filtered.length === 0 ? (
        <div className="m-empty">
          <p className="m-empty__title">Brak meczów</p>
          <p className="m-empty__sub">
            {search ? 'Brak wyników dla podanej frazy.' : 'Żadne mecze turniejowe nie spełniają kryteriów.'}
          </p>
          <a href={tournamentsUrl} className="dash-link-sm">Zobacz turnieje →</a>
        </div>
      ) : (
        <ul className="m-list" role="list">
          {filtered.map(m => (
            <li key={m.id} className="m-row cm-row">
              {/* Turniej */}
              <div className="cm-row__tournament">
                <a href={`${tournamentsUrl}/${m.tournament_id}`} className="cm-row__tourn-link">
                  {m.tournament_name}
                </a>
                <span className="m-badge m-badge--type">
                  {TOURNAMENT_TYPE_LABEL[m.tournament_type] ?? m.tournament_type}
                </span>
              </div>
              {/* Mecz */}
              <div className="cm-row__matchup">{matchup(m)}</div>
              {/* Wynik */}
              <div className="cm-row__score">
                <span className="m-score">{matchScore(m)}</span>
                {m.winner && (
                  <span className="cm-row__winner">
                    <svg width="10" height="10" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style={{color: 'var(--tc-accent)'}}>
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                    </svg>
                    {m.winner}
                  </span>
                )}
              </div>
              {/* Data */}
              <div className="m-row__date cm-row__date">{formatDate(m.match_date)}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
