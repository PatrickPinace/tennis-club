import { useState, useRef, useEffect, useCallback } from 'react';

interface Props {
  myId: number;
  today: string;
  matchesUrl: string;
  isModal?: boolean;
  onClose?: () => void;
}

interface UserSuggestion {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
}

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

function UserAutocomplete({
  label,
  required,
  selectedId,
  onSelect,
  excludeIds,
  error,
}: {
  label: string;
  required?: boolean;
  selectedId: number | null;
  onSelect: (id: number | null, name: string) => void;
  excludeIds: Set<number>;
  error?: string;
}) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<UserSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const fetchUsers = useCallback(async (q: string) => {
    setStatus('Szukam…');
    try {
      const endpoint = q.length >= 2
        ? `/api/users/?search=${encodeURIComponent(q)}`
        : '/api/users/?suggest=1';
      const res = await fetch(endpoint, { credentials: 'include' });
      if (!res.ok) throw new Error();
      const data: UserSuggestion[] = await res.json();
      setSuggestions(data);
      setOpen(true);
    } catch {
      setSuggestions([]);
    } finally {
      setStatus('');
    }
  }, []);

  const handleInput = (val: string) => {
    setQuery(val);
    onSelect(null, '');
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => fetchUsers(val.trim()), 250);
  };

  const handleFocus = () => {
    if (!query.trim()) fetchUsers('');
  };

  const handleSelect = (u: UserSuggestion) => {
    const full = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username;
    setQuery(full);
    onSelect(u.id, full);
    setOpen(false);
  };

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  const filtered = suggestions.filter(u => !excludeIds.has(u.id) || u.id === selectedId);

  return (
    <div className="af-field">
      <label className="af-label">
        {label} {required && <span className="af-required">*</span>}
      </label>
      <div className="af-autocomplete" ref={wrapRef}>
        <input
          className="af-input"
          type="text"
          placeholder="Wpisz imię lub nazwisko..."
          autoComplete="off"
          value={query}
          onChange={e => handleInput(e.target.value)}
          onFocus={handleFocus}
          onKeyDown={e => { if (e.key === 'Escape') setOpen(false); }}
        />
        {open && (
          <ul className="af-suggestions" role="listbox" style={{ display: 'block' }}>
            {filtered.length === 0 ? (
              <li className="af-sug-empty">Brak wyników</li>
            ) : (
              filtered.map(u => {
                const full = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username;
                const sub = (u.first_name || u.last_name) ? u.username : '';
                return (
                  <li key={u.id} className="af-sug-item" role="option" onClick={() => handleSelect(u)}>
                    <span className="af-sug-name">{full}</span>
                    {sub && <span className="af-sug-sub">{sub}</span>}
                  </li>
                );
              })
            )}
          </ul>
        )}
        {status && <div className="af-search-status">{status}</div>}
      </div>
      {error && <p className="af-field-err">{error}</p>}
    </div>
  );
}

function SetInput({
  setNum,
  required,
  p1Label,
  p2Label,
  p1Val,
  p2Val,
  onP1Change,
  onP2Change,
  error,
}: {
  setNum: number;
  required?: boolean;
  p1Label: string;
  p2Label: string;
  p1Val: string;
  p2Val: string;
  onP1Change: (v: string) => void;
  onP2Change: (v: string) => void;
  error?: string;
}) {
  return (
    <div className={`af-set${!required ? ' af-set--opt' : ''}`}>
      <span className="af-set-label">
        Set {setNum} {required
          ? <span className="af-required">*</span>
          : <span className="af-optional">(opcjonalnie)</span>}
      </span>
      <div className="af-set-row">
        <div className="af-set-col">
          <span className="af-set-who">{p1Label}</span>
          <input
            className="af-num"
            type="number" min="0" max="99"
            placeholder={required ? '0' : '—'}
            inputMode="numeric"
            value={p1Val}
            onChange={e => onP1Change(e.target.value)}
          />
        </div>
        <span className="af-set-sep">:</span>
        <div className="af-set-col">
          <span className="af-set-who">{p2Label}</span>
          <input
            className="af-num"
            type="number" min="0" max="99"
            placeholder={required ? '0' : '—'}
            inputMode="numeric"
            value={p2Val}
            onChange={e => onP2Change(e.target.value)}
          />
        </div>
      </div>
      {error && <p className="af-field-err">{error}</p>}
    </div>
  );
}

