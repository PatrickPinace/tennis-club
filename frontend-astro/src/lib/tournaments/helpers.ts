// Shared helpers for tournament client-side modules.
// Re-exports getCsrf/escHtml from the shared client-utils (single source of truth).
export { getCsrf, escHtml } from '@/lib/client-utils';

/** Abbreviate name to initials: "Jan Kowalski" → "JK", "Kowalski" → "KOW". Skips '/' (doubles separator). */
export function abbrev(name: string): string {
  const parts = name.trim().split(/\s+/).filter(w => w && w !== '/');
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase();
  return name.slice(0, 3).toUpperCase();
}

/** Initials for avatar: "Jan Kowalski" → "JK". Skips '/' separator. */
export function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(w => w && w !== '/')
    .slice(0, 2)
    .map(w => w[0].toUpperCase())
    .join('');
}

/** Read API base URL from <meta name="api-base">. */
export function getApiBase(): string {
  return (document.querySelector('meta[name="api-base"]') as HTMLMetaElement)?.content ?? '';
}

/** Format a number|null to input value string. */
export function valStr(n: number | null): string {
  return n != null ? String(n) : '';
}

/** Status sets used for filtering. */
export const PENDING_STATUSES = new Set(['WAI', 'SCH', 'INP']);
export const DONE_STATUSES = new Set(['CMP', 'WDR']);
