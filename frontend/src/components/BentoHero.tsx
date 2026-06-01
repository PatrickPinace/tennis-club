import { useState, useEffect } from 'react';

// ── Types ──────────────────────────────────────────────────────────────────

interface MatchHistoryItem {
  user: 'user-win' | 'user-loss' | 'user-draw';
  match_double: boolean;
}

interface SummaryLastMatch {
  date: string;
  opponent: string;
  score: string;
  won: boolean;
}

interface SummaryRanking {
  position: number | null;
  points: number | null;
  matches_played: number | null;
  matches_won: number | null;
  win_rate: number | null;
}

interface SummaryReservation {
  date: string;
  end_time: string;
  court: string | null;
}

interface DashboardSummary {
  last_match: SummaryLastMatch | null;
  ranking: SummaryRanking | null;
  next_reservation: SummaryReservation | null;
}

interface Props {
  matchHistory: MatchHistoryItem[];
  matchesPlayed: number;
  courtsUrl: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function parseSets(score: string): string[] {
  return score.split(' ').map(s => s.trim()).filter(Boolean);
}

function countSetsWon(sets: string[]): [number, number] {
  let won = 0;
  let lost = 0;
  for (const s of sets) {
    const [a, b] = s.split(':').map(Number);
    if (a > b) won++;
    else lost++;
  }
  return [won, lost];
}

function formatMatchDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('pl-PL', {
      day: 'numeric', month: 'long', year: 'numeric',
    });
  } catch {
    return iso;
  }
}

// ── Sub-components ─────────────────────────────────────────────────────────

