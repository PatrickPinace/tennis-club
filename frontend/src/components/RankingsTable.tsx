import { useState, useEffect } from 'react';

interface PlayerEntry {
  position: number;
  display_name: string;
  points: number | string;
  matches_played: number;
  matches_won: number;
  matches_lost: number;
  win_rate: number;
}

interface MyRank {
  position: number;
  points: number | string;
  matches_won: number | string;
  matches_played: number | string;
  win_rate: number | null;
  display_name: string | null;
}

interface Props {
  initialPlayers: PlayerEntry[];
  isLive: boolean;
  totalPlayers: number;
  availableSeasons: number[];
  defaultSeason: number | 'all';
  lastUpdate?: string;
}

type MatchType = 'SNG' | 'DBL';
type Season = number | 'all';

function getInitials(name: string): string {
  return name.split(' ').filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('');
}

function fmtPoints(pts: number | string): string {
  return Math.round(Number(pts)).toLocaleString('pl-PL');
}

function todayFormatted(): string {
  return new Date().toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
}

const MEDALS = ['gold', 'silver', 'bronze'] as const;
const PODIUM_KEYS = ['silver', 'gold', 'bronze'] as const;
const PODIUM_LABELS = ['SREBRO', 'ZŁOTO', 'BRĄZ'];
const PODIUM_NUMBERS = [2, 1, 3];
const PODIUM_HEADER_COLORS: Record<string, string> = {
  gold: '#92750a',
  silver: '#6b7a8a',
  bronze: '#8a6040',
};

function MyRankCard({ rank, matchType, season }: { rank: MyRank; matchType: MatchType; season: Season }) {
  const wr = rank.win_rate != null ? `${Math.round(rank.win_rate)}%` : '—';
  const pts = rank.points != null && rank.points !== '—'
    ? Math.round(Number(rank.points)).toLocaleString('pl-PL')
    : '—';
  const typeLabel = matchType === 'SNG' ? 'singlowy' : 'deblowy';
  const seasonLabel = season === 'all' ? 'All-time' : season;

  return (
    <div className="rk-my">
      <div className="rk-my__left">
        <div className="rk-my__pos">
          <span className="rk-my__pos-num">{rank.position}</span>
          <span className="rk-my__pos-label">miejsce</span>
        </div>
        <div className="rk-my__sep" aria-hidden="true" />
        <div>
          <div className="rk-my__title">Twoja pozycja</div>
          <div className="rk-my__sub">Ranking {typeLabel} {seasonLabel}</div>
        </div>
      </div>
      <div className="rk-my__stats">
        <div className="rk-my__stat">
          <span className="rk-my__stat-label">PUNKTY</span>
          <span className="rk-my__stat-val">{pts}</span>
        </div>
        <div className="rk-my__stat">
          <span className="rk-my__stat-label">WYGRANE</span>
          <span className="rk-my__stat-val">{rank.matches_won}/{rank.matches_played}</span>
        </div>
        <div className="rk-my__stat">
          <span className="rk-my__stat-label">SKUTECZNOŚĆ</span>
          <span className="rk-my__stat-val">{wr}</span>
        </div>
      </div>
    </div>
  );
}