export default function AddMatchForm({ myId, today, matchesUrl, isModal = false, onClose }: Props) {
  const [isDouble, setIsDouble] = useState(false);

  const [opponentId, setOpponentId] = useState<number | null>(null);
  const [partnerId, setPartnerId] = useState<number | null>(null);
  const [rival2Id, setRival2Id] = useState<number | null>(null);

  const [s1p1, setS1p1] = useState('');
  const [s1p2, setS1p2] = useState('');
  const [s2p1, setS2p1] = useState('');
  const [s2p2, setS2p2] = useState('');
  const [s3p1, setS3p1] = useState('');
  const [s3p2, setS3p2] = useState('');
  const [matchDate, setMatchDate] = useState(today);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState('');
  const [loading, setLoading] = useState(false);

  const clearErrors = () => { setErrors({}); setGeneralError(''); };

  const switchFormat = (dbl: boolean) => {
    setIsDouble(dbl);
    if (!dbl) {
      setPartnerId(null);
      setRival2Id(null);
    }
    clearErrors();
  };

  const intVal = (v: string): number | null => {
    if (v.trim() === '') return null;
    const n = parseInt(v, 10);
    return isNaN(n) ? null : n;
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};

    if (!opponentId) errs.opponent = 'Wybierz przeciwnika z listy.';

    if (isDouble) {
      if (!partnerId) errs.partner = 'Wybierz partnera z listy.';
      if (!rival2Id) errs.rival2 = 'Wybierz partnera przeciwnika z listy.';

      if (opponentId && partnerId && rival2Id) {
        const ids = [myId, opponentId, partnerId, rival2Id];
        if (new Set(ids).size < ids.length) {
          setGeneralError('Każdy gracz musi być inną osobą — ten sam gracz pojawia się dwukrotnie.');
          return false;
        }
      }
    }

    const v1p1 = intVal(s1p1), v1p2 = intVal(s1p2);
    if (v1p1 === null || v1p2 === null || v1p1 < 0 || v1p2 < 0)
      errs.s1 = 'Set 1 jest wymagany — wpisz wynik dla obu stron.';

    const v2p1 = intVal(s2p1), v2p2 = intVal(s2p2);
    if ((v2p1 === null) !== (v2p2 === null) || (v2p1 !== null && v2p1 < 0) || (v2p2 !== null && v2p2 < 0))
      errs.s2 = 'Wpisz wynik dla obu stron w secie 2.';

    const v3p1 = intVal(s3p1), v3p2 = intVal(s3p2);
    if ((v3p1 === null) !== (v3p2 === null) || (v3p1 !== null && v3p1 < 0) || (v3p2 !== null && v3p2 < 0))
      errs.s3 = 'Wpisz wynik dla obu stron w secie 3.';

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    if (!validate()) return;

    setLoading(true);

    const payload: Record<string, unknown> = {
      p2: opponentId,
      match_double: isDouble,
      match_date: matchDate,
      p1_set1: intVal(s1p1),
      p2_set1: intVal(s1p2),
    };

    if (isDouble) {
      payload.p3 = partnerId;
      payload.p4 = rival2Id;
    }

    const v2p1 = intVal(s2p1), v2p2 = intVal(s2p2);
    if (v2p1 !== null && v2p2 !== null) { payload.p1_set2 = v2p1; payload.p2_set2 = v2p2; }

    const v3p1 = intVal(s3p1), v3p2 = intVal(s3p2);
    if (v3p1 !== null && v3p2 !== null) { payload.p1_set3 = v3p1; payload.p2_set3 = v3p2; }

    try {
      const res = await fetch('/api/matches/create/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        window.location.href = matchesUrl + '?added=1';
        return;
      }

      let errMsg = 'Nie udało się zapisać meczu. Spróbuj ponownie.';
      try {
        const d = await res.json();
        if (typeof d === 'object') {
          const msgs = Object.entries(d)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' | ');
          if (msgs) errMsg = msgs;
        }
      } catch {}

      setGeneralError(errMsg);
    } catch {
      setGeneralError('Błąd połączenia. Sprawdź sieć i spróbuj ponownie.');
    } finally {
      setLoading(false);
    }
  };

  const excludeIds = new Set([myId]);
  if (opponentId) excludeIds.add(opponentId);
  if (partnerId) excludeIds.add(partnerId);
  if (rival2Id) excludeIds.add(rival2Id);

  const p1Label = isDouble ? 'Ty / P' : 'Ty';
  const p2Label = isDouble ? 'Rywal / P' : 'Rywal';

  return (
    <div className={isModal ? '' : 'add-wrap'}>
      {!isModal && (
        <div className="add-header">
          <h1 className="add-title">Dodaj mecz towarzyski</h1>
          <p className="add-subtitle">Zapisz wynik rozegranego meczu.</p>
        </div>
      )}

      {generalError && (
        <div className="add-alert add-alert--err" role="alert">{generalError}</div>
      )}

      <div className={isModal ? '' : 'tc-card add-card'}>
        <form onSubmit={handleSubmit} noValidate>

          <div className="af-field">
            <label className="af-label">Format</label>
            <div className="af-format-toggle" role="group" aria-label="Format meczu">
              <button type="button"
                className={`af-format-btn${!isDouble ? ' af-format-btn--active' : ''}`}
                onClick={() => switchFormat(false)}>Singiel</button>
              <button type="button"
                className={`af-format-btn${isDouble ? ' af-format-btn--active' : ''}`}
                onClick={() => switchFormat(true)}>Debel</button>
            </div>
          </div>

          {isDouble && (
            <div className="af-team-header">
              <span className="af-team-label af-team-label--you">Twoja drużyna</span>
            </div>
          )}

          {isDouble && (
            <UserAutocomplete
              label="Twój partner"
              required
              selectedId={partnerId}
              onSelect={(id) => setPartnerId(id)}
              excludeIds={excludeIds}
              error={errors.partner}
            />
          )}

          {isDouble && (
            <div className="af-team-header">
              <span className="af-team-label af-team-label--opp">Drużyna przeciwna</span>
            </div>
          )}

          <UserAutocomplete
            label={isDouble ? 'Główny przeciwnik' : 'Przeciwnik'}
            required
            selectedId={opponentId}
            onSelect={(id) => setOpponentId(id)}
            excludeIds={excludeIds}
            error={errors.opponent}
          />

          {isDouble && (
            <UserAutocomplete
              label="Partner przeciwnika"
              required
              selectedId={rival2Id}
              onSelect={(id) => setRival2Id(id)}
              excludeIds={excludeIds}
              error={errors.rival2}
            />
          )}

          <div className="af-field">
            <label className="af-label">Wynik</label>
            <div className="af-sets">
              <SetInput setNum={1} required p1Label={p1Label} p2Label={p2Label}
                p1Val={s1p1} p2Val={s1p2} onP1Change={setS1p1} onP2Change={setS1p2}
                error={errors.s1} />
              <SetInput setNum={2} p1Label={p1Label} p2Label={p2Label}
                p1Val={s2p1} p2Val={s2p2} onP1Change={setS2p1} onP2Change={setS2p2}
                error={errors.s2} />
              <SetInput setNum={3} p1Label={p1Label} p2Label={p2Label}
                p1Val={s3p1} p2Val={s3p2} onP1Change={setS3p1} onP2Change={setS3p2}
                error={errors.s3} />
            </div>
          </div>

          <div className="af-field">
            <label className="af-label" htmlFor="af-date">Data meczu</label>
            <input className="af-input af-input--date" type="date" id="af-date"
              value={matchDate} max={today}
              onChange={e => setMatchDate(e.target.value)} />
          </div>

          <div className="af-actions">
            {isModal ? (
              <button type="button" className="tc-btn tc-btn-ghost" onClick={onClose}>Anuluj</button>
            ) : (
              <a href={matchesUrl} className="tc-btn tc-btn-ghost">Anuluj</a>
            )}
            <button type="submit" className="tc-btn tc-btn-primary" disabled={loading}>
              {loading ? 'Zapisuję…' : 'Zapisz mecz'}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}
