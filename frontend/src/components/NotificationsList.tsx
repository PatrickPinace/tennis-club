import { useState, useCallback } from 'react';

interface NotificationItem {
  id: number;
  message: string;
  created_at: string;
  is_read: boolean;
  target_url: string | null;
}

interface Props {
  notifications: NotificationItem[];
  initialUnread: number;
  lastSeenAt: string | null;
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMin = Math.floor((now.getTime() - d.getTime()) / 60000);
    if (diffMin < 1) return 'przed chwilą';
    if (diffMin < 60) return `${diffMin} min temu`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH} godz. temu`;
    const diffD = Math.floor(diffH / 24);
    if (diffD < 7) return `${diffD} dni temu`;
    return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
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

function getApiBase(): string {
  return (window as any)._API ?? '';
}

function updateTopbarBadge(count: number) {
  const badge = document.getElementById('notif-count');
  if (!badge) return;
  if (count > 0) {
    badge.textContent = String(count > 99 ? '99+' : count);
    badge.style.display = '';
  } else {
    badge.style.display = 'none';
  }
}

const BellIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true" style={{ color: 'var(--tc-muted)', marginBottom: 12 }}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
  </svg>
);

function isNew(createdAt: string, lastSeenAt: string | null): boolean {
  if (!lastSeenAt) return true;
  return new Date(createdAt) > new Date(lastSeenAt);
}

export default function NotificationsList({ notifications: initial, initialUnread, lastSeenAt }: Props) {
  const [items, setItems] = useState(initial);
  const unreadCount = items.filter(n => !n.is_read).length;

  const markRead = useCallback(async (id: number) => {
    const api = getApiBase();
    const csrf = await getCsrf(api);
    try {
      await fetch(`${api}/api/notifications/${id}/read/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
      });
    } catch (e) {
      console.error('[notif] markRead error', e);
    }
  }, []);

  const handleItemClick = useCallback(async (n: NotificationItem) => {
    if (!n.is_read) {
      // Optimistic update
      setItems(prev => {
        const next = prev.map(x => x.id === n.id ? { ...x, is_read: true } : x);
        updateTopbarBadge(next.filter(x => !x.is_read).length);
        return next;
      });
      markRead(n.id);
    }
    if (n.target_url) {
      window.location.href = n.target_url;
    }
  }, [markRead]);

  const readAll = useCallback(async () => {
    const api = getApiBase();
    const csrf = await getCsrf(api);
    try {
      const r = await fetch(`${api}/api/notifications/read-all/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/json' },
      });
      if (!r.ok) return;
      setItems(prev => prev.map(n => ({ ...n, is_read: true })));
      updateTopbarBadge(0);
    } catch (e) {
      console.error('[notif] readAll error', e);
    }
  }, []);

  // Update subtitle text reactively
  const subtitleText = unreadCount > 0
    ? `Masz ${unreadCount} nieprzeczytanych powiadomień`
    : 'Wszystkie powiadomienia przeczytane';

  if (items.length === 0) {
    return (
      <>
        <SubtitleUpdater text={subtitleText} />
        <div className="notif-empty">
          <BellIcon />
          <p className="notif-empty__title">Brak powiadomień</p>
          <p className="notif-empty__sub">Gdy coś się wydarzy, pojawi się tutaj.</p>
        </div>
      </>
    );
  }

  return (
    <>
      <SubtitleUpdater text={subtitleText} />
      <div className="tc-card notif-card">
        <div className="notif-toolbar">
          <span className="notif-toolbar__count">
            {items.length} powiadomień{unreadCount > 0 ? `, ${unreadCount} nieprzeczytanych` : ''}
          </span>
          {unreadCount > 0 && (
            <button className="notif-read-all-btn" type="button" onClick={readAll}>
              Oznacz wszystkie jako przeczytane
            </button>
          )}
        </div>

        <ul className="notif-list">
          {items.map(n => (
            <li
              key={n.id}
              className={`notif-item${n.is_read ? '' : ' notif-item--unread'}${n.target_url ? ' notif-item--link' : ''}`}
              onClick={() => handleItemClick(n)}
              style={{ cursor: (n.target_url || !n.is_read) ? 'pointer' : 'default' }}
              role={n.target_url ? 'link' : undefined}
              tabIndex={n.target_url ? 0 : undefined}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') handleItemClick(n); }}
            >
              <div className="notif-item__dot" aria-hidden="true" />
              <div className="notif-item__body">
                <p className="notif-item__msg">
                  {isNew(n.created_at, lastSeenAt) && (
                    <span className="notif-item__new-badge">NEW</span>
                  )}
                  {n.message}
                </p>
                <time className="notif-item__time" dateTime={n.created_at}>
                  {fmtTime(n.created_at)}
                </time>
              </div>
              {!n.is_read && !n.target_url && (
                <button
                  className="notif-item__mark-btn"
                  type="button"
                  onClick={e => { e.stopPropagation(); markRead(n.id); setItems(prev => { const next = prev.map(x => x.id === n.id ? { ...x, is_read: true } : x); updateTopbarBadge(next.filter(x => !x.is_read).length); return next; }); }}
                  title="Oznacz jako przeczytane"
                  aria-label="Oznacz jako przeczytane"
                >
                  ✓
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}

function SubtitleUpdater({ text }: { text: string }) {
  if (typeof document !== 'undefined') {
    const el = document.querySelector('.page-header__subtitle');
    if (el) el.textContent = text;
  }
  return null;
}