function PodiumCard({ player, slot }: { player: PlayerEntry; slot: number }) {
  const k = PODIUM_KEYS[slot];
  const raised = slot === 1;

  return (
    <div className={`rk-podium__card rk-podium__card--${k}${raised ? ' rk-podium__card--raised' : ''}`}>
      <div className="rk-podium__header" style={{ background: PODIUM_HEADER_COLORS[k] }}>
        <span className="rk-podium__label">{PODIUM_LABELS[slot]}</span>
        <span className="rk-podium__num">{PODIUM_NUMBERS[slot]}</span>
      </div>
      <div className="rk-podium__body">
        <div className={`rk-podium__avatar rk-podium__avatar--${k}`} aria-hidden="true">
          {getInitials(player.display_name)}
        </div>
        <div className="rk-podium__info">
          <span className="rk-podium__name">{player.display_name}</span>
          <span className="rk-podium__meta">
            {player.matches_played} meczów · {Math.round(player.win_rate)}% skuteczności
          </span>
        </div>
      </div>
      <div className="rk-podium__footer">
        <div className="rk-podium__stat">
          <span className="rk-podium__stat-label">PUNKTY</span>
          <span className="rk-podium__stat-val">{fmtPoints(player.points)}</span>
        </div>
        <div className="rk-podium__stat">
          <span className="rk-podium__stat-label">WYGRANE</span>
          <span className="rk-podium__stat-val">
            {player.matches_won} <span className="rk-podium__stat-of">/ {player.matches_played}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function PlayerRow({ player, isMe }: { player: PlayerEntry; isMe: boolean }) {
  const isFirst = player.position === 1;
  const medal = player.position <= 3 ? MEDALS[player.position - 1] : null;

  return (
    <div
      className={`rk-row${isMe ? ' rk-row--me' : ''}`}
      data-pos={player.position}
    >
      <div className="rk-row__pos">
        <span className={`rk-pos-badge${player.position <= 3 ? ` rk-pos-badge--${player.position}` : ''}`}>
          {player.position}
        </span>
      </div>
      <div className="rk-row__player">
        <div
          className={`rk-row__avatar${medal ? ` rk-row__avatar--${medal}` : ''}`}
          aria-hidden="true"
        >
          {getInitials(player.display_name)}
        </div>
        <div className="rk-row__player-info">
          <span className="rk-row__name">
            {player.display_name}
          </span>
          {isMe && <span className="rk-me-badge">TY</span>}
          <span className="rk-row__winrate">{Math.round(player.win_rate)}% skuteczności</span>
        </div>
      </div>
      <div className="rk-row__num rk-row__muted">{player.matches_played}</div>
      <div className="rk-row__num rk-row__muted">
        {player.matches_won} <span className="rk-row__of">/ {player.matches_played}</span>
      </div>
      <div className="rk-row__num rk-row__points">
        {fmtPoints(player.points)} <span className="rk-row__pkt">pkt</span>
      </div>
    </div>
  );
}

export default function RankingsTable({ initialPlayers, isLive, totalPlayers, availableSeasons, defaultSeason, lastUpdate }: Props) {
  const [matchType, setMatchType] = useState<MatchType>('SNG');
  const [season, setSeason] = useState<Season>(defaultSeason);
  const [players, setPlayers] = useState<PlayerEntry[]>(initialPlayers);
  const [myRank, setMyRank] = useState<MyRank | null>(null);
  const [live, setLive] = useState(isLive);
  const [seasonsExpanded, setSeasonsExpanded] = useState(false);

  // Zawsze widoczne: 2 najnowsze + All-time; reszta chowana pod "..."
  const visibleSeasons = availableSeasons.slice(0, 2);
  const hiddenSeasons = availableSeasons.slice(2);
  const hasHidden = hiddenSeasons.length > 0;
  const selectedIsHidden = season !== 'all' && hiddenSeasons.includes(season as number);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/dashboard/summary/', {
          credentials: 'include',
          redirect: 'manual',
        });
        if (!res.ok || res.type === 'opaqueredirect') return;
        const data = await res.json();
        const ranking = data?.ranking;
        if (!ranking || !ranking.display_name) return;
        setMyRank({
          position: ranking.position ?? ('—' as any),
          display_name: ranking.display_name,
          points: ranking.points ?? '—',
          matches_won: ranking.matches_won ?? 0,
          matches_played: ranking.matches_played ?? 0,
          win_rate: ranking.win_rate ?? null,
        });
      } catch {
        // silent
      }
    })();
  }, []);

  const fetchRankings = async (type: MatchType, yr: Season) => {
    try {
      const params = new URLSearchParams({ type });
      params.set('year', yr === 'all' ? 'all' : String(yr));
      const res = await fetch(`/api/rankings/list/?${params}`, {
        credentials: 'include',
        redirect: 'manual',
      });
      if (!res.ok || res.type === 'opaqueredirect') return;
      const rows: PlayerEntry[] = await res.json();
      setPlayers(rows ?? []);
      setLive(true);
    } catch {
      // silent
    }
  };

  const switchType = async (type: MatchType) => {
    if (type === matchType) return;
    setMatchType(type);
    await fetchRankings(type, season);
  };

  const switchSeason = async (yr: Season) => {
    if (yr === season) return;
    setSeason(yr);
    await fetchRankings(matchType, yr);
  };

  const count = players.length;
  const sorted = [...players].sort((a, b) => a.position - b.position);
  const top3 = sorted.slice(0, 3);
  // Visual order: [silver(#2), gold(#1), bronze(#3)]
  const podiumOrder = top3.length >= 3 ? [top3[1], top3[0], top3[2]] : top3;

  const typeLabel = matchType === 'SNG' ? 'Singiel' : 'Debel';
  const seasonLabel = season === 'all' ? 'All-time' : String(season);
  const footerInfo = lastUpdate
    ? `🕒 Ostatnia aktualizacja: ${lastUpdate}`
    : (live ? `Dane live · ${todayFormatted()}` : 'Dane demonstracyjne');
  const footerLabel = live
    ? `${typeLabel} · ${seasonLabel}`
    : `${typeLabel} · ${seasonLabel} (demo)`;

  const loggedInPlayer = myRank?.display_name
    ? players.find(p => p.display_name === myRank.display_name)
    : null;

  const activeRank: MyRank | null = myRank
    ? {
        position: loggedInPlayer ? loggedInPlayer.position : '—' as any,
        points: loggedInPlayer ? loggedInPlayer.points : '—',
        matches_won: loggedInPlayer ? loggedInPlayer.matches_won : 0,
        matches_played: loggedInPlayer ? loggedInPlayer.matches_played : 0,
        win_rate: loggedInPlayer ? loggedInPlayer.win_rate : null,
        display_name: myRank.display_name,
      }
    : null;

  return (
    <>
      {activeRank && <MyRankCard rank={activeRank} matchType={matchType} season={season} />}

      {podiumOrder.length >= 3 && (
        <div className="rk-podium">
          {podiumOrder.map((p, i) => (
            <PodiumCard key={`${p.display_name}-${i}`} player={p} slot={i} />
          ))}
        </div>
      )}

      <section className="rk-card">
        <div className="rk-card__header">
          <div className="rk-card__title-wrap">
            <span className="rk-card__dot" aria-hidden="true" />
            <h2 className="rk-card__title">TABELA KLUBOWA</h2>
            <span className="rk-card__badge">{count}</span>
          </div>
          <div className="rk-card__controls">
            <div className="rk-segmented" role="group" aria-label="Sezon">
              {visibleSeasons.map(yr => (
                <button
                  key={yr}
                  type="button"
                  className={`rk-seg${season === yr ? ' rk-seg--active' : ''}`}
                  onClick={() => switchSeason(yr)}
                >
                  {yr}
                </button>
              ))}
              {hasHidden && (seasonsExpanded ? (
                <>
                  {hiddenSeasons.map(yr => (
                    <button
                      key={yr}
                      type="button"
                      className={`rk-seg${season === yr ? ' rk-seg--active' : ''}`}
                      onClick={() => switchSeason(yr)}
                    >
                      {yr}
                    </button>
                  ))}
                  <button
                    type="button"
                    className="rk-seg rk-seg--more"
                    onClick={() => setSeasonsExpanded(false)}
                    title="Zwiń sezony"
                  >
                    ‹
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className={`rk-seg rk-seg--more${selectedIsHidden ? ' rk-seg--active' : ''}`}
                  onClick={() => setSeasonsExpanded(true)}
                  title="Pokaż starsze sezony"
                >
                  {selectedIsHidden ? String(season) : '···'}
                </button>
              ))}
              <button
                type="button"
                className={`rk-seg${season === 'all' ? ' rk-seg--active' : ''}`}
                onClick={() => switchSeason('all')}
              >
                <span className="rk-all-time-desktop">All-time</span>
                <span className="rk-all-time-mobile">ALL</span>
              </button>
            </div>
            <div className="rk-segmented" role="group" aria-label="Typ rankingu">
              <button
                type="button"
                className={`rk-seg${matchType === 'SNG' ? ' rk-seg--active' : ''}`}
                onClick={() => switchType('SNG')}
              >
                Singiel
              </button>
              <button
                type="button"
                className={`rk-seg${matchType === 'DBL' ? ' rk-seg--active' : ''}`}
                onClick={() => switchType('DBL')}
              >
                Debel
              </button>
            </div>
          </div>
        </div>

        <div className="rk-thead">
          <span className="rk-th">POZ.</span>
          <span className="rk-th">GRACZ</span>
          <span className="rk-th rk-th--r">MECZE</span>
          <span className="rk-th rk-th--r">WYGRANE</span>
          <span className="rk-th rk-th--r">PUNKTY</span>
        </div>

        <div className="rk-tbody">
          {count === 0 ? (
            <div className="rk-empty">Brak danych dla wybranej kategorii.</div>
          ) : (
            sorted.map((p, i) => (
              <PlayerRow
                key={`${matchType}-${p.display_name}-${i}`}
                player={p}
                isMe={myRank?.display_name != null && myRank.display_name === p.display_name}
              />
            ))
          )}
        </div>

        <div className="rk-card__footer">
          <span className="rk-footer-info">{footerInfo}</span>
          <span className="rk-footer-label">{footerLabel}</span>
        </div>
      </section>
    </>
  );
}
