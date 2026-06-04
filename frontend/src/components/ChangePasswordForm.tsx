import { useState } from 'react';

interface Props {
  changeUrl: string;
}

type Status = 'idle' | 'loading' | 'success' | 'error';

function getCsrf(): string {
  return document.cookie.split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))?.split('=')[1] ?? '';
}

export default function ChangePasswordForm({ changeUrl }: Props) {
  const [oldPassword,  setOldPassword]  = useState('');
  const [newPassword,  setNewPassword]  = useState('');
  const [newPassword2, setNewPassword2] = useState('');
  const [status,  setStatus]  = useState<Status>('idle');
  const [message, setMessage] = useState('');

  const valid = oldPassword.length > 0 && newPassword.length >= 8 && newPassword === newPassword2;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setStatus('loading');
    setMessage('');
    try {
      const res = await fetch('/api/auth/password/change/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword, new_password2: newPassword2 }),
      });
      const data = await res.json();
      if (data.success) {
        setStatus('success');
        setOldPassword('');
        setNewPassword('');
        setNewPassword2('');
      } else {
        setStatus('error');
        setMessage(data.error ?? 'Wystąpił błąd.');
      }
    } catch {
      setStatus('error');
      setMessage('Błąd sieci. Spróbuj ponownie.');
    }
  }

  const mismatch = newPassword2.length > 0 && newPassword !== newPassword2;
  const tooShort  = newPassword.length > 0 && newPassword.length < 8;

  return (
    <div className="pw-wrap">
      {status === 'success' ? (
        <div className="pw-success">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
          </svg>
          Hasło zostało zmienione. Możesz teraz <a href={changeUrl.replace('/profile/change-password', '/dashboard')}>wrócić do dashboardu</a>.
        </div>
      ) : (
        <form className="pw-form" onSubmit={handleSubmit} noValidate>
          <div className="pw-field">
            <label className="pw-label" htmlFor="old-password">Aktualne hasło</label>
            <input
              id="old-password"
              className="pw-input"
              type="password"
              autoComplete="current-password"
              value={oldPassword}
              onChange={e => setOldPassword(e.target.value)}
              required
            />
          </div>

          <div className="pw-field">
            <label className="pw-label" htmlFor="new-password">Nowe hasło</label>
            <input
              id="new-password"
              className={`pw-input${tooShort ? ' pw-input--error' : ''}`}
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
            />
            {tooShort && <span className="pw-hint pw-hint--error">Minimum 8 znaków</span>}
          </div>

          <div className="pw-field">
            <label className="pw-label" htmlFor="new-password2">Powtórz nowe hasło</label>
            <input
              id="new-password2"
              className={`pw-input${mismatch ? ' pw-input--error' : ''}`}
              type="password"
              autoComplete="new-password"
              value={newPassword2}
              onChange={e => setNewPassword2(e.target.value)}
              required
            />
            {mismatch && <span className="pw-hint pw-hint--error">Hasła nie są identyczne</span>}
          </div>

          {status === 'error' && (
            <div className="pw-error">{message}</div>
          )}

          <div className="pw-actions">
            <button
              type="submit"
              className="pw-btn"
              disabled={!valid || status === 'loading'}
            >
              {status === 'loading' ? 'Zapisywanie…' : 'Zmień hasło'}
            </button>
            <a href={changeUrl.replace('/profile/change-password', '/profile')} className="pw-cancel">Anuluj</a>
          </div>
        </form>
      )}
    </div>
  );
}
