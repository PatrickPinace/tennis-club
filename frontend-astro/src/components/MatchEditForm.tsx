import { useState } from 'react';

interface Props {
  matchId: number;
  initialSets: {
    p1_set1: string; p2_set1: string;
    p1_set2: string; p2_set2: string;
    p1_set3: string; p2_set3: string;
  };
}

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

function Spinner({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const inc = () => {
    const n = parseInt(value || '0', 10);
    onChange(String(isNaN(n) ? 1 : Math.min(n + 1, 99)));
  };
  const dec = () => {
    const n = parseInt(value || '0', 10);
    onChange(String(isNaN(n) ? 0 : Math.max(n - 1, 0)));
  };

  return (
    <div className="edit-spinner">
      <button type="button" className="edit-spin-btn edit-spin-up" tabIndex={-1} onClick={inc}>▲</button>
      <input
        className="edit-set-input"
        type="number" min={0} max={99}
        value={value}
        placeholder="—"
        onChange={e => onChange(e.target.value)}
      />
      <button type="button" className="edit-spin-btn edit-spin-down" tabIndex={-1} onClick={dec}>▼</button>
    </div>
  );
}

export default function MatchEditForm({ matchId, initialSets }: Props) {
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

    const body: Record<string, number | null> = {
      p1_set1: getVal(sets.p1_set1),
      p2_set1: getVal(sets.p2_set1),
      p1_set2: getVal(sets.p1_set2),
      p2_set2: getVal(sets.p2_set2),
      p1_set3: getVal(sets.p1_set3),
      p2_set3: getVal(sets.p2_set3),
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
        setMsgColor('var(--danger)');
        setLoading(false);
      }
    } catch {
      setMsg('Błąd sieci.');
      setMsgColor('var(--danger)');
      setLoading(false);
    }
  };

  return (
    <>
      <button
        className="tc-btn tc-btn-secondary tc-btn-sm"
        type="button"
        onClick={() => setVisible(v => !v)}
      >
        Edytuj wynik
      </button>

      {visible && (
        <div className="tc-card" style={{ marginTop: 20 }}>
          <div className="tc-card-header">
            <span className="tc-card-title">Edytuj wynik</span>
          </div>
          <form onSubmit={handleSubmit} noValidate style={{ padding: '16px 20px 20px' }}>
            <div className="edit-sets-row">
              {[1, 2, 3].map(s => {
                const p1Key = `p1_set${s}` as keyof typeof sets;
                const p2Key = `p2_set${s}` as keyof typeof sets;
                return (
                  <div key={s} className="edit-set-group">
                    <div className="edit-set-label">Set {s}{s === 1 ? ' *' : ''}</div>
                    <div className="edit-set-inputs">
                      <Spinner value={sets[p1Key]} onChange={v => update(p1Key, v)} />
                      <span className="edit-set-sep">:</span>
                      <Spinner value={sets[p2Key]} onChange={v => update(p2Key, v)} />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="edit-form-hint">* Set 1 jest wymagany. Sety 2–3 wypełnij tylko jeśli były rozegrane.</p>
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
              <button type="submit" className="tc-btn tc-btn-primary tc-btn-sm" disabled={loading}>
                Zapisz wynik
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
