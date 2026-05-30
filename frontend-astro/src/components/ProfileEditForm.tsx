import { useState } from 'react';

interface Props {
  initialData: {
    firstName: string;
    lastName: string;
    email: string;
    city: string;
    birthDate: string;
    username: string;
  };
  profileUrl: string;
}

const FIELDS = ['first_name', 'last_name', 'email', 'city', 'birth_date'] as const;

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

const BackIcon = () => (
  <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
    <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd"/>
  </svg>
);

export default function ProfileEditForm({ initialData, profileUrl }: Props) {
  const [firstName, setFirstName] = useState(initialData.firstName);
  const [lastName, setLastName] = useState(initialData.lastName);
  const [email, setEmail] = useState(initialData.email);
  const [city, setCity] = useState(initialData.city);
  const [birthDate, setBirthDate] = useState(initialData.birthDate);

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
    setLoading(true);

    const payload = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: email.trim(),
      city: city.trim(),
      birth_date: birthDate,
    };

    try {
      await fetch('/api/auth/csrf/', { method: 'GET', credentials: 'include' });

      const res = await fetch('/api/auth/profile/update/', {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (data.success) {
        window.location.href = profileUrl + '?saved=1';
      } else if (data.errors) {
        const errs: Record<string, string> = {};
        for (const [field, msgs] of Object.entries(data.errors as Record<string, string[]>)) {
          if (field === '__all__') {
            setGeneralError(msgs[0] ?? 'Błąd zapisu.');
          } else {
            errs[field] = msgs[0] ?? '';
          }
        }
        setFieldErrors(errs);
      } else {
        setGeneralError(data.error ?? 'Błąd zapisu. Spróbuj ponownie.');
      }
    } catch {
      setGeneralError('Nie można połączyć się z serwerem. Sprawdź połączenie.');
    } finally {
      setLoading(false);
    }
  };

  const fieldClass = (name: string) =>
    `tc-input${fieldErrors[name] ? ' input-error' : ''}`;

  return (
    <div className="edit-wrap">
      <div className="edit-header">
        <a href={profileUrl} className="edit-back">
          <BackIcon />
          Wróć do profilu
        </a>
      </div>

      <div className="edit-card tc-card">
        <h1 className="edit-title">Dane osobowe</h1>
        <p className="edit-subtitle">Zaktualizuj swoje podstawowe informacje</p>

        {generalError && (
          <div className="edit-alert edit-alert--err" role="alert">{generalError}</div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="edit-row">
            <div className="edit-field">
              <label className="edit-label" htmlFor="first_name">Imię</label>
              <input
                className={fieldClass('first_name')}
                type="text" id="first_name"
                autoComplete="given-name"
                value={firstName}
                onChange={e => setFirstName(e.target.value)}
              />
              {fieldErrors.first_name && (
                <span className="field-error" style={{ display: 'block' }}>{fieldErrors.first_name}</span>
              )}
            </div>
            <div className="edit-field">
              <label className="edit-label" htmlFor="last_name">Nazwisko</label>
              <input
                className={fieldClass('last_name')}
                type="text" id="last_name"
                autoComplete="family-name"
                value={lastName}
                onChange={e => setLastName(e.target.value)}
              />
              {fieldErrors.last_name && (
                <span className="field-error" style={{ display: 'block' }}>{fieldErrors.last_name}</span>
              )}
            </div>
          </div>

          <div className="edit-field">
            <label className="edit-label" htmlFor="email">
              E-mail <span className="label-optional">(opcjonalnie)</span>
            </label>
            <input
              className={fieldClass('email')}
              type="email" id="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
            {fieldErrors.email && (
              <span className="field-error" style={{ display: 'block' }}>{fieldErrors.email}</span>
            )}
          </div>

          <div className="edit-field">
            <label className="edit-label" htmlFor="city">
              Miasto <span className="label-optional">(opcjonalnie)</span>
            </label>
            <input
              className={fieldClass('city')}
              type="text" id="city"
              autoComplete="address-level2"
              placeholder="np. Warszawa"
              value={city}
              onChange={e => setCity(e.target.value)}
            />
            {fieldErrors.city && (
              <span className="field-error" style={{ display: 'block' }}>{fieldErrors.city}</span>
            )}
          </div>

          <div className="edit-field">
            <label className="edit-label" htmlFor="birth_date">
              Data urodzenia <span className="label-optional">(opcjonalnie)</span>
            </label>
            <input
              className={fieldClass('birth_date')}
              type="date" id="birth_date"
              value={birthDate}
              onChange={e => setBirthDate(e.target.value)}
            />
            {fieldErrors.birth_date && (
              <span className="field-error" style={{ display: 'block' }}>{fieldErrors.birth_date}</span>
            )}
          </div>

          <div className="edit-field edit-field--readonly">
            <label className="edit-label">Login</label>
            <span className="edit-readonly">{initialData.username}</span>
          </div>

          <div className="edit-actions">
            <button type="submit" className="tc-btn tc-btn-primary" disabled={loading}>
              {loading ? 'Zapisywanie…' : 'Zapisz zmiany'}
            </button>
            <a href={profileUrl} className="tc-btn tc-btn-ghost">
              Anuluj
            </a>
          </div>
        </form>
      </div>
    </div>
  );
}
