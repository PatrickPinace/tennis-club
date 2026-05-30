import { useState, useEffect, useRef } from 'react';

interface Props {
  profileUrl: string;
  manageUrl: string;
  loginUrl: string;
}

interface UserData {
  username: string;
  first_name: string;
  last_name: string;
}

export default function UserChip({ profileUrl, manageUrl, loginUrl }: Props) {
  const [user, setUser] = useState<UserData | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/auth/me/', {
          credentials: 'include',
          redirect: 'manual',
        });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated && data.user) {
            setUser(data.user);
          }
        }
      } catch {}
      setLoaded(true);
    })();
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  const handleLogout = async () => {
    await fetch('/api/auth/logout/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    window.location.href = loginUrl;
  };

  if (!loaded) return null;

  if (!user) {
    return (
      <div className="topbar__user-wrap">
        <a href={loginUrl} className="topbar__login-link">Zaloguj się</a>
      </div>
    );
  }

  const initials = ((user.first_name?.[0] ?? '') + (user.last_name?.[0] ?? '')).toUpperCase()
    || user.username.slice(0, 2).toUpperCase();

  return (
    <div className="topbar__user-wrap" ref={wrapRef}>
      <div
        className="topbar__user"
        role="button"
        tabIndex={0}
        aria-label="Menu użytkownika"
        onClick={() => setMenuOpen(o => !o)}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setMenuOpen(o => !o); } }}
      >
        <div className="topbar__user-avatar" aria-hidden="true">{initials}</div>
        <div className="topbar__user-info">
          <span className="topbar__user-name">{user.first_name || user.username}</span>
          <span className="topbar__user-surname">{user.last_name || ''}</span>
        </div>
        <svg className="topbar__user-caret" width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd"/>
        </svg>

        {menuOpen && (
          <div className="topbar__user-menu" style={{ display: 'block' }}>
            <a href={manageUrl} className="topbar__user-menu-item topbar__user-menu-link">
              <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd"/>
              </svg>
              Moje turnieje
            </a>
            <a href={profileUrl} className="topbar__user-menu-item topbar__user-menu-link">
              <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd"/>
              </svg>
              Mój profil
            </a>
            <div className="topbar__user-menu-divider" />
            <button className="topbar__user-menu-item" onClick={handleLogout}>
              <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V4a1 1 0 00-1-1H3zm11 4a1 1 0 10-2 0v4a1 1 0 102 0V7zm-3 1a1 1 0 10-2 0v3a1 1 0 102 0V8z" clipRule="evenodd"/>
              </svg>
              Wyloguj
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
