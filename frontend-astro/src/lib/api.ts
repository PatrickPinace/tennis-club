/**
 * api.ts — minimalna warstwa do komunikacji z Django REST API
 *
 * Zasady:
 * - Wszystkie fetche są server-side (Astro SSR frontmatter)
 * - Adresy bazowe z env: DJANGO_API_URL (server) / PUBLIC_API_BASE_URL (client)
 * - Przy błędzie auth (401/302) zwracamy null + logujemy — graceful degradation
 * - Brak nadmiarowej architektury — proste funkcje, nie klasy/cache
 */

// ── Typy danych z Django API ──────────────────────────────────────────────────

export interface Tournament {
  id: number;
  name: string;
  description: string;
  start_date: string | null;   // ISO datetime string
  end_date: string | null;
  status: 'DRF' | 'REG' | 'ACT' | 'FIN' | 'CNC';
  tournament_type: string;
  match_format: string;
  participants: Participant[];
}

export interface Participant {
  id: number;
  display_name: string;
  seed_number: number | null;
  status: string;
}

export interface Notification {
  id: number;
  message: string;
  created_at: string;
  is_read: boolean;
}

export interface NotificationsResponse {
  notifications: Notification[];
  count: number;
}

export interface UnreadCountResponse {
  count: number;
}

export interface RankingData {
  position: number | null;
  points: number | null;
  matches_played: number | null;
  matches_won: number | null;
  matches_lost: number | null;
  win_rate: number | null;
}

export interface LastMatchData {
  date: string;        // ISO date
  opponent: string;
  score: string;       // np. "6:3 7:5"
  won: boolean;
  double: boolean;
}

export interface NextReservationData {
  date: string;        // np. "08 kwi, 16:00"
  end_time: string;    // np. "17:30"
  court: string | null;
  status: string;
}

export interface DashboardSummary {
  ranking: RankingData | null;
  last_match: LastMatchData | null;
  next_reservation: NextReservationData | null;
  upcoming_tournaments_count: number | null;
}

// ── Mapowanie statusów na etykiety PL ────────────────────────────────────────

export const TOURNAMENT_STATUS_LABEL: Record<string, string> = {
  DRF: 'Szkic',
  REG: 'Rejestracja',
  ACT: 'Trwa',
  FIN: 'Zakończony',
  CNC: 'Odwołany',
};

export const TOURNAMENT_TYPE_LABEL: Record<string, string> = {
  RR:  'Round Robin',
  SE:  'Eliminacja pojedyncza',
  DE:  'Eliminacja podwójna',
  LAD: 'Drabinka',
  AME: 'Americano',
  SWS: 'System szwajcarski',
};

// ── Konfiguracja ──────────────────────────────────────────────────────────────

/**
 * Bazowy URL do Django — po stronie serwera (Astro SSR).
 * Nie używaj w client-side code (brak dostępu do zmiennych bez prefixu PUBLIC_).
 */
function getApiBase(): string {
  // import.meta.env działa w Astro — DJANGO_API_URL to zmienna server-only
  return import.meta.env.DJANGO_API_URL ?? 'http://localhost:8000';
}

// ── Fetch helper ──────────────────────────────────────────────────────────────

interface FetchOptions {
  /** Cookie sesji Django — przekaż z Astro.request.headers gdy potrzebujesz auth */
  sessionCookie?: string;
  /** Timeout w ms (domyślnie 5000) */
  timeoutMs?: number;
}

async function apiFetch<T>(
  path: string,
  options: FetchOptions = {}
): Promise<T | null> {
  const { sessionCookie, timeoutMs = 5000 } = options;
  const url = `${getApiBase()}${path}`;

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  // Przekaż cookie sesji Django dla endpointów chronionych @login_required
  if (sessionCookie) {
    headers['Cookie'] = sessionCookie;
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const res = await fetch(url, {
      headers,
      redirect: 'manual', // NIE podążaj za redirect 302 → login
      signal: controller.signal,
    });

    clearTimeout(timer);

    // 302 = niezalogowany (login_required) — graceful fallback
    if (res.status === 302 || res.status === 301) {
      console.warn(`[api] ${path} → auth required (${res.status})`);
      return null;
    }

    // Inne błędy
    if (!res.ok) {
      console.error(`[api] ${path} → HTTP ${res.status}`);
      return null;
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      console.error(`[api] ${path} → timeout after ${timeoutMs}ms`);
    } else {
      console.error(`[api] ${path} → fetch error:`, err);
    }
    return null;
  }
}

// ── Publiczne funkcje API ─────────────────────────────────────────────────────

/**
 * Zwraca listę turniejów.
 * Endpoint: GET /api/tournaments/
 * Auth: IsAuthenticatedOrReadOnly — działa bez logowania (lista publiczna).
 */
export async function getTournaments(): Promise<Tournament[]> {
  const data = await apiFetch<Tournament[]>('/api/tournaments/');
  return data ?? [];
}

/**
 * Zwraca turnieje przefiltrowane do dashboardu:
 * aktywne (REG/ACT) i nadchodzące, max `limit` sztuk.
 */
export async function getDashboardTournaments(limit = 5): Promise<Tournament[]> {
  const all = await getTournaments();
  const active = all.filter(t => t.status === 'REG' || t.status === 'ACT');
  return active.slice(0, limit);
}

/**
 * Zwraca liczbę nieprzeczytanych powiadomień.
 * Endpoint: GET /notifications/api/unread-count/
 * Auth: @login_required — wymaga cookie sesji Django.
 * Zwraca null gdy użytkownik niezalogowany (graceful degradation).
 */
export async function getUnreadCount(
  sessionCookie?: string
): Promise<number | null> {
  const data = await apiFetch<UnreadCountResponse>(
    '/notifications/api/unread-count/',
    { sessionCookie }
  );
  return data?.count ?? null;
}

/**
 * Zwraca listę powiadomień użytkownika.
 * Endpoint: GET /notifications/api/notifications/
 * Auth: @login_required — wymaga cookie sesji Django.
 */
export async function getNotifications(
  sessionCookie?: string
): Promise<Notification[]> {
  const data = await apiFetch<NotificationsResponse>(
    '/notifications/api/notifications/',
    { sessionCookie }
  );
  return data?.notifications ?? [];
}

/**
 * Zwraca podsumowanie dla dashboardu: ranking, ostatni mecz, rezerwacja, turnieje.
 * Endpoint: GET /api/dashboard/summary/
 * Auth: IsAuthenticated — wymaga cookie sesji Django lub JWT.
 * Zwraca null gdy użytkownik niezalogowany (graceful degradation).
 */
export async function getDashboardSummary(
  sessionCookie?: string
): Promise<DashboardSummary | null> {
  return apiFetch<DashboardSummary>('/api/dashboard/summary/', { sessionCookie });
}
