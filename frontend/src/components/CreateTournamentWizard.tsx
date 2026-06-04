import { useState, useRef, useEffect } from 'react';

interface Props {
  manageUrl: string;
  tournamentBaseUrl: string;
}

type TournamentType = 'RND' | 'SGL' | 'DBE' | 'AMR' | 'LDR';

const TYPE_LABELS: Record<string, string> = {
  RND: 'Liga (Round Robin)',
  SGL: 'Eliminacja pojedyncza',
  DBE: 'Eliminacja podwójna',
  AMR: 'Americano / Mexicano',
  LDR: 'Drabinka Liderów',
};
const FORMAT_LABELS: Record<string, string> = { SNG: 'Singiel', DBL: 'Debel' };

const TYPE_NOTES: Record<string, string> = {
  RND: 'Panel zarządzania meczami i tabela ligowa dostępne dla Round Robin.',
  SGL: 'Eliminacja pojedyncza — drabinka z awansem zwycięzców.',
  DBE: 'Eliminacja podwójna — zawodnik odpada dopiero po dwóch przegranych (Winners + Losers Bracket).',
  AMR: 'Americano / Mexicano — tryb (stały / dynamiczny) wybierasz w następnym kroku.',
  LDR: 'Drabinka Liderów — gracze sami rzucają wyzwania i wspinają się w górę rankingu.',
};

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatDatePL(iso: string): string {
  try {
    return new Date(iso).toLocaleString('pl-PL', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function Spinner({ label, hint, value, onChange, min, max, step = 1 }: {
  label: string; hint?: string; value: number;
  onChange: (v: number) => void; min: number; max: number; step?: number;
}) {
  const inc = () => onChange(Math.min(max, parseFloat((value + step).toFixed(2))));
  const dec = () => onChange(Math.max(min, parseFloat((value - step).toFixed(2))));

  return (
    <div className="cfg-spinner-col">
      <span className="cfg-spinner-label">{label}</span>
      <div className="cfg-spinner">
        <button type="button" className="cfg-spin-btn" onClick={inc} aria-label="Więcej">&#9650;</button>
        <input
          className="cfg-spin-input" type="number"
          min={min} max={max} step={step}
          value={value}
          onChange={e => {
            const v = parseFloat(e.target.value);
            if (!isNaN(v)) onChange(Math.min(max, Math.max(min, v)));
          }}
        />
        <button type="button" className="cfg-spin-btn" onClick={dec} aria-label="Mniej">&#9660;</button>
      </div>
      {hint && <span className="cfg-hint">{hint}</span>}
    </div>
  );
}

function SumRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="sum-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function CreateTournamentWizard({ manageUrl, tournamentBaseUrl }: Props) {
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Step 1
  const [name, setName] = useState('');
  const [nameWarn, setNameWarn] = useState('');
  const [desc, setDesc] = useState('');
  const [type, setType] = useState<TournamentType>('RND');
  const [format, setFormat] = useState<'SNG' | 'DBL'>('SNG');
  const [rank, setRank] = useState(1);
  const [isRanked, setIsRanked] = useState(true);
  const [startDate, setStartDate] = useState(() => {
    const now = new Date();
    now.setSeconds(0, 0);
    return now.toISOString().slice(0, 16);
  });
  const [endDate, setEndDate] = useState('');

  // Step 2 — RND
  const [setsToWin, setSetsToWin] = useState(2);
  const [gamesPerSet, setGamesPerSet] = useState(6);
  const [maxPart, setMaxPart] = useState(16);
  const [ptsWin, setPtsWin] = useState(2);
  const [ptsLoss, setPtsLoss] = useState(1);
  const [ptsSetWin, setPtsSetWin] = useState(0.5);
  const [ptsSetLoss, setPtsSetLoss] = useState(0);
  const [ptsGemWin, setPtsGemWin] = useState(0.1);
  const [ptsGemLoss, setPtsGemLoss] = useState(-0.1);
  const [ptsStbWin, setPtsStbWin] = useState(0.05);
  const [ptsStbLoss, setPtsStbLoss] = useState(-0.05);
  const [tiebreak, setTiebreak] = useState('HEAD');

  // Step 2 — SGL
  const [sglSeeding, setSglSeeding] = useState('RANDOM');
  const [sglThirdPlace, setSglThirdPlace] = useState(true);

  // Step 2 — DBE
  const [dbeSeeding, setDbeSeeding] = useState('RANDOM');

  // Step 2 — AMR
  const [amrRounds, setAmrRounds] = useState(7);
  const [amrPpm, setAmrPpm] = useState(32);
  const [amrSched, setAmrSched] = useState<'STATIC' | 'DYNAMIC'>('STATIC');

  // Step 2 — LDR
  const [ldrRange, setLdrRange] = useState(3);
  const [ldrSeeding, setLdrSeeding] = useState('SEEDING');

  // Name duplicate check
  const nameTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const checkName = (val: string) => {
    setName(val);
    setNameWarn('');
    if (nameTimerRef.current) clearTimeout(nameTimerRef.current);
    if (val.trim().length < 3) return;
    nameTimerRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/tournaments/check-name/?name=${encodeURIComponent(val.trim())}`, {
          credentials: 'include',
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.exists) {
          setNameWarn(`Turniej o nazwie „${val.trim()}" już istnieje (${data.count}). Możesz mimo to kontynuować.`);
        }
      } catch {}
    }, 500);
  };

  const goTo = (s: number) => {
    setError('');
    setStep(s);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const validateStep1 = () => {
    if (!name.trim()) { setError('Nazwa turnieju jest wymagana.'); return false; }
    if (name.trim().length > 200) { setError('Nazwa może mieć maksymalnie 200 znaków.'); return false; }
    if (startDate && endDate && endDate <= startDate) {
      setError('Data zakończenia musi być późniejsza niż data rozpoczęcia.');
      return false;
    }
    return true;
  };

  const validateStep2 = () => {
    if (type === 'RND') {
      if (setsToWin < 1) { setError('Sety do wygrania muszą wynosić ≥ 1.'); return false; }
      if (gamesPerSet < 1) { setError('Liczba gemów w secie musi wynosić ≥ 1.'); return false; }
      if (maxPart < 2) { setError('Maks. uczestników musi wynosić ≥ 2.'); return false; }
      if (ptsWin < ptsLoss) { setError('Punkty za wygraną muszą być ≥ punkty za przegraną.'); return false; }
    }
    return true;
  };

  const handleNext1 = () => {
    setError('');
    if (!validateStep1()) return;
    goTo(2);
  };

  const handleNext2 = () => {
    setError('');
    if (!validateStep2()) return;
    goTo(3);
  };

  const handleCreate = async () => {
    setError('');
    setLoading(true);

    try {
      await fetch('/api/auth/csrf/', { credentials: 'include' });

      const body: Record<string, unknown> = {
        name: name.trim(),
        tournament_type: type,
        match_format: format,
        rank,
        is_ranked: isRanked,
        description: desc.trim(),
      };
      if (startDate) body.start_date = startDate;
      if (endDate) body.end_date = endDate;

      const createRes = await fetch('/api/tournaments/create/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify(body),
      });

      const createData = await createRes.json().catch(() => ({}));

      if (!createRes.ok) {
        setError(createData.detail ?? `Błąd tworzenia turnieju (${createRes.status}).`);
        setLoading(false);
        return;
      }

      const tournamentId: number = createData.id;
      const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() };

      if (type === 'SGL') {
        try {
          await fetch(`/api/tournaments/${tournamentId}/config/sgl/`, {
            method: 'POST', credentials: 'include', headers,
            body: JSON.stringify({ initial_seeding: sglSeeding, third_place_match: sglThirdPlace }),
          });
        } catch {}
      }

      if (type === 'DBE') {
        try {
          await fetch(`/api/tournaments/${tournamentId}/config/sgl/`, {
            method: 'POST', credentials: 'include', headers,
            body: JSON.stringify({ initial_seeding: dbeSeeding }),
          });
        } catch {}
      }

      if (type === 'AMR') {
        try {
          await fetch(`/api/tournaments/${tournamentId}/config/amr/`, {
            method: 'POST', credentials: 'include', headers,
            body: JSON.stringify({
              points_per_match: amrPpm,
              number_of_rounds: amrRounds,
              scheduling_type: amrSched,
            }),
          });
        } catch {}
      }

      if (type === 'LDR') {
        try {
          await fetch(`/api/tournaments/${tournamentId}/config/ldr/`, {
            method: 'POST', credentials: 'include', headers,
            body: JSON.stringify({ challenge_range: ldrRange, initial_seeding: ldrSeeding }),
          });
        } catch {}
      }

      if (type === 'RND') {
        try {
          await fetch(`/api/tournaments/${tournamentId}/config/`, {
            method: 'PATCH', credentials: 'include', headers,
            body: JSON.stringify({
              sets_to_win: setsToWin,
              games_per_set: gamesPerSet,
              max_participants: maxPart,
              points_for_win: ptsWin,
              points_for_loss: ptsLoss,
              points_for_set_win: ptsSetWin,
              points_for_set_loss: ptsSetLoss,
              points_for_gem_win: ptsGemWin,
              points_for_gem_loss: ptsGemLoss,
              points_for_supertiebreak_win: ptsStbWin,
              points_for_supertiebreak_loss: ptsStbLoss,
              tie_breaker_priority: tiebreak,
            }),
          });
        } catch {}
      }

      window.location.href = `${tournamentBaseUrl}/${tournamentId}?created=1#org-panel`;
    } catch {
      setError('Błąd połączenia z API. Sprawdź połączenie i spróbuj ponownie.');
      setLoading(false);
    }
  };

  const pane2Title = {
    RND: 'Konfiguracja punktacji',
    SGL: 'Konfiguracja drabinki',
    DBE: 'Konfiguracja eliminacji podwójnej',
    AMR: 'Konfiguracja Americano',
    LDR: 'Konfiguracja Drabinki Liderów',
  }[type];

  const pane2Sub = {
    RND: 'Wartości domyślne działają dla większości lig. Możesz je zmienić też po utworzeniu.',
    SGL: 'Opcje eliminacji pojedynczej. Możesz je zmienić też po utworzeniu.',
    DBE: 'Zawodnik odpada dopiero po dwóch przegranych. Opcje rozstawienia jak w SGL.',
    AMR: 'Ustaw liczbę rund i pulę punktów na mecz. Harmonogram generowany automatycznie.',
    LDR: 'Ustaw zasięg wyzwań i sposób rozstawienia. Możesz zmienić po utworzeniu.',
  }[type];

  const tiebreakOptions = [
    { value: 'HEAD', label: 'Bezpośrednie spotkanie' },
    { value: 'SETS', label: 'Bilans setów' },
    { value: 'GAMES', label: 'Bilans gemów' },
  ];

  const stepClass = (s: number) => {
    if (s === step) return 'wiz-step wiz-step--active';
    if (s < step) return 'wiz-step wiz-step--done';
    return 'wiz-step';
  };

  return (
    <div className="wiz-wrap">
      {/* Progress */}
      <div className="wiz-progress" aria-label="Postęp kreatora">
        <div className="wiz-steps">
          <div className={stepClass(1)}>
            <div className="wiz-step__dot">1</div>
            <span className="wiz-step__label">Podstawy</span>
          </div>
          <div className="wiz-step-connector" />
          <div className={stepClass(2)}>
            <div className="wiz-step__dot">2</div>
            <span className="wiz-step__label">Konfiguracja</span>
          </div>
          <div className="wiz-step-connector" />
          <div className={stepClass(3)}>
            <div className="wiz-step__dot">3</div>
            <span className="wiz-step__label">Podsumowanie</span>
          </div>
        </div>
      </div>

      <div className="tc-card wiz-card">
        {error && <div className="wiz-alert wiz-alert--err" role="alert">{error}</div>}

        {/* Step 1 */}
        {step === 1 && (
          <div className="wiz-pane">
            <h2 className="wiz-pane__title">Podstawowe informacje</h2>

            <div className="cr-field">
              <label className="cr-label" htmlFor="cr-name">Nazwa turnieju <span className="cr-required">*</span></label>
              <input id="cr-name" type="text" className="cr-input" maxLength={200}
                placeholder="np. Liga wiosenna 2026" autoComplete="off"
                value={name} onChange={e => checkName(e.target.value)} />
              {nameWarn && <span className="cr-hint cr-hint--warn">{nameWarn}</span>}
            </div>

            <div className="cr-field">
              <label className="cr-label" htmlFor="cr-desc">Opis</label>
              <textarea id="cr-desc" className="cr-input cr-textarea" rows={2}
                placeholder="Opcjonalny opis zasad, miejsca, kontaktu…"
                value={desc} onChange={e => setDesc(e.target.value)} />
            </div>

            <div className="cr-row">
              <div className="cr-field">
                <label className="cr-label" htmlFor="cr-type">Typ turnieju</label>
                <select id="cr-type" className="cr-input cr-select"
                  value={type} onChange={e => setType(e.target.value as TournamentType)}>
                  <option value="RND">Liga (Round Robin)</option>
                  <option value="SGL">Eliminacja pojedyncza</option>
                  <option value="DBE">Eliminacja podwójna</option>
                  <option value="AMR">Americano / Mexicano</option>
                  <option value="LDR">Drabinka Liderów</option>
                </select>
                <span className="cr-hint">{TYPE_NOTES[type]}</span>
              </div>
              <div className="cr-field">
                <label className="cr-label" htmlFor="cr-format">Format</label>
                <select id="cr-format" className="cr-input cr-select"
                  value={format} onChange={e => setFormat(e.target.value as 'SNG' | 'DBL')}>
                  <option value="SNG">Singiel (1 vs 1)</option>
                  <option value="DBL">Debel (2 vs 2)</option>
                </select>
              </div>
              <div className="cr-field cr-field--sm">
                <label className="cr-label" htmlFor="cr-rank">Ranga</label>
                <select id="cr-rank" className="cr-input cr-select"
                  value={rank} onChange={e => setRank(Number(e.target.value))}>
                  <option value={1}>1</option>
                  <option value={2}>2</option>
                  <option value={3}>3</option>
                </select>
              </div>
            </div>

            <div className="cr-row" style={{ marginTop: '4px' }}>
              <div className="cr-field">
                <label className="cr-checkbox-label">
                  <input type="checkbox" checked={isRanked} onChange={e => setIsRanked(e.target.checked)} />
                  <span>Turniej rankingowy</span>
                </label>
                <span className="cr-hint">Odznacz, jeśli to turniej towarzyski — wyniki nie będą wliczane do globalnego rankingu.</span>
              </div>
            </div>

            <div className="cr-row">
              <div className="cr-field">
                <label className="cr-label" htmlFor="cr-start">Data rozpoczęcia</label>
                <input id="cr-start" type="datetime-local" className="cr-input"
                  value={startDate} onChange={e => setStartDate(e.target.value)} />
              </div>
              <div className="cr-field">
                <label className="cr-label" htmlFor="cr-end">Data zakończenia</label>
                <input id="cr-end" type="datetime-local" className="cr-input"
                  value={endDate} onChange={e => setEndDate(e.target.value)} />
              </div>
            </div>

            <div className="wiz-actions">
              <button type="button" className="tc-btn tc-btn-primary" onClick={handleNext1}>Dalej →</button>
              <a href={manageUrl} className="tc-btn tc-btn-ghost">Anuluj</a>
            </div>
          </div>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div className="wiz-pane">
            <h2 className="wiz-pane__title">{pane2Title}</h2>
            <p className="wiz-pane__sub">{pane2Sub}</p>

            {type === 'RND' && (
              <>
                <div className="cfg-group-label">Mechanika meczu</div>
                <div className="cfg-spinners-row">
                  <Spinner label="Sety do wygrania" value={setsToWin} onChange={setSetsToWin} min={1} max={5} hint='2 → „2 z 3"' />
                  <Spinner label="Gemy w secie" value={gamesPerSet} onChange={setGamesPerSet} min={1} max={12} />
                  <Spinner label="Maks. uczestników" value={maxPart} onChange={setMaxPart} min={2} max={128} />
                </div>

                <div className="cfg-group-label" style={{ marginTop: '20px' }}>Punkty za mecz</div>
                <div className="cfg-spinners-row">
                  <Spinner label="Za wygraną" value={ptsWin} onChange={setPtsWin} min={-100} max={100} step={0.5} />
                  <Spinner label="Za przegraną" value={ptsLoss} onChange={setPtsLoss} min={-100} max={100} step={0.5} />
                </div>

                <div className="cfg-group-label" style={{ marginTop: '16px' }}>Punkty za sety</div>
                <div className="cfg-spinners-row">
                  <Spinner label="Za wygrany set" value={ptsSetWin} onChange={setPtsSetWin} min={-100} max={100} step={0.5} />
                  <Spinner label="Za przegrany set" value={ptsSetLoss} onChange={setPtsSetLoss} min={-100} max={100} step={0.5} />
                </div>

                <div className="cfg-group-label" style={{ marginTop: '16px' }}>Punkty za gemy</div>
                <div className="cfg-spinners-row">
                  <Spinner label="Za wygrany gem" value={ptsGemWin} onChange={setPtsGemWin} min={-100} max={100} step={0.1} />
                  <Spinner label="Za przegrany gem" value={ptsGemLoss} onChange={setPtsGemLoss} min={-100} max={100} step={0.1} />
                </div>

                <div className="cfg-group-label" style={{ marginTop: '16px' }}>Super tie-break (STB)</div>
                <div className="cfg-spinners-row">
                  <Spinner label="Za wygrany punkt" value={ptsStbWin} onChange={setPtsStbWin} min={-100} max={100} step={0.05} />
                  <Spinner label="Za przegrany punkt" value={ptsStbLoss} onChange={setPtsStbLoss} min={-100} max={100} step={0.05} />
                </div>

                <div className="cfg-group-label" style={{ marginTop: '20px' }}>Rozbijanie remisów</div>
                <div className="cr-field" style={{ maxWidth: '380px', marginBottom: 0 }}>
                  <select className="cr-input cr-select" value={tiebreak} onChange={e => setTiebreak(e.target.value)}>
                    {tiebreakOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
              </>
            )}

            {type === 'SGL' && (
              <>
                <div className="cfg-group-label">Rozstawienie</div>
                <div className="cr-field" style={{ maxWidth: '340px' }}>
                  <label className="cr-label">Kolejność w drabince</label>
                  <select className="cr-input cr-select" value={sglSeeding} onChange={e => setSglSeeding(e.target.value)}>
                    <option value="RANDOM">Losowe (brak rozstawienia)</option>
                    <option value="SEEDING">Według rozstawienia (seed_number)</option>
                  </select>
                  <span className="cr-hint">Przy losowym — uczestnik bez seed_number trafia na przypadkową pozycję.</span>
                </div>
                <div className="cfg-group-label" style={{ marginTop: '20px' }}>Opcje</div>
                <label className="cr-field cr-field--checkbox">
                  <input type="checkbox" checked={sglThirdPlace} onChange={e => setSglThirdPlace(e.target.checked)} />
                  <span>Mecz o 3. miejsce</span>
                </label>
                <span className="cr-hint" style={{ marginTop: '-10px', marginBottom: '16px', display: 'block' }}>Przegrani z półfinałów rozegrają mecz o brązowy medal.</span>
              </>
            )}

            {type === 'DBE' && (
              <>
                <div className="cfg-group-label">Rozstawienie</div>
                <div className="cr-field" style={{ maxWidth: '340px' }}>
                  <label className="cr-label">Kolejność w drabince</label>
                  <select className="cr-input cr-select" value={dbeSeeding} onChange={e => setDbeSeeding(e.target.value)}>
                    <option value="RANDOM">Losowe (brak rozstawienia)</option>
                    <option value="SEEDING">Według rozstawienia (seed_number)</option>
                  </select>
                  <span className="cr-hint">Przy losowym — uczestnik bez seed_number trafia na przypadkową pozycję.</span>
                </div>
                <p className="cr-hint" style={{ marginTop: '8px' }}>Eliminacja podwójna — zawodnik odpada dopiero po dwóch przegranych. Brak meczu o 3. miejsce.</p>
              </>
            )}

            {type === 'AMR' && (
              <>
                <div className="cfg-group-label">Tryb rozgrywek</div>
                <div className="cr-field" style={{ maxWidth: '400px', marginBottom: '18px' }}>
                  <label className="cr-label">Format</label>
                  <select className="cr-input cr-select" value={amrSched} onChange={e => setAmrSched(e.target.value as 'STATIC' | 'DYNAMIC')}>
                    <option value="STATIC">Americano (stały harmonogram)</option>
                    <option value="DYNAMIC">Mexicano (dynamiczne parowanie co rundę)</option>
                  </select>
                  <span className="cr-hint">
                    {amrSched === 'DYNAMIC'
                      ? 'Mexicano — parowanie co rundę na podstawie aktualnego rankingu punktowego.'
                      : 'Americano — harmonogram wszystkich rund ustalany z góry na podstawie rotacji.'}
                  </span>
                </div>
                <div className="cfg-group-label">Mecze</div>
                <div className="cfg-spinners-row">
                  <Spinner label="Liczba rund" value={amrRounds} onChange={setAmrRounds} min={1} max={99} hint="maks. n-1 dla n graczy" />
                  <Spinner label="Punkty na mecz" value={amrPpm} onChange={setAmrPpm} min={1} max={999} step={4} hint="np. 32 = suma gemów w meczu" />
                </div>
              </>
            )}

            {type === 'LDR' && (
              <>
                <div className="cfg-group-label">Zasięg wyzwań</div>
                <div className="cfg-spinners-row">
                  <Spinner label="Zasięg wyzwania" value={ldrRange} onChange={setLdrRange} min={1} max={20} hint="Gracz może wyzwać do N pozycji wyżej" />
                </div>
                <div className="cfg-group-label" style={{ marginTop: '20px' }}>Rozstawienie początkowe</div>
                <div className="cr-field" style={{ maxWidth: '400px', marginBottom: 0 }}>
                  <label className="cr-label">Kolejność na starcie</label>
                  <select className="cr-input cr-select" value={ldrSeeding} onChange={e => setLdrSeeding(e.target.value)}>
                    <option value="SEEDING">Według rozstawienia (seed_number)</option>
                    <option value="RANDOM">Losowe</option>
                  </select>
                  <span className="cr-hint">Ustala pozycje graczy po zamknięciu rejestracji. Pozycje zmieniają się przez wyzwania.</span>
                </div>
              </>
            )}

            <div className="wiz-actions">
              <button type="button" className="tc-btn tc-btn-ghost" onClick={() => goTo(1)}>← Wstecz</button>
              <button type="button" className="tc-btn tc-btn-primary" onClick={handleNext2}>Dalej →</button>
            </div>
          </div>
        )}

        {/* Step 3 — Summary */}
        {step === 3 && (
          <div className="wiz-pane">
            <h2 className="wiz-pane__title">Podsumowanie</h2>
            <p className="wiz-pane__sub">Sprawdź dane przed utworzeniem turnieju.</p>

            <div className="sum-grid">
              <div className="sum-group">
                <div className="sum-group-label">Turniej</div>
                <SumRow label="Nazwa" value={name.trim()} />
                <SumRow label="Typ" value={TYPE_LABELS[type] ?? type} />
                <SumRow label="Format" value={FORMAT_LABELS[format] ?? format} />
                <SumRow label="Ranga" value={String(rank)} />
                <SumRow label="Rankingowy" value={isRanked ? 'Tak' : 'Nie (towarzyski)'} />
                {desc.trim() && <SumRow label="Opis" value={desc.trim()} />}
                <SumRow label="Data rozpoczęcia" value={startDate ? formatDatePL(startDate) : '—'} />
                <SumRow label="Data zakończenia" value={endDate ? formatDatePL(endDate) : '—'} />
              </div>

              {type === 'RND' && (
                <>
                  <div className="sum-group">
                    <div className="sum-group-label">Mechanika meczu</div>
                    <SumRow label="Sety do wygrania" value={String(setsToWin)} />
                    <SumRow label="Gemy w secie" value={String(gamesPerSet)} />
                    <SumRow label="Maks. uczestników" value={String(maxPart)} />
                    <SumRow label="Rozbijanie remisów" value={tiebreakOptions.find(o => o.value === tiebreak)?.label ?? tiebreak} />
                  </div>
                  <div className="sum-group">
                    <div className="sum-group-label">Punkty za mecz</div>
                    <SumRow label="Wygrana" value={`+${ptsWin} pkt`} />
                    <SumRow label="Przegrana" value={`+${ptsLoss} pkt`} />
                    <SumRow label="Wygrany set" value={`+${ptsSetWin} pkt`} />
                    <SumRow label="Przegrany set" value={`${ptsSetLoss} pkt`} />
                  </div>
                </>
              )}

              {type === 'SGL' && (
                <div className="sum-group">
                  <div className="sum-group-label">Eliminacja pojedyncza</div>
                  <SumRow label="Rozstawienie" value={sglSeeding === 'RANDOM' ? 'Losowe' : 'Według rozstawienia'} />
                  <SumRow label="Mecz o 3. miejsce" value={sglThirdPlace ? 'Tak' : 'Nie'} />
                </div>
              )}

              {type === 'DBE' && (
                <div className="sum-group">
                  <div className="sum-group-label">Eliminacja podwójna</div>
                  <SumRow label="Rozstawienie" value={dbeSeeding === 'RANDOM' ? 'Losowe' : 'Według rozstawienia'} />
                  <SumRow label="Mecz o 3. miejsce" value="Nie (niedostępne)" />
                </div>
              )}

              {type === 'AMR' && (
                <div className="sum-group">
                  <div className="sum-group-label">{amrSched === 'DYNAMIC' ? 'Mexicano' : 'Americano'}</div>
                  <SumRow label="Tryb" value={amrSched === 'DYNAMIC' ? 'Mexicano (dynamiczne parowanie)' : 'Americano (stały harmonogram)'} />
                  <SumRow label="Liczba rund" value={String(amrRounds)} />
                  <SumRow label="Punkty na mecz" value={String(amrPpm)} />
                </div>
              )}

              {type === 'LDR' && (
                <div className="sum-group">
                  <div className="sum-group-label">Drabinka Liderów</div>
                  <SumRow label="Zasięg wyzwania" value={`±${ldrRange} pozycji`} />
                  <SumRow label="Rozstawienie" value={ldrSeeding === 'RANDOM' ? 'Losowe' : 'Według rozstawienia'} />
                </div>
              )}
            </div>

            <div className="wiz-actions">
              <button type="button" className="tc-btn tc-btn-ghost" onClick={() => goTo(2)}>← Wstecz</button>
              <button type="button" className="tc-btn tc-btn-primary" onClick={handleCreate} disabled={loading}>
                {loading ? 'Tworzenie…' : 'Utwórz turniej'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
