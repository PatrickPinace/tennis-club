import { useState } from 'react';

interface Props {
  nextUrl: string;
  registerUrl: string;
  classicLoginUrl: string;
  guestUrl: string;
}

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

export default function LoginForm({ nextUrl, registerUrl, classicLoginUrl, guestUrl }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const user = username.trim();
    if (!user || !password) {
      setError('Wypełnij login i hasło.');
      return;
    }

    setLoading(true);

    try {
      await fetch('/api/auth/csrf/', { method: 'GET', credentials: 'include' });

      const res = await fetch('/api/auth/login/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify({ username: user, password }),
      });

      const data = await res.json();

      if (data.success) {
        window.location.href = nextUrl;
      } else {
        setError(data.error ?? 'Błąd logowania. Sprawdź dane i spróbuj ponownie.');
      }
    } catch {
      setError('Nie można połączyć się z serwerem. Sprawdź połączenie.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {error && (
        <div className="auth-error" role="alert">{error}</div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <div className="auth-field">
          <label className="auth-label" htmlFor="username">Login lub e-mail</label>
          <input
            className="tc-input"
            type="text"
            id="username"
            autoComplete="username"
            placeholder="np. jan.kowalski"
            value={username}
            onChange={e => setUsername(e.target.value)}
          />
        </div>

        <div className="auth-field">
          <label className="auth-label" htmlFor="password">Hasło</label>
          <input
            className="tc-input"
            type="password"
            id="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={e => setPassword(e.target.value)}
          />
        </div>

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? 'Logowanie…' : 'Zaloguj'}
        </button>
      </form>

      <hr className="auth-divider" />

      <p className="auth-footer-link" style={{ marginTop: '20px' }}>
        Nie masz konta? <a href={registerUrl}>Zarejestruj się →</a>
      </p>
      <p className="auth-footer-link" style={{ marginTop: '10px' }}>
        <a href="/reset-password" style={{ color: 'var(--tc-muted)', fontSize: '0.82rem' }}>Zapomniałem hasła →</a>
      </p>
    </>
  );
}
