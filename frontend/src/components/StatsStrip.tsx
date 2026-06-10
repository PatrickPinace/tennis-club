interface MatchHistoryItem {
  user: 'user-win' | 'user-loss' | 'user-draw';
}

interface Props {
  matchesPlayed: number;
  matchesWon: number;
  matchesLost: number;
  winRate: number;
  tournamentsActive: number;
  matchHistory: MatchHistoryItem[];
}

export default function StatsStrip({
  matchesPlayed,
  matchesWon,
  matchesLost,
  winRate,
  tournamentsActive,
  matchHistory,
}: Props) {
  const last8 = matchHistory.slice(0, 8);

  return (
    <section className="stats-strip" aria-label="Statystyki ogólne">
      <div className="stats-strip__stat">
        <div className="bento-label">ŁĄCZNIE MECZÓW</div>
        <div className="stats-strip__value">{matchesPlayed}</div>
      </div>
      <div className="stats-strip__stat">
        <div className="bento-label">WYGRANE</div>
        <div className="stats-strip__value">
          <span style={{ color: 'var(--tc-accent)' }}>{matchesWon}</span>
          <span className="stats-strip__frac">/ {matchesPlayed}</span>
        </div>
      </div>
      <div className="stats-strip__stat">
        <div className="bento-label">SKUTECZNOŚĆ</div>
        <div className="stats-strip__value">
          {winRate}<span className="stats-strip__frac">%</span>
        </div>
      </div>
      <div className="stats-strip__stat">
        <div className="bento-label">AKTYWNE TURNIEJE</div>
        <div className="stats-strip__value">{tournamentsActive}</div>
      </div>
      <div className="stats-strip__form">
        <div className="bento-label">FORMA · OSTATNIE 8</div>
        <div className="stats-strip__bars">
          {last8.map((m, i) => {
            const isWin = m.user === 'user-win';
            return (
              <div
                key={i}
                className={`stats-bar ${isWin ? 'stats-bar--win' : 'stats-bar--loss'}`}
                title={isWin ? 'Wygrana' : 'Porażka'}
              />
            );
          })}
          <span className="stats-strip__bars-summary">
            <span style={{ color: 'var(--tc-accent)', fontWeight: 700 }}>{matchesWon} wygranych</span> · <span style={{ color: 'var(--tc-hot)', fontWeight: 700 }}>{matchesLost} porażki</span>
          </span>
        </div>
      </div>
    </section>
  );
}
