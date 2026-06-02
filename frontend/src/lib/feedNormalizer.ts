/**
 * feedNormalizer.ts — normalizacja różnych źródeł danych do wspólnego ActivityItem.
 *
 * Używane przez:
 *   - dashboard.astro (feed teaserowy, limit 6)
 *   - activity.astro  (pełna strona aktywności)
 *
 * Nie importuje nic z Astro ani React — czyste funkcje, zero side-effects.
 */

import type { ActivityItem } from '@/components/ActivityFeed';
import type { MatchHistoryEntry, Notification, ReservationEntry } from '@/lib/api';

// ── Helpers ───────────────────────────────────────────────────────────────────

export function relativeTime(iso: string): string {
  try {
    if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
      const todayStr = new Date().toISOString().slice(0, 10);
      if (iso === todayStr) return 'dziś';
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      if (iso === yesterday.toISOString().slice(0, 10)) return 'wczoraj';
      const d = new Date(iso + 'T12:00:00');
      const diffDays = Math.floor((Date.now() - d.getTime()) / 86_400_000);
      if (diffDays < 7) return `${diffDays} dni temu`;
      return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
    }
    const d = new Date(iso);
    const diffMs = Date.now() - d.getTime();
    if (diffMs < 3_600_000) {
      const mins = Math.max(1, Math.floor(diffMs / 60_000));
      return `${mins} min temu`;
    }
    const diffDays = Math.floor(diffMs / 86_400_000);
    if (diffDays === 0) return d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
    if (diffDays === 1) return 'wczoraj';
    if (diffDays < 7)  return `${diffDays} dni temu`;
    return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
  } catch { return iso; }
}

export function isoTimestamp(iso: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso + 'T12:00:00';
  return iso;
}

function matchScore(m: MatchHistoryEntry): string {
  const parts: string[] = [];
  if (m.p1_set1 !== null && m.p2_set1 !== null) parts.push(`${m.p1_set1}:${m.p2_set1}`);
  if (m.p1_set2 !== null && m.p2_set2 !== null) parts.push(`${m.p1_set2}:${m.p2_set2}`);
  if (m.p1_set3 !== null && m.p2_set3 !== null) parts.push(`${m.p1_set3}:${m.p2_set3}`);
  return parts.join(', ') || '—';
}

function matchOpponent(m: MatchHistoryEntry): string {
  const isP1Side =
    (m.user === 'user-win'  && m.win === 'p1') ||
    (m.user === 'user-loss' && m.win === 'p2');
  const opp = isP1Side ? m.p2 : m.p1;
  if (!opp) return 'Nieznany';
  return [opp.first_name, opp.last_name].filter(Boolean).join(' ') || opp.username;
}

// Typy notyfikacji sensowne w activity feedzie (nie court.*, nie generic)
export const FEED_NOTIFICATION_TYPES = new Set([
  'tournament.started',
  'tournament.finished',
  'tournament.cancelled',
  'tournament.participant.added',
  'tournament.participant.joined',
  'tournament.participant.removed',
  'tournament.ladder.challenge_sent',
  'tournament.ladder.challenge_accepted',
  'tournament.ladder.challenge_rejected',
  'tournament.match.score_entered',
]);

// ── Normalizatory ─────────────────────────────────────────────────────────────

export function matchesToFeedItems(
  matches: MatchHistoryEntry[],
  urlBase: string,        // prefix z url() — np. '' lub '/astro'
): ActivityItem[] {
  return matches.map(m => {
    const isWin  = m.user === 'user-win';
    const isDraw = m.user === 'user-draw';
    const result = isWin ? 'win' : isDraw ? 'neutral' : 'loss';
    const label  = isWin ? 'Wygrana' : isDraw ? 'Remis' : 'Porażka';
    const fmt    = m.match_double ? 'Debel' : 'Singiel';
    const score  = matchScore(m);
    const href   = m.is_tournament && m.tournament_id
      ? `${urlBase}/tournaments/${m.tournament_id}`
      : `${urlBase}/matches/${m.id}`;
    return {
      kind:      'match' as const,
      title:     `${label} vs ${matchOpponent(m)}`,
      desc:      fmt,
      score,
      time:      relativeTime(m.match_date),
      timestamp: isoTimestamp(m.match_date),
      result,
      href,
    };
  });
}

export function notificationsToFeedItems(
  notifications: Notification[],
  cutoffMs: number,        // Date.now() - N — filtr czasu; 0 = bez ograniczenia
): ActivityItem[] {
  return notifications
    .filter(n =>
      FEED_NOTIFICATION_TYPES.has(n.event_type ?? '') &&
      (cutoffMs === 0 || new Date(n.created_at).getTime() >= cutoffMs)
    )
    .map(n => ({
      kind:      'notification' as const,
      title:     n.message,
      desc:      '',
      score:     '',
      time:      relativeTime(n.created_at),
      timestamp: n.created_at,
      result:    'neutral' as const,
      href:      n.target_url ?? undefined,
    }));
}

export function reservationsToFeedItems(
  reservations: ReservationEntry[],
  urlBase: string,
  futureOnly = true,       // true = dashboard (tylko przyszłe), false = /activity (też minione)
): ActivityItem[] {
  const nowIso = new Date().toISOString();
  return reservations
    .filter(r =>
      (r.status === 'PENDING' || r.status === 'CONFIRMED') &&
      (!futureOnly || r.start_time > nowIso)
    )
    .map(r => {
      const d = new Date(r.start_time);
      const dateLabel = d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
      const timeLabel = d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
      const statusLabel = r.status === 'CONFIRMED' ? 'potwierdzona' : 'oczekująca';
      const courtLabel = r.court_name ?? r.facility_name ?? 'Kort';
      const isPast = r.start_time <= nowIso;
      return {
        kind:      'reservation' as const,
        title:     `Rezerwacja ${courtLabel}`,
        desc:      `${dateLabel}, ${timeLabel}${isPast ? ' · zakończona' : ` · ${statusLabel}`}`,
        score:     '',
        time:      isPast ? relativeTime(r.start_time) : `${dateLabel} ${timeLabel}`,
        timestamp: r.start_time,
        result:    r.status === 'CONFIRMED' ? 'win' as const : 'neutral' as const,
        href:      `${urlBase}/courts/reservations`,
      };
    });
}

// ── Sortowanie ────────────────────────────────────────────────────────────────

export function sortByTimestampDesc(items: ActivityItem[]): ActivityItem[] {
  return [...items].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
}
