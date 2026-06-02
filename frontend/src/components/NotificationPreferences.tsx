import { useState, useEffect, useCallback } from 'react';

interface PrefGroup {
  key: string;
  label: string;
  description: string;
  enabled: boolean;
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

function getApiBase(): string {
  return (window as any)._API ?? '';
}

async function getCsrf(apiBase: string): Promise<string> {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  if (m) return m[1];
  try {
    await fetch(`${apiBase}/api/auth/me/`, { credentials: 'include' });
    const m2 = document.cookie.match(/csrftoken=([^;]+)/);
    return m2 ? m2[1] : '';
  } catch {
    return '';
  }
}

export default function NotificationPreferences() {
  const [prefs, setPrefs] = useState<PrefGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>('idle');

  useEffect(() => {
    const api = getApiBase();
    fetch(`${api}/api/notifications/preferences/`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then((data: PrefGroup[]) => setPrefs(data))
      .catch(() => setPrefs([]))
      .finally(() => setLoading(false));
  }, []);

  const toggle = useCallback(async (key: string, newVal: boolean) => {
    // Optimistic update
    setPrefs(prev => prev.map(p => p.key === key ? { ...p, enabled: newVal } : p));
    setSaveState('saving');

    const api = getApiBase();
    const csrf = await getCsrf(api);
    try {
      const r = await fetch(`${api}/api/notifications/preferences/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: newVal }),
      });
      if (!r.ok) throw new Error(String(r.status));
      const updated: PrefGroup[] = await r.json();
      setPrefs(updated);
      setSaveState('saved');
      setTimeout(() => setSaveState('idle'), 2000);
    } catch {
      // Rollback
      setPrefs(prev => prev.map(p => p.key === key ? { ...p, enabled: !newVal } : p));
      setSaveState('error');
      setTimeout(() => setSaveState('idle'), 3000);
    }
  }, []);

  if (loading) {
    return (
      <div className="pref-wrap">
        <div className="pref-loading">Ładowanie ustawień…</div>
      </div>
    );
  }

  if (!prefs.length) return null;

  return (
    <div className="pref-wrap">
      <div className="pref-header">
        <h2 className="pref-title">Ustawienia powiadomień</h2>
        <p className="pref-sub">Wybierz, o czym chcesz być powiadamiany.</p>
      </div>

      <div className="tc-card pref-card">
        {prefs.map((p, i) => (
          <div
            key={p.key}
            className={`pref-row${i < prefs.length - 1 ? ' pref-row--border' : ''}`}
          >
            <div className="pref-row__text">
              <span className="pref-row__label">{p.label}</span>
              <span className="pref-row__desc">{p.description}</span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={p.enabled}
              aria-label={`${p.label}: ${p.enabled ? 'włączone' : 'wyłączone'}`}
              className={`pref-toggle${p.enabled ? ' pref-toggle--on' : ''}`}
              onClick={() => toggle(p.key, !p.enabled)}
              disabled={saveState === 'saving'}
            >
              <span className="pref-toggle__knob" />
            </button>
          </div>
        ))}
      </div>

      <div
        className={`pref-status pref-status--${saveState}`}
        aria-live="polite"
      >
        {saveState === 'saving' && 'Zapisuję…'}
        {saveState === 'saved' && '✓ Zapisano'}
        {saveState === 'error' && 'Błąd zapisu. Spróbuj ponownie.'}
      </div>
    </div>
  );
}
