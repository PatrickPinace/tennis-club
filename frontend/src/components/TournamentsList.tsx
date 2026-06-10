interface TournamentItem {
  id: number;
  name: string;
  type: string;
  date: string;
  status: 'open' | 'scheduled' | 'active';
  statusLabel: string;
  participants: number;
  href: string;
  joined?: boolean;
  isRegOpen?: boolean;
}

interface Props {
  tournaments: TournamentItem[];
  tournamentsUrl: string;
}

const StarIcon = () => (
  <svg width="15" height="15" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style={{ color: 'var(--tc-accent)', flexShrink: 0 }}>
    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
  </svg>
);

const TrophyIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.25 9.71 2 12 2c2.291 0 4.545.25 6.75.721v1.515M18.75 4.236c.983.143 1.955.317 2.917.52A6.003 6.003 0 0016.27 9.728M18.75 4.236V4.5a9.023 9.023 0 01-2.48 5.228" />
  </svg>
);

export default function TournamentsList({ tournaments, tournamentsUrl }: Props) {
  const hasTournaments = tournaments.length > 0;

  return (
    <div className="dash-card" aria-labelledby="tournaments-heading">
      <div className="dash-section-header">
        <h2 className="dash-section-title" id="tournaments-heading">
          <StarIcon />
          Nadchodzące turnieje
          {hasTournaments && <span className="section-badge">{tournaments.length}</span>}
        </h2>
        <a href={tournamentsUrl} className="dash-link-sm">Wszystkie →</a>
      </div>

      {hasTournaments ? (
        <>
          <div className="tourn-table-head">
            <span className="th-num">#</span>
            <span className="th-main">Turniej</span>
            <span className="th-type">Typ</span>
            <span className="th-players">Gracze</span>
            <span className="th-status">Status</span>
            <span className="th-join"></span>
          </div>
          <div className="tourn-table-body">
            {tournaments.map((t, i) => (
              <a key={t.id} className="dash-row tourn-row" href={t.href}>
                <span className="tourn-row__num">{String(i + 1).padStart(2, '0')}</span>
                <span className="tourn-row__name">{t.name}</span>
                <span className="tourn-row__type">{t.type}</span>
                <span className="tourn-row__players">{t.participants}</span>
                <span className={`tourn-row__status tourn-status--${t.status}`}>
                  {(t.status === 'active' || t.status === 'open') && (
                    <span className="tourn-status__dot" aria-hidden="true" />
                  )}
                  {t.statusLabel}
                </span>
                <span className="tourn-row__join">
                  {t.joined ? (
                    <span className="tourn-row__joined-badge">Zapisano</span>
                  ) : t.isRegOpen ? (
                    <span className="tourn-row__join-cta">Zapisz się</span>
                  ) : null}
                </span>
              </a>
            ))}
          </div>
          <div className="dash-card-footer">
            <a href={tournamentsUrl} className="dash-btn-secondary">+ Zapisz się do turnieju</a>
          </div>
        </>
      ) : (
        <div className="dash-empty-block">
          <div className="dash-empty-block__icon" aria-hidden="true">
            <TrophyIcon />
          </div>
          <p className="dash-empty-block__title">Brak nadchodzących turniejów</p>
          <p className="dash-empty-block__sub">Przeglądaj dostępne turnieje i zapisz się.</p>
          <div className="dash-empty-block__links">
            <a href={tournamentsUrl} className="dash-btn-primary">Przeglądaj turnieje →</a>
          </div>
        </div>
      )}
    </div>
  );
}
