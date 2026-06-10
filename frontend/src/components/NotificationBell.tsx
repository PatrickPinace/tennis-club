import { useState, useEffect, useRef, useCallback } from 'react';

interface Notification {
  id: number;
  message: string;
  created_at: string;
  is_read: boolean;
  target_url: string | null;
}

interface NotifResponse {
  notifications: Notification[];
  last_seen_at: string | null;
}

interface Props {
  initialUnread: number;
  notificationsUrl: string;
}

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now.getTime() - d.getTime()) / 1000;
    if (diff < 60) return 'przed chwilą';
    if (diff < 3600) return `${Math.floor(diff / 60)} min temu`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} godz. temu`;
    return d.toLocaleDateString('pl-PL', { day: '2-digit', month: 'short' });
  } catch { return iso; }
}

function escHtml(s: string): string {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function isNew(createdAt: string, lastSeenAt: string | null): boolean {
  if (!lastSeenAt) return true;
  return new Date(createdAt) > new Date(lastSeenAt);
}

export default function NotificationBell({ initialUnread, notificationsUrl }: Props) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(initialUnread);
  const [lastSeenAt, setLastSeenAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seenPostedRef = useRef(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/notifications/', { credentials: 'include' });
      if (!res.ok) throw new Error();
      const data: NotifResponse = await res.json();
      setNotifications(data.notifications.slice(0, 10));
      setUnreadCount(data.notifications.filter(n => !n.is_read).length);
      setLastSeenAt(data.last_seen_at);
    } catch {
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const postSeen = useCallback((): Promise<void> => {
    return fetch('/api/notifications/seen/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
    })
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data?.last_seen_at) setLastSeenAt(data.last_seen_at); })
      .catch(() => {});
  }, []);

  // Pobierz unread count przy mount (bez otwierania panelu)
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/notifications/', { credentials: 'include', redirect: 'manual' });
        if (res.type === 'opaqueredirect' || !res.ok) return;
        const data: NotifResponse = await res.json();
        setUnreadCount(data.notifications.filter(n => !n.is_read).length);
        setLastSeenAt(data.last_seen_at);
      } catch {}
    })();
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      if (!seenPostedRef.current) {
        // Pierwsze otwarcie: POST /seen/ najpierw, potem load — żeby GET widział już nowy timestamp
        seenPostedRef.current = true;
        postSeen().then(() => loadNotifications());
      } else if (notifications === null) {
        loadNotifications();
      }
    }
  };

  const markRead = async (id: number) => {
    try {
      await fetch(`/api/notifications/${id}/read/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
      });
    } catch {}
  };

  const handleItemClick = (n: Notification) => {
    if (!n.is_read) {
      setNotifications(prev => prev?.map(x => x.id === n.id ? { ...x, is_read: true } : x) ?? null);
      setUnreadCount(c => Math.max(0, c - 1));
      markRead(n.id);
    }
    if (n.target_url) {
      setOpen(false);
      window.location.href = n.target_url;
    }
  };

  const readAll = async () => {
    try {
      await fetch('/api/notifications/read-all/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
      });
      setUnreadCount(0);
      loadNotifications();
    } catch {}
  };

  return (
    <div className="topbar__notif-wrap" ref={wrapRef}>
      <button
        className="topbar__icon-btn"
        onClick={handleToggle}
        aria-label="Powiadomienia"
        title="Powiadomienia"
      >
        <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z"/>
        </svg>
        {unreadCount > 0 && (
          <span className="topbar__notif-dot" aria-label={`${unreadCount} nieprzeczytanych powiadomień`}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="topbar__notif-panel" role="dialog" aria-label="Powiadomienia">
          <div className="topbar__notif-arrow" aria-hidden="true" />
          <div className="topbar__notif-header">
            <span className="topbar__notif-title">
              <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style={{ flexShrink: 0 }}>
                <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z"/>
              </svg>
              Powiadomienia
            </span>
            <button onClick={readAll} className="topbar__notif-mark">Oznacz wszystkie</button>
          </div>
          <div className="topbar__notif-list">
            {loading && (
              <div className="topbar__notif-empty" style={{ padding: 16, fontSize: '0.8rem' }}>Ładowanie…</div>
            )}
            {!loading && notifications && notifications.length === 0 && (
              <div className="topbar__notif-empty">Brak powiadomień.</div>
            )}
            {!loading && notifications && notifications.length > 0 && notifications.map(n => (
              <div
                key={n.id}
                className={`topbar__notif-item${n.is_read ? '' : ' topbar__notif-item--unread'}${n.target_url ? ' topbar__notif-item--link' : ''}`}
                onClick={() => handleItemClick(n)}
                style={{ cursor: (n.target_url || !n.is_read) ? 'pointer' : 'default' }}
                role={n.target_url ? 'link' : undefined}
                tabIndex={n.target_url ? 0 : undefined}
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') handleItemClick(n); }}
              >
                <div className="topbar__notif-dot" />
                <div className="topbar__notif-body">
                  <p className="topbar__notif-msg" dangerouslySetInnerHTML={{
                    __html: (isNew(n.created_at, lastSeenAt)
                      ? '<span class="topbar__notif-new">NEW</span>'
                      : '') + escHtml(n.message)
                  }} />
                  <time className="topbar__notif-time">{fmtTime(n.created_at)}</time>
                </div>
              </div>
            ))}
          </div>
          <div className="topbar__notif-footer">
            <a href={notificationsUrl}>Zobacz wszystkie powiadomienia →</a>
          </div>
        </div>
      )}
    </div>
  );
}
