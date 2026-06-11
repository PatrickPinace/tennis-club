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

  const [showTournamentModal, setShowTournamentModal] = useState(false);
  const [activeTournamentMatches, setActiveTournamentMatches] = useState<any[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [expandedMatchId, setExpandedMatchId] = useState<number | null>(null);
  const [savingMatchId, setSavingMatchId] = useState<number | null>(null);
  const [saveErrors, setSaveErrors] = useState<Record<number, string>>({});
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<Record<number, string>>({});

  const [set1p1, setSet1p1] = useState<Record<number, string>>({});
  const [set1p2, setSet1p2] = useState<Record<number, string>>({});
  const [set2p1, setSet2p1] = useState<Record<number, string>>({});
  const [set2p2, setSet2p2] = useState<Record<number, string>>({});
  const [set3p1, setSet3p1] = useState<Record<number, string>>({});
  const [set3p2, setSet3p2] = useState<Record<number, string>>({});
  const [walkover, setWalkover] = useState<Record<number, boolean>>({});
  const [walkoverWinnerId, setWalkoverWinnerId] = useState<Record<number, string>>({});
  const [matchDates, setMatchDates] = useState<Record<number, string>>({});

  const fetchActiveMatches = async () => {
    setLoadingMatches(true);
    setFetchError(null);
    try {
      const res = await fetch('/api/tournaments/my-active-matches/', { credentials: 'include' });
      if (!res.ok) throw new Error(`Błąd: ${res.status}`);
      const data = await res.json();
      setActiveTournamentMatches(data);

      const s1p1: Record<number, string> = {};
      const s1p2: Record<number, string> = {};
      const s2p1: Record<number, string> = {};
      const s2p2: Record<number, string> = {};
      const s3p1: Record<number, string> = {};
      const s3p2: Record<number, string> = {};
      const wdr: Record<number, boolean> = {};
      const wdrWin: Record<number, string> = {};
      const dates: Record<number, string> = {};

      data.forEach((m: any) => {
        s1p1[m.id] = m.set1_p1_score !== null ? String(m.set1_p1_score) : '';
        s1p2[m.id] = m.set1_p2_score !== null ? String(m.set1_p2_score) : '';
        s2p1[m.id] = m.set2_p1_score !== null ? String(m.set2_p1_score) : '';
        s2p2[m.id] = m.set2_p2_score !== null ? String(m.set2_p2_score) : '';
        s3p1[m.id] = m.set3_p1_score !== null ? String(m.set3_p1_score) : '';
        s3p2[m.id] = m.set3_p2_score !== null ? String(m.set3_p2_score) : '';
        wdr[m.id] = false;
        wdrWin[m.id] = '';
        if (m.scheduled_time) {
          try {
            dates[m.id] = new Date(m.scheduled_time).toISOString().slice(0, 16);
          } catch {
            dates[m.id] = '';
          }
        } else {
          dates[m.id] = '';
        }
      });
      setSet1p1(s1p1);
      setSet1p2(s1p2);
      setSet2p1(s2p1);
      setSet2p2(s2p2);
      setSet3p1(s3p1);
      setSet3p2(s3p2);
      setWalkover(wdr);
      setWalkoverWinnerId(wdrWin);
      setMatchDates(dates);
    } catch (err: any) {
      setFetchError(err.message || 'Nie udało się pobrać meczów.');
    } finally {
      setLoadingMatches(false);
    }
  };

  const handleSaveScore = async (match: any) => {
    const mId = match.id;
    setSavingMatchId(mId);
    setSaveErrors(prev => ({ ...prev, [mId]: '' }));
    setSaveSuccessMsg(prev => ({ ...prev, [mId]: '' }));

    const isWalkover = walkover[mId] || false;
    const dateVal = matchDates[mId] || '';

    let payload: any = {};
    if (dateVal) {
      payload.scheduled_time = new Date(dateVal).toISOString();
    } else {
      payload.scheduled_time = new Date().toISOString();
    }

    if (isWalkover) {
      const winnerId = walkoverWinnerId[mId];
      if (!winnerId) {
        setSaveErrors(prev => ({ ...prev, [mId]: 'Musisz wybrać zwycięzcę walkowera.' }));
        setSavingMatchId(null);
        return;
      }
      payload.walkover = true;
      payload.winner_participant_id = parseInt(winnerId, 10);
    } else {
      const val1_1 = set1p1[mId] || '';
      const val1_2 = set1p2[mId] || '';
      const val2_1 = set2p1[mId] || '';
      const val2_2 = set2p2[mId] || '';
      const val3_1 = set3p1[mId] || '';
      const val3_2 = set3p2[mId] || '';

      const intVal = (v: string): number | null => {
        const trimmed = v.trim();
        if (trimmed === '') return null;
        const n = parseInt(trimmed, 10);
        return isNaN(n) ? null : n;
      };

      const s1_1 = intVal(val1_1);
      const s1_2 = intVal(val1_2);
      const s2_1 = intVal(val2_1);
      const s2_2 = intVal(val2_2);
      const s3_1 = intVal(val3_1);
      const s3_2 = intVal(val3_2);

      if (s1_1 === null || s1_2 === null) {
        setSaveErrors(prev => ({ ...prev, [mId]: 'Set 1 jest wymagany — wpisz wynik dla obu stron.' }));
        setSavingMatchId(null);
        return;
      }

      const checkTennisSet = (a: number, b: number, n: number): string | null => {
        if (a < 0 || b < 0) return `Set ${n}: wynik nie może być ujemny.`;
        const hi = Math.max(a, b), lo = Math.min(a, b);
        if (hi >= 10) {
          if (hi > 20) return `Set ${n}: super tie-break nie może mieć więcej niż 20 punktów.`;
          if (hi - lo < 2) return `Set ${n}: super tie-break wymaga przewagi ≥ 2 punktów.`;
          if (hi > 10 && lo !== hi - 2) return `Set ${n}: po 10:10 gra trwa do różnicy 2 punktów.`;
          return null;
        }
        if (hi < 6) return `Set ${n}: zwycięzca musi mieć co najmniej 6 gemów.`;
        if (hi === 6 && lo <= 4) return null;
        if (hi === 7 && (lo === 5 || lo === 6)) return null;
        return `Set ${n}: wynik ${a}:${b} jest niemożliwy w standardowym secie tenisowym.`;
      };

      if (match.tournament_type !== 'AMR') {
        const err1 = checkTennisSet(s1_1, s1_2, 1);
        if (err1) {
          setSaveErrors(prev => ({ ...prev, [mId]: err1 }));
          setSavingMatchId(null);
          return;
        }

        if ((s2_1 === null) !== (s2_2 === null)) {
          setSaveErrors(prev => ({ ...prev, [mId]: 'Set 2: wpisz wynik dla obu stron.' }));
          setSavingMatchId(null);
          return;
        } else if (s2_1 !== null && s2_2 !== null) {
          const err2 = checkTennisSet(s2_1, s2_2, 2);
          if (err2) {
            setSaveErrors(prev => ({ ...prev, [mId]: err2 }));
            setSavingMatchId(null);
            return;
          }
        }

        if ((s3_1 === null) !== (s3_2 === null)) {
          setSaveErrors(prev => ({ ...prev, [mId]: 'Set 3: wpisz wynik dla obu stron.' }));
          setSavingMatchId(null);
          return;
        } else if (s3_1 !== null && s3_2 !== null) {
          const err3 = checkTennisSet(s3_1, s3_2, 3);
          if (err3) {
            setSaveErrors(prev => ({ ...prev, [mId]: err3 }));
            setSavingMatchId(null);
            return;
          }
        }
      }

      payload = {
        ...payload,
        set1_p1: s1_1,
        set1_p2: s1_2,
        set2_p1: s2_1,
        set2_p2: s2_2,
        set3_p1: s3_1,
        set3_p2: s3_2,
      };
    }

    try {
      const csrfToken = document.cookie
        .split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))
        ?.split('=')[1] ?? '';

      const res = await fetch(`/api/tournaments/${match.tournament_id}/matches/${mId}/score/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setSaveSuccessMsg(prev => ({ ...prev, [mId]: 'Zapisano pomyślnie!' }));
        setTimeout(() => {
          setActiveTournamentMatches(prev => prev.filter(m => m.id !== mId));
          setExpandedMatchId(null);
        }, 1500);
      } else {
        setSaveErrors(prev => ({ ...prev, [mId]: data.detail || data.error || 'Nie udało się zapisać wyniku.' }));
      }
    } catch {
      setSaveErrors(prev => ({ ...prev, [mId]: 'Błąd połączenia z serwerem.' }));
    } finally {
      setSavingMatchId(null);
    }
  };

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

  useEffect(() => {
    const handleOpen = () => {
      setShowTournamentModal(true);
      fetchActiveMatches();
    };
    window.addEventListener('open-tournament-matches-modal', handleOpen);
    return () => window.removeEventListener('open-tournament-matches-modal', handleOpen);
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

      {showTournamentModal && (
        <div className="res-popup-backdrop" role="dialog" aria-modal="true"
          onClick={e => { if (e.target === e.currentTarget) setShowTournamentModal(false); }}>
          <div className="res-popup" style={{ maxWidth: 650, width: '100%' }}>
            <div className="res-popup__header">
              <div>
                <div className="res-popup__title">Mecze turniejowe</div>
                <div className="res-popup__subtitle">Wprowadź wynik meczu turniejowego</div>
              </div>
              <button className="res-popup__close" aria-label="Zamknij" onClick={() => setShowTournamentModal(false)}>
                <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
                </svg>
              </button>
            </div>
            <div className="res-popup__body" style={{ maxHeight: 'var(--modal-body-max-height, 70vh)', overflowY: 'auto', padding: '16px 20px' }}>
              {loadingMatches && <div style={{ textAlign: 'center', padding: '20px', color: 'var(--tc-muted)' }}>Ładowanie meczów...</div>}
              {fetchError && <div style={{ color: 'var(--tc-hot)', padding: '10px 0' }}>{fetchError}</div>}
              
              {!loadingMatches && !fetchError && activeTournamentMatches.length === 0 && (
                <div style={{ textAlign: 'center', padding: '30px 20px', color: 'var(--tc-muted)' }}>
                  Brak aktywnych meczów turniejowych, do których możesz wpisać wynik.
                </div>
              )}

              {!loadingMatches && !fetchError && activeTournamentMatches.map(m => {
                const isExpanded = expandedMatchId === m.id;
                
                // Group players for doubles/Americano if participant 3/4 are available
                const isDbl = m.participant3_name || m.participant4_name;
                const formatNameShort = (fullName: string | null | undefined) => {
                  if (!fullName) return '';
                  const parts = fullName.trim().split(/\s+/);
                  if (parts.length < 2) return fullName;
                  return `${parts[0]} ${parts[parts.length - 1].charAt(0)}.`;
                };

                const teamANameFull = m.participant1_name + (m.participant3_name ? ` / ${m.participant3_name}` : '');
                const teamBNameFull = m.participant2_name + (m.participant4_name ? ` / ${m.participant4_name}` : '');
                const teamANameShort = formatNameShort(m.participant1_name) + (m.participant3_name ? ` / ${formatNameShort(m.participant3_name)}` : '');
                const teamBNameShort = formatNameShort(m.participant2_name) + (m.participant4_name ? ` / ${formatNameShort(m.participant4_name)}` : '');

                return (
                  <div key={m.id} style={{
                    background: 'var(--tc-chip-bg)',
                    border: '1px solid var(--tc-card-border)',
                    borderRadius: '10px',
                    marginBottom: '12px',
                    overflow: 'hidden',
                    transition: 'all 0.2s ease'
                  }}>
                    {/* Header bar */}
                    <div 
                      onClick={() => setExpandedMatchId(isExpanded ? null : m.id)}
                      style={{
                        padding: '14px 18px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: 'pointer',
                        userSelect: 'none'
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--tc-accent)', textTransform: 'uppercase', marginBottom: '2px' }}>
                          🏆 {m.tournament_name}
                        </div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--tc-ink)' }}>
                          <span className="player-name-full">{teamANameFull}</span>
                          <span className="player-name-short">{teamANameShort}</span>
                          {' '}<span style={{ color: 'var(--tc-faint)' }}>vs</span>{' '}
                          <span className="player-name-full">{teamBNameFull}</span>
                          <span className="player-name-short">{teamBNameShort}</span>
                        </div>
                        {m.scheduled_time && (
                          <div style={{ fontSize: '0.7rem', color: 'var(--tc-muted)', marginTop: '2px' }}>
                            Termin: {new Date(m.scheduled_time).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                          </div>
                        )}
                      </div>
                      <div style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        border: '1px solid var(--tc-card-border-soft)',
                        background: '#ffffff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--tc-muted)',
                        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
                      }}>
                        <svg 
                          width="8" height="8" 
                          viewBox="0 0 10 10" 
                          fill="none" 
                          stroke="currentColor" 
                          strokeWidth="1.2" 
                          style={{
                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
                          }}
                        >
                          <path d="M1 3.5l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    </div>

                    {/* Expandable score form */}
                    {isExpanded && (
                      <div style={{
                        padding: '16px 18px',
                        borderTop: '1px solid var(--tc-card-border-soft)',
                        background: 'var(--tc-card-bg)'
                      }}>
                        {saveErrors[m.id] && (
                          <div style={{
                            padding: '8px 12px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            borderRadius: '6px',
                            color: 'var(--tc-hot)',
                            fontSize: '0.8rem',
                            marginBottom: '12px'
                          }}>
                            {saveErrors[m.id]}
                          </div>
                        )}
                        {saveSuccessMsg[m.id] && (
                          <div style={{
                            padding: '8px 12px',
                            background: 'var(--tc-accent-soft)',
                            border: '1px solid var(--tc-accent-border)',
                            borderRadius: '6px',
                            color: 'var(--tc-accent)',
                            fontSize: '0.8rem',
                            marginBottom: '12px'
                          }}>
                            {saveSuccessMsg[m.id]}
                          </div>
                        )}

                        {/* Tabular tennis scoreboard style */}
                        <div className="scoreboard-grid" style={{ 
                          background: 'var(--tc-chip-bg)', 
                          border: '1px solid var(--tc-card-border)', 
                          borderRadius: '8px',
                          overflow: 'hidden',
                          marginBottom: '16px',
                          opacity: walkover[m.id] ? 0.4 : 1,
                          pointerEvents: walkover[m.id] ? 'none' : 'auto'
                        }}>
                          {/* Column Headers */}
                          <div style={{ padding: '10px 14px', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)', textTransform: 'uppercase' }}>Gracz</div>
                          <div style={{ textAlign: 'center', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)' }}>SET 1</div>
                          <div style={{ textAlign: 'center', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)' }}>SET 2</div>
                          <div style={{ textAlign: 'center', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)' }}>SET 3</div>

                          {/* Row 1: Team A */}
                          <div style={{ padding: '10px 14px', fontSize: '0.88rem', fontWeight: 600, color: 'var(--tc-ink)', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <span className="player-name-full">{teamANameFull}</span>
                            <span className="player-name-short">{teamANameShort}</span>
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set1p1[m.id] || ''}
                              onChange={e => setSet1p1(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set2p1[m.id] || ''}
                              onChange={e => setSet2p1(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set3p1[m.id] || ''}
                              onChange={e => setSet3p1(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>

                          {/* Row 2: Team B */}
                          <div style={{ padding: '10px 14px', fontSize: '0.88rem', fontWeight: 600, color: 'var(--tc-ink)', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <span className="player-name-full">{teamBNameFull}</span>
                            <span className="player-name-short">{teamBNameShort}</span>
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set1p2[m.id] || ''}
                              onChange={e => setSet1p2(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set2p2[m.id] || ''}
                              onChange={e => setSet2p2(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set3p2[m.id] || ''}
                              onChange={e => setSet3p2(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                        </div>

                        {/* Date field and Walkover side-by-side */}
                        <div className="mobile-stack-grid" style={{ marginBottom: '16px' }}>
                          {/* Date selection */}
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                            <label style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)', textTransform: 'uppercase' }}>Termin rozegrania</label>
                            <input 
                              type="datetime-local" 
                              value={matchDates[m.id] || ''}
                              onChange={e => setMatchDates(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ 
                                height: '36px', 
                                padding: '0 10px', 
                                background: 'var(--tc-chip-bg)', 
                                border: '1px solid var(--tc-card-border)', 
                                borderRadius: '6px', 
                                color: 'var(--tc-ink)', 
                                fontSize: '0.8rem',
                                fontWeight: 500,
                                fontFamily: 'inherit'
                              }}
                            />
                          </div>

                          {/* Walkover setup */}
                          <div style={{ 
                            padding: '10px 14px', 
                            background: 'rgba(239, 68, 68, 0.04)', 
                            border: '1px solid rgba(239, 68, 68, 0.1)', 
                            borderRadius: '8px',
                            display: 'flex', 
                            flexDirection: 'column',
                            justifyContent: 'center',
                            gap: '8px'
                          }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: 'var(--tc-muted)', margin: 0 }}>
                              <input 
                                type="checkbox" 
                                checked={walkover[m.id] || false}
                                onChange={e => setWalkover(prev => ({ ...prev, [m.id]: e.target.checked }))}
                              />
                              ⚠️ Walkover ( WDR )
                            </label>

                            {walkover[m.id] && (
                              <select 
                                value={walkoverWinnerId[m.id] || ''} 
                                onChange={e => setWalkoverWinnerId(prev => ({ ...prev, [m.id]: e.target.value }))}
                                style={{ 
                                  height: '30px', 
                                  padding: '0 6px', 
                                  background: 'var(--tc-card-bg)', 
                                  border: '1px solid var(--tc-card-border)', 
                                  borderRadius: '4px', 
                                  color: 'var(--tc-ink)',
                                  fontSize: '0.78rem'
                                }}
                              >
                                <option value="">— wybierz zwycięzcę —</option>
                                <option value={m.participant1_id}>{teamAName}</option>
                                <option value={m.participant2_id}>{teamBName}</option>
                              </select>
                            )}
                          </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
                          <button 
                            type="button" 
                            disabled={savingMatchId === m.id}
                            onClick={() => handleSaveScore(m)}
                            className="tc-btn tc-btn-primary"
                            style={{ height: '34px', fontSize: '0.8rem', padding: '0 16px' }}
                          >
                            {savingMatchId === m.id ? 'Zapisywanie...' : 'Zapisz wynik'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
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
