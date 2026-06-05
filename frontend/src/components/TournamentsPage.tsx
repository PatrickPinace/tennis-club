import { useState, useMemo } from 'react';

interface TournamentRow {
  id: number;
  name: string;
  status: string;
  tournamentType: string;
  participantCount: number;
  startDate: string | null;
  joined: boolean;
  href: string;
  matchesProgress: { done: number; total: number } | null;
}

interface FeaturedTournament {
  id: number;
  name: string;
  type: string;
  participants: number;
  total: number;
  done: number;
  href: string;
  isMine: boolean;
  standings: StandingRow[];
}

interface StandingRow {
  displayName: string;
  points: number;
  isMe: boolean;
}

interface Props {
  tournaments: TournamentRow[];
  featured: FeaturedTournament[];
  stats: {
    running: number;
    registration: number;
    myCount: number | null;
    finished: number;
  };
  createUrl: string;
}

type Filter = 'all' | 'mine' | 'open' | 'finished';

const TYPE_LABEL: Record<string, string> = {
  SGL: 'Eliminacja pojedyncza', DBE: 'Eliminacja podwójna',
  RND: 'Round Robin', LDR: 'Drabinka', AMR: 'Americano', SWS: 'System szwajcarski',
};

// Rozwinięcia skrótów — tooltip na nazwie typu turnieju w tabeli.
const TYPE_HINT: Record<string, string> = {
  RND: 'Round Robin — każdy gra z każdym, punkty sumowane w tabeli',
  LDR: 'Drabinka Liderów — gracze rzucają wyzwania wyżej notowanym i wspinają się w rankingu',
  AMR: 'Americano / Mexicano — rotacyjny format par; Mexicano = dynamiczne parowanie po każdej rundzie',
  DBE: 'Eliminacja podwójna — zawodnik odpada dopiero po dwóch przegranych (Winners + Losers Bracket)',
};

const STATUS_META: Record<string, { label: string; color: 'accent' | 'win' | 'muted' }> = {
  DRF: { label: 'Szkic', color: 'muted' },
  REG: { label: 'Rejestracja', color: 'win' },
  SCH: { label: 'Zaplanowany', color: 'muted' },
  ACT: { label: 'Trwa', color: 'accent' },
  FIN: { label: 'Zakończony', color: 'muted' },
  CNC: { label: 'Odwołany', color: 'muted' },
};

