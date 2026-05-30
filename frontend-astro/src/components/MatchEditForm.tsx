import { useState } from 'react';

interface Props {
  matchId: number;
  matchesUrl: string;
  initialSets: {
    p1_set1: string; p2_set1: string;
    p1_set2: string; p2_set2: string;
    p1_set3: string; p2_set3: string;
  };
  p1Label: string;
  p2Label: string;
}

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

export default function MatchEditForm({ matchId, matchesUrl, initialSets, p1Label, p2Label }: Props) {
  const [visible, setVisible] = useState(false);
  const [sets, setSets] = useState(initialSets);
  const [msg, setMsg] = useState('');
  const [msgColor, setMsgColor] = useState('');
  const [loading, setLoading] = useState(false);

  const update = (field: keyof typeof sets, val: string) => {
    setSets(prev => ({ ...prev, [field]: val }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMsg('');

    const getVal = (v: string): number | null => {
      if (v.trim() === '') return null;
      const n = parseInt(v, 10);
      return isNaN(n) ? null : n;
    };

    const v1p1 = getVal(sets.p1_set1), v1p2 = getVal(sets.p2_set1);
    if (v1p1 === null || v1p2 === null || v1p1 < 0 || v1p2 < 0) {
      setMsg('Set 1 jest wymagany — wpisz wynik dla obu stron.');
      setMsgColor('var(--tc-hot)');
      setLoading(false);
      return;
    }

    const v2p1 = getVal(sets.p1_set2), v2p2 = getVal(sets.p2_set2);
    if ((v2p1 === null) !== (v2p2 === null) || (v2p1 !== null && v2p1 < 0) || (v2p2 !== null && v2p2 < 0)) {
      setMsg('Wpisz wynik dla obu stron w secie 2.');
      setMsgColor('var(--tc-hot)');
      setLoading(false);
      return;
    }

    const v3p1 = getVal(sets.p1_set3), v3p2 = getVal(sets.p2_set3);
    if ((v3p1 === null) !== (v3p2 === null) || (v3p1 !== null && v3p1 < 0) || (v3p2 !== null && v3p2 < 0)) {
      setMsg('Wpisz wynik dla obu stron w secie 3.');
      setMsgColor('var(--tc-hot)');
      setLoading(false);
      return;
    }

    const body: Record<string, number | null> = {
      p1_set1: v1p1,
      p2_set1: v1p2,
      p1_set2: v2p1,
      p2_set2: v2p2,
      p1_set3: v3p1,
      p2_set3: v3p2,
    };

    try {
      const res = await fetch(`/api/matches/${matchId}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        setMsg('Zapisano!');
        setMsgColor('#22c55e');
        setTimeout(() => window.location.reload(), 800);
      } else {
        const err = await res.json().catch(() => ({}));
        setMsg(err.detail || Object.values(err)[0] || `Błąd ${res.status}`);
        setMsgColor('var(--tc-hot)');
        setLoading(false);
      }
    } catch {
      setMsg('Błąd sieci.');
      setMsgColor('var(--tc-hot)');
      setLoading(false);
    }
  };

  return (
    <>
      <div className="match-topbar">
        <nav className="breadcrumb" aria-label="Nawigacja okruszkowa" style={{ marginBottom: 0 }}>
          <a href={matchesUrl} className="breadcrumb__link">Mecze</a>
          <span className="breadcrumb__sep" aria-hidden="true">›</span>
          {!visible ? (
            <span className="breadcrumb__current">Mecz #{matchId}</span>
          ) : (
            <>
              <a href="#" onClick={(e) => { e.preventDefault(); setVisible(false); }} className="breadcrumb__link">Mecz #{matchId}</a>
              <span className="breadcrumb__sep" aria-hidden="true">›</span>
              <span className="breadcrumb__current">Edycja wyniku</span>
            </>
          )}
        </nav>

        {!visible && (
          <button
            className="tc-btn tc-btn-secondary tc-btn-sm"
            type="button"
            onClick={() => setVisible(true)}
          >
            Edytuj wynik
          </button>
        )}
      </div>

      {visible && (
        <div className="edit-card-container tc-card" style={{ marginTop: 20 }}>
          <div className="tc-card-header">
            <span className="tc-card-title">Edytuj wynik</span>
          </div>
          <form onSubmit={handleSubmit} noValidate style={{ padding: '16px 20px 20px' }}>
            <div className="edit-sets">
              {[1, 2, 3].map(s => {
                const p1Key = `p1_set${s}` as keyof typeof sets;
                const p2Key = `p2_set${s}` as keyof typeof sets;
                const required = s === 1;
                return (
                  <div key={s} className={`edit-set${!required ? ' edit-set--opt' : ''}`}>
                    <span className="edit-set-label">
                      Set {s} {required
                        ? <span className="edit-required">*</span>
                        : <span className="edit-optional">(opcjonalnie)</span>}
                    </span>
                    <div className="edit-set-row">
                      <div className="edit-set-col">
                        <span className="edit-set-who" title={p1Label}>{p1Label}</span>
                        <input
                          className="edit-num-input"
                          type="number" min={0} max={99}
                          placeholder={required ? '0' : '—'}
                          inputMode="numeric"
                          value={sets[p1Key]}
                          onChange={e => update(p1Key, e.target.value)}
                        />
                      </div>
                      <span className="edit-set-sep">:</span>
                      <div className="edit-set-col">
                        <span className="edit-set-who" title={p2Label}>{p2Label}</span>
                        <input
                          className="edit-num-input"
                          type="number" min={0} max={99}
                          placeholder={required ? '0' : '—'}
                          inputMode="numeric"
                          value={sets[p2Key]}
                          onChange={e => update(p2Key, e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="edit-form-hint">* Set 1 jest wymagany. Sety 2–3 wypełnij tylko jeśli były rozegrane.</p>
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
              <button type="submit" className="tc-btn tc-btn-primary tc-btn-sm" disabled={loading}>
                {loading ? 'Zapisuję…' : 'Zapisz wynik'}
              </button>
              <button type="button" className="tc-btn tc-btn-ghost tc-btn-sm" onClick={() => setVisible(false)}>
                Anuluj
              </button>
              {msg && <span style={{ fontSize: '0.82rem', color: msgColor }}>{msg}</span>}
            </div>
          </form>
        </div>
      )}
    </>
  );
}
