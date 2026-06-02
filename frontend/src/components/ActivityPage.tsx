// ActivityPage.tsx — React island: pełna strona aktywności użytkownika.
// Filtry: typ (Wszystko / Mecze / Turnieje / Rezerwacje) + czas (Dziś / Tydzień / Miesiąc / Wszystko).
// Reuse ActivityItem, FeedKind i KIND_BADGE z ActivityFeed.tsx.
// CSS w activity.astro <style is:global>.

import { useState, useMemo } from 'react';
import type { ActivityItem, FeedKind } from '@/components/ActivityFeed';

// ── Filtry ─────────────────────────────────────────────────────────────────

type KindFilter = 'all' | FeedKind;
type TimeFilter = 'today' | 'week' | 'month' | 'all';

const KIND_FILTERS: { id: KindFilter; label: string }[] = [
  { id: 'all',          label: 'Wszystko'   },
  { id: 'match',        label: 'Mecze'      },
  { id: 'notification', label: 'Turnieje'   },
  { id: 'reservation',  label: 'Rezerwacje' },
];

const TIME_FILTERS: { id: TimeFilter; label: string }[] = [
  { id: 'today', label: 'Dziś'    },
  { id: 'week',  label: 'Tydzień' },
  { id: 'month', label: 'Miesiąc' },
  { id: 'all',   label: 'Wszystko'},
];

const KIND_BADGE_CFG: Record<FeedKind, { label: string; cls: string }> = {
  match:        { label: 'Mecz',     cls: 'af-badge--match' },
  notification: { label: 'Turniej',  cls: 'af-badge--notif' },
  reservation:  { label: 'Kort',     cls: 'af-badge--court' },
};

// ── Filtrowanie ────────────────────────────────────────────────────────────

function parseTs(s: string): number {
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(s + 'T00:00:00').getTime();
  return new Date(s).getTime();
}

function applyFilters(
  items: ActivityItem[],
  kind: KindFilter,
  time: TimeFilter,
): ActivityItem[] {
  let result = kind === 'all' ? items : items.filter(i => i.kind === kind);

  if (time !== 'all') {
    let fromMs: number;
    if (time === 'today') {
      const d = new Date(); d.setHours(0, 0, 0, 0); fromMs = d.getTime();
    } else if (time === 'week') {
      fromMs = Date.now() - 7 * 86_400_000;
    } else {
      fromMs = Date.now() - 30 * 86_400_000;
    }
    result = result.filter(i => { const ts = parseTs(i.timestamp); return !isNaN(ts) && ts >= fromMs; });
  }

  return result;
}

// ── Empty states ───────────────────────────────────────────────────────────

const EMPTY: Record<KindFilter, Record<TimeFilter, [string, string]>> = {
  all: {
    today: ['Brak aktywności dziś',          'Nic się nie wydarzyło jeszcze dzisiaj.'],
    week:  ['Brak aktywności w tym tygodniu','Tu pojawią się zdarzenia z ostatnich 7 dni.'],
    month: ['Brak aktywności w tym miesiącu','Tu pojawią się zdarzenia z ostatnich 30 dni.'],
    all:   ['Brak aktywności',               'Tu pojawią się Twoje mecze, turnieje i rezerwacje.'],
  },
  match: {
    today: ['Brak meczów dziś',          'Nie rozegrałeś jeszcze żadnego meczu dzisiaj.'],
    week:  ['Brak meczów w tym tygodniu','Tu pojawią się mecze z ostatnich 7 dni.'],
    month: ['Brak meczów w tym miesiącu','Tu pojawią się mecze z ostatnich 30 dni.'],
    all:   ['Brak meczów',               'Twoja historia meczów jest pusta.'],
  },
  notification: {
    today: ['Brak zdarzeń turniejowych dziś',          'Żadne turnieje nie zmieniły statusu dzisiaj.'],
    week:  ['Brak zdarzeń turniejowych w tym tygodniu','Tu pojawią się zdarzenia z ostatnich 7 dni.'],
    month: ['Brak zdarzeń turniejowych w tym miesiącu','Tu pojawią się zdarzenia z ostatnich 30 dni.'],
    all:   ['Brak zdarzeń turniejowych',               'Dołącz do turnieju, żeby zobaczyć aktywność.'],
  },
  reservation: {
    today: ['Brak rezerwacji dziś',          'Nie masz rezerwacji na dziś.'],
    week:  ['Brak rezerwacji w tym tygodniu','Tu pojawią się rezerwacje z tego tygodnia.'],
    month: ['Brak rezerwacji w tym miesiącu','Tu pojawią się rezerwacje z ostatnich 30 dni.'],
    all:   ['Brak rezerwacji',               'Zarezerwuj kort, żeby zobaczyć historię.'],
  },
};