function FeaturedCard({ tournaments }: { tournaments: FeaturedTournament[] }) {
  const [current, setCurrent] = useState(0);
  if (tournaments.length === 0) return null;

  const t = tournaments[current];
  const progressPct = t.total > 0 ? Math.round(t.done / t.total * 100) : 0;

  const prev = () => setCurrent((current - 1 + tournaments.length) % tournaments.length);
  const next = () => setCurrent((current + 1) % tournaments.length);

  return (
    <div className="tr-featured">
      <div className="tr-featured__accent-bar" aria-hidden="true" />
      <div className="tr-featured__grid">
        <div className="tr-featured__info">
          <div className="tr-featured__top">
            <span className="tr-featured__badge">Trwa teraz</span>
            <span className="tr-featured__tag">
              {t.isMine ? 'Twój aktywny turniej' : 'Aktywny turniej'}
            </span>
            {tournaments.length > 1 && (
              <div className="tr-feat-nav" aria-label="Przełącz turniej">
                <button type="button" className="tr-feat-nav__btn" onClick={prev} aria-label="Poprzedni turniej">‹</button>
                <span className="tr-feat-nav__counter">{current + 1} / {tournaments.length}</span>
                <button type="button" className="tr-feat-nav__btn" onClick={next} aria-label="Następny turniej">›</button>
              </div>
            )}
          </div>
          <h2 className="tr-featured__name">{t.name}</h2>
          <div className="tr-featured__meta">
            Format {t.type} · {t.participants} uczestników
            {t.total > 0 && ` · runda ${t.done} z ${t.total}`}
          </div>

          {t.total > 0 && (
            <div className="tr-featured__progress">
              <div className="tr-progress-bar">
                <div className="tr-progress-bar__fill" style={{ width: `${progressPct}%` }} />
              </div>
              <div className="tr-progress-meta">
                <span>Postęp turnieju</span>
                <span className="tr-progress-val">{t.done} / {t.total} rundy</span>
              </div>
            </div>
          )}

          <div className="tr-featured__actions">
            <a href={t.href} className="tr-btn-primary">Zobacz tabelę →</a>
            <a href={t.href} className="tr-btn-secondary">Wyniki rund</a>
          </div>
        </div>

        {t.standings.length > 0 && (
          <div className="tr-featured__standings">
            <div className="tr-standings-label">AKTUALNE MIEJSCA</div>
            <div className="tr-standings-list">
              {t.standings.map((s, i) => (
                <div key={s.displayName} className={`tr-standing-row${s.isMe ? ' tr-standing-row--me' : ''}`}>
                  <span className={`tr-standing-pos${i === 0 ? ' tr-standing-pos--first' : ''}`}>{i + 1}</span>
                  <span className="tr-standing-name">
                    {s.displayName}
                    {s.isMe && <span className="tr-standing-me">TY</span>}
                  </span>
                  <span className={`tr-standing-pts${s.isMe ? ' tr-standing-pts--me' : ''}`}>
                    {s.points}
                  </span>
                  <span className="tr-standing-pkt">pkt</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TournamentTableRow({ t, index }: { t: TournamentRow; index: number }) {
  const sm = STATUS_META[t.status] ?? { label: t.status, color: 'muted' as const };
  const fillPct = t.participantCount > 0
    ? Math.min(100, Math.round(t.participantCount / Math.max(t.participantCount, 8) * 100))
    : 0;

  let dateLabel: string;
  if (t.status === 'ACT') dateLabel = 'Trwa';
  else if (t.status === 'FIN') dateLabel = 'Zakończony';
  else if (t.startDate) dateLabel = `Trwa od ${t.startDate}`;
  else dateLabel = '—';

  return (
    <a className="tr-row" href={t.href}>
      <div className="tr-row__idx">{String(index + 1).padStart(2, '0')}</div>
      <div className="tr-row__tournament">
        <div className="tr-row__name-line">
          <span className="tr-row__name">{t.name}</span>
          {t.joined && <span className="tr-row__joined-badge">Zapisano</span>}
        </div>
        <div className="tr-row__date">{dateLabel}</div>
      </div>
      <div className="tr-row__type">
        {TYPE_HINT[t.tournamentType]
          ? <abbr title={TYPE_HINT[t.tournamentType]}>{TYPE_LABEL[t.tournamentType] ?? t.tournamentType}</abbr>
          : (TYPE_LABEL[t.tournamentType] ?? t.tournamentType)
        }
      </div>
      <div className="tr-row__participants">
        <span className="tr-row__p-count">{t.participantCount}</span>
        <span className="tr-row__p-max">/ {Math.max(t.participantCount, 8)}</span>
        <div className="tr-row__p-bar">
          <div className={`tr-row__p-fill tr-row__p-fill--${sm.color}`} style={{ width: `${fillPct}%` }} />
        </div>
      </div>
      <div className={`tr-row__status tr-row__status--${sm.color}`}>
        {(sm.color === 'accent' || sm.color === 'win') && <span className="tr-row__status-dot" />}
        {sm.label}
      </div>
    </a>
  );
}

export default function TournamentsPage({ tournaments, featured, stats, createUrl }: Props) {
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = useMemo(() => {
    return tournaments.filter(t => {
      if (filter === 'mine') return t.joined;
      if (filter === 'open') return t.status === 'REG' || t.status === 'SCH';
      if (filter === 'finished') return t.status === 'FIN' || t.status === 'CNC';
      return true;
    });
  }, [tournaments, filter]);

  return (
    <>
      <div className="tr-mobile-cta">
        <a href={createUrl} className="tr-mobile-cta__btn">+ Utwórz turniej</a>
      </div>

      <div className="tr-stats">
        <div className="tr-stat-card tr-stat-card--accent">
          <div className="tr-stat-label">AKTYWNE</div>
          <div className="tr-stat-val" style={{ color: 'var(--tc-accent)' }}>{stats.running}</div>
          <div className="tr-stat-sub">trwają teraz</div>
        </div>
        <div className="tr-stat-card">
          <div className="tr-stat-label">W REJESTRACJI</div>
          <div className="tr-stat-val">{stats.registration}</div>
          <div className="tr-stat-sub">możesz dołączyć</div>
        </div>
        <div className="tr-stat-card">
          <div className="tr-stat-label">MOJE TURNIEJE</div>
          <div className="tr-stat-val">{stats.myCount ?? '—'}</div>
          <div className="tr-stat-sub">{stats.myCount !== null ? 'bierzesz udział' : 'zaloguj się'}</div>
        </div>
        <div className="tr-stat-card">
          <div className="tr-stat-label">ZAKOŃCZONE</div>
          <div className="tr-stat-val">{stats.finished}</div>
          <div className="tr-stat-sub">{stats.finished > 0 ? 'w historii' : 'brak'}</div>
        </div>
      </div>

      <FeaturedCard tournaments={featured} />

      <section className="tr-card">
        <div className="tr-card__header">
          <div className="tr-card__title-wrap">
            <span className="tr-card__dot" aria-hidden="true" />
            <h2 className="tr-card__title">WSZYSTKIE TURNIEJE</h2>
            <span className="tr-card__badge">{filtered.length}</span>
          </div>
          <div className="tr-segmented" role="group" aria-label="Filtr turniejów">
            {([
              { value: 'all', label: 'Wszystkie' },
              { value: 'mine', label: 'Moje' },
              { value: 'open', label: 'Otwarte' },
              { value: 'finished', label: 'Zakończone' },
            ] as const).map(o => (
              <button
                key={o.value}
                type="button"
                className={`tr-seg${filter === o.value ? ' tr-seg--active' : ''}`}
                onClick={() => setFilter(o.value)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>

        <div className="tr-thead">
          <span className="tr-th">#</span>
          <span className="tr-th">TURNIEJ</span>
          <span className="tr-th">TYP</span>
          <span className="tr-th tr-th--r">UCZESTNICY</span>
          <span className="tr-th">STATUS</span>
        </div>

        <div className="tr-tbody">
          {filtered.length === 0 ? (
            <div className="tr-empty">Brak turniejów do wyświetlenia.</div>
          ) : (
            filtered.map((t, i) => (
              <TournamentTableRow key={t.id} t={t} index={i} />
            ))
          )}
        </div>
      </section>
    </>
  );
}
