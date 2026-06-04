import { useState, useEffect } from 'react';

type Mode = 'request' | 'confirm';
type Status = 'idle' | 'loading' | 'success' | 'error';

function getCsrf(): string {
  return document.cookie.split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))?.split('=')[1] ?? '';
}

export default function ResetPasswordForm() {
  const [mode,    setMode]    = useState<Mode>('request');
  const [token,   setToken]   = useState('');
  const [email,   setEmail]   = useState('');
  const [pass1,   setPass1]   = useState('');
  const [pass2,   setPass2]   = useState('');
  const [status,  setStatus]  = useState<Status>('idle');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get('token');
    if (t) { setToken(t); setMode('confirm'); }
  }, []);

  async function handleRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus('loading');
    try {
      await fetch('/api/auth/password/reset/request/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({ email: email.trim() }),
      });
      // Zawsze success — nie ujawniamy czy email istnieje
      setStatus('success');
    } catch {
      setStatus('error');
      setMessage('Błąd sieci. Spróbuj ponownie.');
    }
  }

  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault();
    if (pass1 !== pass2) { setStatus('error'); setMessage('Hasła nie są identyczne.'); return; }
    if (pass1.length < 8) { setStatus('error'); setMessage('Hasło musi mieć co najmniej 8 znaków.'); return; }
    setStatus('loading');
    setMessage('');
    try {
      const res = await fetch('/api/auth/password/reset/confirm/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({ token, new_password: pass1, new_password2: pass2 }),
      });
      const data = await res.json();
      if (data.success) {
        setStatus('success');
      } else {
        setStatus('error');
        setMessage(data.error ?? 'Wystąpił błąd.');
      }
    } catch {
      setStatus('error');
      setMessage('Błąd sieci. Spróbuj ponownie.');
    }
  }

  const mismatch = pass2.length > 0 && pass1 !== pass2;
  const tooShort  = pass1.length > 0 && pass1.length < 8;

  if (mode === 'request') {
    if (status === 'success') return (
      <div className="pw-success">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
        </svg>
        Jeśli podany adres email jest w naszej bazie, wysłaliśmy na niego link do zresetowania hasła. Sprawdź skrzynkę (i folder spam).
      </div>
    );
    return (
      <form className="pw-form" onSubmit={handleRequest} noValidate>
        <p className="pw-desc">Podaj adres email powiązany z Twoim kontem. Wyślemy Ci link do ustawienia nowego hasła.</p>
        <div className="pw-field">
          <label className="pw-label" htmlFor="reset-email">Adres email</label>
          <input
            id="reset-email"
            className="pw-input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
          />
        </div>
        {status === 'error' && <div className="pw-error">{message}</div>}
        <div className="pw-hint pw-hint--info">
          Nie masz emaila w profilu? <a href="/login">Zaloguj się</a> i skontaktuj z administratorem.
        </div>
        <div className="pw-actions">
          <button type="submit" className="pw-btn" disabled={!email.trim() || status === 'loading'}>
            {status === 'loading' ? 'Wysyłanie…' : 'Wyślij link resetujący'}
          </button>
          <a href="/login" className="pw-cancel">Wróć do logowania</a>
        </div>
      </form>
    );
  }

  // mode === 'confirm'
  if (status === 'success') return (
    <div className="pw-success">
      <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
      </svg>
      Hasło zostało zmienione. Możesz teraz <a href="/login">zalogować się</a>.
    </div>
  );

  return (
    <form className="pw-form" onSubmit={handleConfirm} noValidate>
      <div className="pw-field">
        <label className="pw-label" htmlFor="confirm-pass1">Nowe hasło</label>
        <input
          id="confirm-pass1"
          className={`pw-input${tooShort ? ' pw-input--error' : ''}`}
          type="password"
          autoComplete="new-password"
          value={pass1}
          onChange={e => setPass1(e.target.value)}
          required
        />
        {tooShort && <span className="pw-hint pw-hint--error">Minimum 8 znaków</span>}
      </div>
      <div className="pw-field">
        <label className="pw-label" htmlFor="confirm-pass2">Powtórz nowe hasło</label>
        <input
          id="confirm-pass2"
          className={`pw-input${mismatch ? ' pw-input--error' : ''}`}
          type="password"
          autoComplete="new-password"
          value={pass2}
          onChange={e => setPass2(e.target.value)}
          required
        />
        {mismatch && <span className="pw-hint pw-hint--error">Hasła nie są identyczne</span>}
      </div>
      {status === 'error' && <div className="pw-error">{message}</div>}
      <div className="pw-actions">
        <button
          type="submit"
          className="pw-btn"
          disabled={pass1.length < 8 || pass1 !== pass2 || status === 'loading'}
        >
          {status === 'loading' ? 'Zapisywanie…' : 'Ustaw nowe hasło'}
        </button>
      </div>
    </form>
  );
}