// ── Props ──────────────────────────────────────────────────────────────────

interface Props {
  items: ActivityItem[];
  matchesUrl: string;
  tournamentsUrl: string;
  courtsUrl: string;
}

// ── Komponent ──────────────────────────────────────────────────────────────

export default function ActivityPage({ items, matchesUrl, tournamentsUrl, courtsUrl }: Props) {
  const [kindFilter, setKindFilter] = useState<KindFilter>('all');
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('month');

  const filtered = useMemo(
    () => applyFilters(items, kindFilter, timeFilter),
    [items, kindFilter, timeFilter],
  );

  const [title, sub] = EMPTY[kindFilter][timeFilter];

  return (
    <div className="act-page">
      {/* ── Toolbar ── */}
      <div className="act-toolbar">
        <div className="act-seg" role="group" aria-label="Filtruj po typie">
          {KIND_FILTERS.map(f => (
            <button
              key={f.id}
              type="button"
              className={`act-seg__btn${kindFilter === f.id ? ' act-seg__btn--active' : ''}`}
              onClick={() => setKindFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="act-seg act-seg--time" role="group" aria-label="Filtruj po czasie">
          {TIME_FILTERS.map(f => (
            <button
              key={f.id}
              type="button"
              className={`act-seg__btn${timeFilter === f.id ? ' act-seg__btn--active' : ''}`}
              onClick={() => setTimeFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Lista lub empty state ── */}
      {filtered.length === 0 ? (
        <div className="act-empty">
          <div className="act-empty__icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd"/>
            </svg>
          </div>
          <p className="act-empty__title">{title}</p>
          <p className="act-empty__sub">{sub}</p>
          <div className="act-empty__links">
            <a href={matchesUrl}     className="dash-link-sm">Historia meczów</a>
            <a href={tournamentsUrl} className="dash-link-sm">Turnieje</a>
            <a href={courtsUrl}      className="dash-link-sm">Rezerwacje</a>
          </div>
        </div>
      ) : (
        <>
          <ul className="act-list" role="list">
            {filtered.map((item, i) => {
              const badge = KIND_BADGE_CFG[item.kind];
              const titleNode = item.href
                ? <a href={item.href} className="act-item__title-link">{item.title}</a>
                : <span>{item.title}</span>;
              return (
                <li key={`${item.timestamp}-${i}`} className="act-item">
                  <div className={`act-dot act-dot--${item.result}`} aria-hidden="true" />
                  <div className="act-item__body">
                    <div className="act-item__title">{titleNode}</div>
                    <div className="act-item__meta">
                      <span className={`af-badge ${badge.cls}`}>{badge.label}</span>
                      {item.desc && (
                        <>
                          <span className="act-sep">·</span>
                          <span className="act-item__desc">{item.desc}</span>
                        </>
                      )}
                      {item.score && item.score !== '—' && (
                        <>
                          <span className="act-sep">·</span>
                          <span className="act-item__score">{item.score}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="act-item__time">{item.time}</div>
                </li>
              );
            })}
          </ul>
          <div className="act-footer">
            <span className="act-footer__count">
              <strong>{filtered.length}</strong> {filtered.length === 1 ? 'wpis' : filtered.length < 5 ? 'wpisy' : 'wpisów'}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
