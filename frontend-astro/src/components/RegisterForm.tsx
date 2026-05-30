import { useState } from 'react';

interface Props {
  dashboardUrl: string;
  loginUrl: string;
}

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

export default function RegisterForm({ dashboardUrl, loginUrl }: Props) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [login, setLogin] = useState('');
  const [email, setEmail] = useState('');
  const [password1, setPassword1] = useState('');
  const [password2, setPassword2] = useState('');
  const [consent, setConsent] = useState(false);

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState('');
  const [loading, setLoading] = useState(false);

  const clearErrors = () => {
    setFieldErrors({});
    setGeneralError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();

    if (!login.trim() || !firstName.trim() || !lastName.trim() || !password1 || !password2) {
      setGeneralError('Wypełnij wszystkie wymagane pola.');
      return;
    }
    if (!consent) {
      setFieldErrors({ data_processing_consent: 'Zgoda na przetwarzanie danych jest wymagana.' });
      return;
    }

    setLoading(true);

    const payload = {
      login: login.trim(),
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: email.trim(),
      password_1: password1,
      password_2: password2,
      data_processing_consent: consent,
    };

    try {
      await fetch('/api/auth/csrf/', { method: 'GET', credentials: 'include' });

      const res = await fetch('/api/auth/register/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (data.success) {
        window.location.href = dashboardUrl;
      } else if (data.errors) {
        const errs: Record<string, string> = {};
        for (const [field, msgs] of Object.entries(data.errors as Record<string, string[]>)) {
          if (field === '__all__') {
            setGeneralError(msgs[0] ?? 'Błąd rejestracji.');
          } else {
            errs[field] = msgs[0] ?? '';
          }
        }
        setFieldErrors(errs);
      } else {
        setGeneralError('Błąd rejestracji. Spróbuj ponownie.');
      }
    } catch {
      setGeneralError('Nie można połączyć się z serwerem. Sprawdź połączenie.');
    } finally {
      setLoading(false);
    }
  };

  const fieldClass = (name: string) =>
    `tc-input${fieldErrors[name] ? ' input-error' : ''}`;

  const fieldError = (name: string) =>
    fieldErrors[name]
      ? <span className="auth-field-error" style={{ display: 'block' }}>{fieldErrors[name]}</span>
      : null;

  return (
    <>
      {generalError && (
        <div className="auth-error" role="alert">{generalError}</div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <div className="reg-row">
          <div className="auth-field">
            <label className="auth-label" htmlFor="first_name">Imię</label>
            <input className={fieldClass('first_name')} type="text" id="first_name"
              autoComplete="given-name" placeholder="Jan"
              value={firstName} onChange={e => setFirstName(e.target.value)} />
            {fieldError('first_name')}
          </div>
          <div className="auth-field">
            <label className="auth-label" htmlFor="last_name">Nazwisko</label>
            <input className={fieldClass('last_name')} type="text" id="last_name"
              autoComplete="family-name" placeholder="Kowalski"
              value={lastName} onChange={e => setLastName(e.target.value)} />
            {fieldError('last_name')}
          </div>
        </div>

        <div className="auth-field">
          <label className="auth-label" htmlFor="login">Login</label>
          <input className={fieldClass('login')} type="text" id="login"
            autoComplete="username" placeholder="np. jan.kowalski"
            value={login} onChange={e => setLogin(e.target.value)} />
          {fieldError('login')}
        </div>

        <div className="auth-field">
          <label className="auth-label" htmlFor="email">
            E-mail <span className="auth-label-optional">(opcjonalnie)</span>
          </label>
          <input className={fieldClass('email')} type="email" id="email"
            autoComplete="email" placeholder="jan@example.com"
            value={email} onChange={e => setEmail(e.target.value)} />
          {fieldError('email')}
        </div>

        <div className="auth-field">
          <label className="auth-label" htmlFor="password_1">Hasło</label>
          <input className={fieldClass('password_1')} type="password" id="password_1"
            autoComplete="new-password" placeholder="min. 8 znaków"
            value={password1} onChange={e => setPassword1(e.target.value)} />
          {fieldError('password_1')}
        </div>

        <div className="auth-field">
          <label className="auth-label" htmlFor="password_2">Powtórz hasło</label>
          <input className={fieldClass('password_2')} type="password" id="password_2"
            autoComplete="new-password" placeholder="••••••••"
            value={password2} onChange={e => setPassword2(e.target.value)} />
          {fieldError('password_2')}
        </div>

        <div className="auth-field" style={{ marginBottom: '20px' }}>
          <label className="auth-consent">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
            <span>Wyrażam zgodę na przetwarzanie moich danych osobowych w ramach funkcjonalności portalu.</span>
          </label>
          {fieldError('data_processing_consent')}
        </div>

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? 'Rejestrowanie…' : 'Zarejestruj się'}
        </button>
      </form>

      <hr className="auth-divider" />

      <p className="auth-footer-link" style={{ marginTop: '20px' }}>
        Masz już konto? <a href={loginUrl}>Zaloguj się →</a>
      </p>
    </>
  );
}
