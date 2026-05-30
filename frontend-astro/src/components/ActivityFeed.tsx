// ActivityFeed.tsx — React island: activity feed z filtrami (dziś/tydzień/miesiąc)
// Zastępuje vanilla JS z dashboard.astro — ten sam wygląd, zero zmian wizualnych.
// Używa istniejących klas CSS z dashboard.astro <style> (BEM: activity-*, dash-*).

import { useState, useMemo } from 'react';

// ── Typy ────────────────────────────────────────────────────────────────────

interface ActivityItem {
  type: string;
  title: string;
  desc: string;
  score: string;
  time: string;
  timestamp: string;
  result: 'win' | 'loss' | 'neutral';
}

interface Props {
  items: ActivityItem[];
  matchesUrl: string;
  tournamentsUrl: string;
}

// ── Filtrowanie ─────────────────────────────────────────────────────────────

type Period = 'today' | 'week' | 'month';

const FILTERS: { id: Period; label: string }[] = [
  { id: 'today', label: 'Dziś' },
  { id: 'week',  label: 'Tydzień' },
  { id: 'month', label: 'Miesiąc' },
];

const EMPTY_LABELS: Record<Period, [string, string]> = {
  today: ['Brak aktywności dziś', 'Nic się nie wydarzyło jeszcze dzisiaj.'],
  week:  ['Brak aktywności w tym tygodniu', 'Tu pojawią się mecze z ostatnich 7 dni.'],
  month: ['Brak aktywności w tym miesiącu', 'Tu pojawią się mecze z ostatnich 30 dni.'],
};

function parseLocalDate(s: string): number {
  // "YYYY-MM-DD" → parse as local midnight (not UTC)
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return new Date(s + 'T00:00:00').getTime();
  return new Date(s).getTime();
}

function filterItems(items: ActivityItem[], period: Period): ActivityItem[] {
  const now = Date.now();
  let fromMs: number;
  if (period === 'today') {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    fromMs = d.getTime();
  } else if (period === 'week') {
    fromMs = now - 7 * 86_400_000;
  } else {
    fromMs = now - 30 * 86_400_000;
  }
  return items.filter(item => {
    const ts = parseLocalDate(item.timestamp);
    return !isNaN(ts) && ts >= fromMs;
  });
}

function bestPeriod(items: ActivityItem[]): Period {
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const todayMs = todayStart.getTime();
  const weekMs = Date.now() - 7 * 86_400_000;

  if (items.some(i => parseLocalDate(i.timestamp) >= todayMs)) return 'today';
  if (items.some(i => parseLocalDate(i.timestamp) >= weekMs)) return 'week';
  return 'month';
}

// ── Komponent ───────────────────────────────────────────────────────────────

export default function ActivityFeed({ items, matchesUrl, tournamentsUrl }: Props) {
  const initialPeriod = useMemo(() => bestPeriod(items), []);
  const [period, setPeriod] = useState<Period>(initialPeriod);

  const filtered = useMemo(() => filterItems(items, period), [items, period]);

  return (
    <div className="dash-card" aria-labelledby="activity-heading">
      {/* Header */}
      <div className="dash-section-header">
        <h2 className="dash-section-title" id="activity-heading">Aktywność</h2>
        <div className="activity-seg" role="group" aria-label="Filtruj aktywność">
          {FILTERS.map(f => (
            <button
              key={f.id}
              type="button"
              className={`activity-seg__btn${period === f.id ? ' activity-seg__btn--active' : ''}`}
              onClick={() => setPeriod(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Lista lub empty state */}
      {filtered.length === 0 ? (
        <div className="dash-empty-block">
          <div className="dash-empty-block__icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd"/>
            </svg>
          </div>
          <p className="dash-empty-block__title">{EMPTY_LABELS[period][0]}</p>
          <p className="dash-empty-block__sub">{EMPTY_LABELS[period][1]}</p>
          <div className="dash-empty-block__links">
            <a href={matchesUrl} className="dash-link-sm">Moje mecze</a>
            <a href={tournamentsUrl} className="dash-link-sm">Turnieje</a>
          </div>
        </div>
      ) : (
        <ul className="activity-list" role="list">
          {filtered.map((item, i) => (
            <li key={`${item.timestamp}-${i}`} className="activity-item">
              <div className={`activity-dot activity-dot--${item.result}`} aria-hidden="true" />
              <div className="activity-item__body">
                <div className="activity-item__title">{item.title}</div>
                <div className="activity-item__desc">
                  {item.desc}
                  {item.score && item.score !== '—' && (
                    <>
                      <span className="activity-item__sep">·</span>
                      <span className="activity-item__score">{item.score}</span>
                    </>
                  )}
                </div>
              </div>
              <div className="activity-item__time">{item.time}</div>
            </li>
          ))}
        </ul>
      )}

      {/* Footer */}
      <div className="dash-card-footer activity-footer">
        <span className="activity-footer__count">
          <strong>{filtered.length}</strong> {filtered.length === 1 ? 'wpis' : 'wpisów'}
        </span>
        <a href={matchesUrl} className="dash-link-sm">Historia meczów →</a>
      </div>
    </div>
  );
}