function LastMatchCard({ match }: { match: SummaryLastMatch | null }) {
  const sets = match ? parseSets(match.score ?? '') : [];
  const [setsWon, setsLost] = match ? countSetsWon(sets) : [0, 0];

  return (
    <div className="dash-card bento-last-match">
      <div className="lm-header">
        <div className="bento-label">OSTATNI MECZ</div>
        {match && (
          <span
            className="lm-badge"
            style={{
              background: match.won ? 'var(--tc-accent-soft)' : 'rgba(239,68,68,0.1)',
              color: match.won ? 'var(--tc-accent)' : 'var(--tc-hot)',
              padding: '3px 10px',
              borderRadius: '99px',
              fontSize: '0.72rem',
              fontWeight: 700,
            }}
          >
            {match.won ? '● Wygrana' : '● Porażka'}
          </span>
        )}
      </div>

      <div className="lm-body">
        <div className="lm-score">
          {match ? (
            <>
              {setsWon}
              <span className="lm-score__colon">:</span>
              <span className="lm-score__loss">{setsLost}</span>
            </>
          ) : '—'}
        </div>
        <div className="lm-opponent">
          <div className="lm-opponent__prefix">przeciwko</div>
          <div className="lm-opponent__name">{match?.opponent ?? 'Brak danych'}</div>
          {match?.date && (
            <div className="lm-opponent__meta">{formatMatchDate(match.date)}</div>
          )}
        </div>
      </div>

      <div className="lm-sets" aria-hidden="true">
        {[0, 1, 2].map(i => {
          const set = sets[i];
          if (!set) {
            return (
              <div key={i} className="lm-set lm-set--empty">
                <span className="lm-set__label">SET {i + 1}</span>
                <span className="lm-set__score">—</span>
              </div>
            );
          }
          const [a, b] = set.split(':').map(Number);
          const myWon = a > b;
          return (
            <div key={i} className="lm-set">
              <span className="lm-set__label">SET {i + 1}</span>
              <span className="lm-set__score">
                <span className={myWon ? 'lm-set__my--win' : ''}>{a}</span>
                <span className="lm-set__dash"> — </span>
                <span className="lm-set__opp">{b}</span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RankingCard({ ranking }: { ranking: SummaryRanking | null }) {
  const pos = ranking?.position;
  const trend: string[] = [];
  if (ranking?.matches_played != null) trend.push(`${ranking.matches_played} meczów`);
  if (ranking?.matches_won != null) trend.push(`${ranking.matches_won} wygranych`);

  return (
    <div className="dash-card bento-ranking">
      <div className="bento-label">RANKING KLUBOWY</div>
      <div className="rk-main">
        <div className="rk-position">{pos ?? '—'}</div>
        <div className="rk-label">miejsce</div>
      </div>
      <div className="rk-trend">{trend.length > 0 ? trend.join(' · ') : ''}</div>
      <div className="rk-bottom">
        <div className="rk-stat">
          <span className="rk-stat__label">PUNKTY</span>
          <span className="rk-stat__value">
            {ranking?.points != null ? Math.round(ranking.points) : '—'}
          </span>
        </div>
        <div className="rk-stat">
          <span className="rk-stat__label">SKUTECZNOŚĆ</span>
          <span className="rk-stat__value rk-stat__value--accent">
            {ranking?.win_rate != null ? `${ranking.win_rate}%` : '—'}
          </span>
        </div>
      </div>
    </div>
  );
}

function ReservationCard({
  reservation,
  courtsUrl,
}: {
  reservation: SummaryReservation | null;
  courtsUrl: string;
}) {
  return (
    <div className="dash-card bento-reservation bento-reservation--dashed">
      <div className="reservation-inner">
        <div className="reservation-icon-box" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" />
            <path d="M16 2v4M8 2v4M3 10h18" />
          </svg>
        </div>
        <div className="reservation-text">
          <div className="bento-label" style={{ marginBottom: 4 }}>NAJBLIŻSZA REZERWACJA</div>
          {reservation ? (
            <>
              <div className="stat-card__value reservation-value" style={{ fontSize: '0.875rem', fontWeight: 500 }}>
                {reservation.date}–{reservation.end_time}
              </div>
              <div className="stat-card__detail reservation-detail">
                {reservation.court ?? 'Kort nieokreślony'}
              </div>
            </>
          ) : (
            <div className="stat-card__value reservation-value" style={{ fontSize: '0.875rem', fontWeight: 500 }}>
              Brak nadchodzących
            </div>
          )}
        </div>
        <a href={courtsUrl} className="reservation-btn">Zarezerwuj kort →</a>
      </div>
    </div>
  );
}

function FormStatsCard({
  matchHistory,
  matchesPlayed,
}: {
  matchHistory: MatchHistoryItem[];
  matchesPlayed: number;
}) {
  const last8 = matchHistory.slice(0, 8);

  return (
    <div className="dash-card bento-stats">
      <div className="bento-form-section">
        <div className="bento-label">FORMA · OSTATNIE 8</div>
        {matchesPlayed > 0 ? (
          <div className="bento-form-blocks" aria-label="Forma (ostatnie mecze)">
            {last8.map((m, i) => {
              const r = m.user === 'user-win' ? 'W' : m.user === 'user-loss' ? 'P' : 'R';
              const cls = r === 'W' ? 'win' : r === 'P' ? 'loss' : 'neutral';
              return (
                <div
                  key={i}
                  className={`form-block form-block--${cls}`}
                  title={r === 'W' ? 'Wygrana' : r === 'P' ? 'Porażka' : 'Remis'}
                >
                  {r}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bento-form-blocks bento-form-blocks--empty">
            <span style={{ fontSize: '0.78rem', color: 'var(--tc-muted)' }}>Brak meczów</span>
          </div>
        )}
      </div>
      <div className="bento-total-section">
        <div className="bento-label">ŁĄCZNIE MECZÓW</div>
        <div className="bento-total-row">
          <span className="bento-total__value">{matchesPlayed}</span>
          <span className="bento-total__sub">w tym sezonie</span>
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function BentoHero({ matchHistory, matchesPlayed, courtsUrl }: Props) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    const apiBase =
      (document.querySelector('meta[name="api-base"]') as HTMLMetaElement)?.content ??
      'http://localhost:8000';

    fetch(`${apiBase}/api/dashboard/summary/`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      redirect: 'manual',
    })
      .then(res => {
        if (res.type === 'opaqueredirect' || !res.ok) return null;
        return res.json();
      })
      .then(data => {
        if (data) setSummary(data);
      })
      .catch(() => {});
  }, []);

  return (
    <section className="bento-hero" aria-label="Podsumowanie">
      <LastMatchCard match={summary?.last_match ?? null} />
      <RankingCard ranking={summary?.ranking ?? null} />
      <ReservationCard reservation={summary?.next_reservation ?? null} courtsUrl={courtsUrl} />
      <FormStatsCard matchHistory={matchHistory} matchesPlayed={matchesPlayed} />
    </section>
  );
}
