import { useState, useEffect, useRef, useCallback } from 'react';

interface Notification {
  id: number;
  message: string;
  created_at: string;
  is_read: boolean;
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

export default function NotificationBell({ initialUnread, notificationsUrl }: Props) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(initialUnread);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/notifications/', { credentials: 'include' });
      if (!res.ok) throw new Error();
      const data: Notification[] = await res.json();
      setNotifications(data.slice(0, 10));
      setUnreadCount(data.filter(n => !n.is_read).length);
    } catch {
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/notifications/', { credentials: 'include', redirect: 'manual' });
        if (res.type === 'opaqueredirect' || !res.ok) return;
        const data: Notification[] = await res.json();
        setUnreadCount(data.filter(n => !n.is_read).length);
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
    if (next && notifications === null) {
      loadNotifications();
    }
  };

  const markRead = async (id: number) => {
    try {
      const res = await fetch(`/api/notifications/${id}/read/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        setNotifications(prev => prev?.map(n => n.id === id ? { ...n, is_read: true } : n) ?? null);
        setUnreadCount(c => Math.max(0, c - 1));
      }
    } catch {}
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
            {!loading && notifications && notifications.length > 0 && (
              <>
                {notifications.map(n => (
                  <div
                    key={n.id}
                    className={`topbar__notif-item${n.is_read ? '' : ' topbar__notif-item--unread'}`}
                    onClick={() => !n.is_read && markRead(n.id)}
                    style={{ cursor: n.is_read ? 'default' : 'pointer' }}
                  >
                    <div className="topbar__notif-dot" />
                    <div className="topbar__notif-body">
                      <p className="topbar__notif-msg" dangerouslySetInnerHTML={{ __html: escHtml(n.message) }} />
                      <time className="topbar__notif-time">{fmtTime(n.created_at)}</time>
                    </div>
                  </div>
                ))}
                <div className="topbar__notif-footer">
                  <a href={notificationsUrl}>Zobacz wszystkie powiadomienia →</a>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
