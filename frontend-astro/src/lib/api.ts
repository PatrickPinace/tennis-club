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
  status: 'DRF' | 'REG' | 'ACT' | 'SCH' | 'FIN' | 'CNC';
  tournament_type: string;
  match_format: string;
  participants: Participant[];
}

/** Lekka wersja turnieju dla /api/tournaments/list/ — bez pełnej listy uczestników */
export interface TournamentListEntry {
  id: number;
  name: string;
  description: string;
  start_date: string | null;
  end_date: string | null;
  status: 'DRF' | 'REG' | 'ACT' | 'SCH' | 'FIN' | 'CNC';
  tournament_type: 'SGL' | 'DBE' | 'RND' | 'LDR' | 'AMR' | 'SWS';
  match_format: 'SNG' | 'DBL';
  rank: 1 | 2 | 3;
  participant_count: number;
  created_by_name: string;
  facility_name: string | null;
  matches_progress: { done: number; total: number } | null;
}

export interface Participant {
  id: number;
  display_name: string;
  seed_number: number | null;
  status: string;
  user_id: number | null;
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

// ── Historia meczów ───────────────────────────────────────────────────────────

export interface MatchUser {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
}

export interface MatchHistoryEntry {
  id: number;
  p1: MatchUser | null;
  p2: MatchUser | null;
  p3: MatchUser | null;
  p4: MatchUser | null;
  p1_set1: number | null;
  p1_set2: number | null;
  p1_set3: number | null;
  p2_set1: number | null;
  p2_set2: number | null;
  p2_set3: number | null;
  match_double: boolean;
  description: string | null;
  match_date: string;          // "YYYY-MM-DD"
  win: 'p1' | 'p2' | 'draw';
  user: 'user-win' | 'user-loss' | 'user-draw';  // backend: user-lose → user-loss (naprawione w tools.py)
  p1_win_set: number;
  p2_win_set: number;
  p1_win_gem: number;
  p2_win_gem: number;
  can_edit?: boolean;  // tylko w /api/matches/<id>/ — true gdy uczestnik lub is_staff
  score_status?: 'PENDING' | 'CONFIRMED';
  reported_by?: MatchUser | null;
  confirmed_by?: MatchUser | null;
}

export interface RankingData {
  position: number | null;
  points: number | null;
  matches_played: number | null;
  matches_won: number | null;
  matches_lost: number | null;
  sets_won?: number | null;
  sets_lost?: number | null;
  win_rate: number | null;
}

// ── Profil użytkownika (/api/auth/profile/) ───────────────────────────────────

export interface UserProfileData {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  date_joined: string;   // ISO date
  city: string | null;
  birth_date: string | null;  // ISO date
  member_since: string | null; // ISO date (start_date lub date_joined)
}

export interface TournamentStats {
  tournaments_played: number;
  tournaments_finished: number;
  tournaments_active: number;
  matches_played: number;
  matches_won: number;
  win_rate: number | null;
}

export interface UserProfileResponse {
  authenticated: boolean;
  user: UserProfileData;
  ranking_sng: RankingData | null;
  ranking_dbl: RankingData | null;
  tournament_stats: TournamentStats | null;
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

// ── Tournament Detail ───────────────────────────────────────────────────────

export interface TournamentMatch {
  id: number;
  round_number: number;
  match_index: number;
  status: string;
  participant1_id: number | null;
  participant2_id: number | null;
  participant3_id: number | null;
  participant4_id: number | null;
  participant1_name: string | null;
  participant2_name: string | null;
  participant3_name: string | null;
  participant4_name: string | null;
  winner_name: string | null;
  set1_p1_score: number | null;
  set1_p2_score: number | null;
  set2_p1_score: number | null;
  set2_p2_score: number | null;
  set3_p1_score: number | null;
  set3_p2_score: number | null;
  score: string | null;
  scheduled_time: string | null;
}

export interface RRStandingRow {
  participant_id: number;
  display_name: string;
  points: number | string;  // DRF DecimalField zwraca string "2.50"
  matches_played: number;
  wins: number;
  losses: number;
  sets_won: number;
  sets_lost: number;
  games_won: number;
  games_lost: number;
  sets_diff: number;
  games_diff: number;
}

export interface RRConfig {
  max_participants: number;
  sets_to_win: number;
  games_per_set: number;
  points_for_win: number;
  points_for_loss: number;
  points_for_set_win: number;
  points_for_set_loss: number;
  points_for_gem_win: number;
  tie_breaker_priority: string;
}

export interface TournamentDetail {
  id: number;
  name: string;
  description: string;
  start_date: string | null;
  end_date: string | null;
  status: string;
  tournament_type: string;
  match_format: string;
  rank: number;
  facility_name: string | null;
  created_by_name: string;
  created_by_username: string;
  participant_count: number;
  participants: Participant[];
  config: RRConfig | null;
  matches: TournamentMatch[];
  standings: RRStandingRow[] | null;
  matches_progress: { done: number; total: number } | null;
}

// ── Rankingi ─────────────────────────────────────────────────────────────────

export interface PlayerRankingEntry {
  position: number;
  display_name: string;
  points: number | string;  // DRF zwraca DecimalField jako string "2840.00"
  matches_played: number;
  matches_won: number;
  matches_lost: number;
  sets_won: number;
  sets_lost: number;
  win_rate: number;    // 0-100, obliczane przez backend
  match_type: 'SNG' | 'DBL';
  season: number | null;
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
  REG: 'Otwarte zapisy',
  SCH: 'Nadchodzący',
  ACT: 'Trwa',
  FIN: 'Zakończony',
  CNC: 'Odwołany',
};

export const TOURNAMENT_TYPE_LABEL: Record<string, string> = {
  RND: 'Round Robin',
  SGL: 'Eliminacja pojedyncza',
  DBE: 'Eliminacja podwójna',
  LDR: 'Drabinka',
  AMR: 'Americano',
  SWS: 'System szwajcarski',
};

// ── Konfiguracja ──────────────────────────────────────────────────────────────

/**
 * Bazowy URL do Django — po stronie serwera (Astro SSR).
 * Nie używaj w client-side code (brak dostępu do zmiennych bez prefixu PUBLIC_).
 */
function getApiBase(): string {
  // process.env jest dostępne w runtime (Node adapter) — nie jest inlineowane przy buildzie.
  // import.meta.env.DJANGO_API_URL byłoby wkompilowane build-time → nie widzi Docker env.
  return process.env.DJANGO_API_URL ?? 'http://localhost:8000';
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

  // Node fetch nadpisuje Host header na wartość z URL (tennis-web:8000),
  // dlatego 'tennis-web' musi być w Django ALLOWED_HOSTS.
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
 * Zwraca listę turniejów (pełna, z uczestnikami).
 * Endpoint: GET /api/tournaments/
 * Auth: IsAuthenticatedOrReadOnly — działa bez logowania (lista publiczna).
 */
export async function getTournaments(): Promise<Tournament[]> {
  const data = await apiFetch<Tournament[]>('/api/tournaments/');
  return data ?? [];
}

/**
 * Zwraca lekką listę turniejów dla strony /tournaments.
 * Endpoint: GET /api/tournaments/list/
 * Dane: id, name, status, type, format, rank, participant_count, facility_name, dates.
 * Auth: IsAuthenticatedOrReadOnly — publiczny GET.
 */
export async function getTournamentsList(): Promise<TournamentListEntry[]> {
  const data = await apiFetch<TournamentListEntry[]>('/api/tournaments/list/');
  return data ?? [];
}

/**
 * Zwraca pełny detal turnieju z meczami i standings.
 * Endpoint: GET /api/tournaments/{id}/detail/
 * Auth: IsAuthenticatedOrReadOnly — publiczny GET.
 * Zwraca null gdy turniej nie istnieje (404).
 */
export async function getTournamentDetail(
  id: number
): Promise<TournamentDetail | null> {
  return apiFetch<TournamentDetail>(`/api/tournaments/${id}/detail/`);
}

/**
 * Zwraca turnieje utworzone przez zalogowanego użytkownika.
 * Endpoint: GET /api/tournaments/mine/
 * Auth: IsAuthenticated — wymaga cookie sesji Django.
 * Zwraca [] gdy niezalogowany lub backend niedostępny.
 */
export async function getMyTournaments(
  sessionCookie?: string
): Promise<TournamentListEntry[]> {
  const data = await apiFetch<TournamentListEntry[]>('/api/tournaments/mine/', { sessionCookie });
  return data ?? [];
}

/**
 * Zwraca turnieje przefiltrowane do dashboardu:
 * aktywne (REG/ACT) i nadchodzące (SCH), max `limit` sztuk.
 * Używa lekkiego /api/tournaments/list/ zamiast pełnego /api/tournaments/.
 */
export async function getDashboardTournaments(limit = 5): Promise<TournamentListEntry[]> {
  const all = await getTournamentsList();
  const active = all.filter(t => t.status === 'REG' || t.status === 'ACT' || t.status === 'SCH');
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

/**
 * Zwraca listę rankingową.
 * Endpoint: GET /api/rankings/list/?type=SNG&year=2026
 * Auth: IsAuthenticatedOrReadOnly — publiczny GET, brak auth wymagany.
 * @param matchType 'SNG' | 'DBL' (domyślnie SNG)
 * @param year  rok sezonu lub 'all' dla all-time; undefined = najnowszy dostępny
 */
export async function getRankings(
  matchType: 'SNG' | 'DBL' = 'SNG',
  year?: string | number
): Promise<PlayerRankingEntry[]> {
  const params = new URLSearchParams({ type: matchType });
  if (year !== undefined) params.set('year', String(year));
  const data = await apiFetch<PlayerRankingEntry[]>(`/api/rankings/list/?${params}`);
  return data ?? [];
}

/**
 * Zwraca szczegóły pojedynczego meczu towarzyskiego.
 * Endpoint: GET /api/matches/<id>/
 * Auth: IsAuthenticated — wymaga cookie sesji Django.
 * Zwraca null gdy mecz nie istnieje lub użytkownik niezalogowany.
 */
export async function getMatch(
  id: number,
  sessionCookie?: string
): Promise<MatchHistoryEntry | null> {
  return apiFetch<MatchHistoryEntry>(`/api/matches/${id}/`, { sessionCookie });
}

// ── Bieżący użytkownik ───────────────────────────────────────────────────────

export interface CurrentUser {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
}

/**
 * Zwraca dane zalogowanego użytkownika lub null gdy niezalogowany.
 * Endpoint: GET /api/auth/me/
 * Auth: sessionid cookie.
 */
export async function getCurrentUser(
  sessionCookie?: string
): Promise<CurrentUser | null> {
  const data = await apiFetch<{ authenticated: boolean; user?: CurrentUser }>(
    '/api/auth/me/',
    { sessionCookie }
  );
  return data?.authenticated ? (data.user ?? null) : null;
}

/**
 * Zwraca pełne dane profilu zalogowanego użytkownika (user + profile + rankingi).
 * Endpoint: GET /api/auth/profile/
 * Auth: sessionid cookie.
 * Zwraca null gdy niezalogowany lub backend niedostępny.
 */
export async function getUserProfile(
  sessionCookie?: string
): Promise<UserProfileResponse | null> {
  const data = await apiFetch<UserProfileResponse>(
    '/api/auth/profile/',
    { sessionCookie }
  );
  return data?.authenticated ? data : null;
}

/**
 * Zwraca historię meczów zalogowanego użytkownika.
 * Endpoint: GET /api/matches/history/
 * Auth: IsAuthenticated — wymaga cookie sesji Django.
 * Zwraca [] gdy niezalogowany lub backend niedostępny (graceful degradation).
 */
export async function getMatchHistory(
  sessionCookie?: string
): Promise<MatchHistoryEntry[]> {
  const data = await apiFetch<MatchHistoryEntry[]>('/api/matches/history/', { sessionCookie });
  return data ?? [];
}

/**
 * Zwraca wszystkie powiadomienia zalogowanego użytkownika (przeczytane i nie).
 * Endpoint: GET /api/notifications/
 * Auth: IsAuthenticated — wymaga cookie sesji Django.
 */
export async function getAllNotifications(
  sessionCookie?: string
): Promise<Notification[]> {
  const data = await apiFetch<Notification[]>('/api/notifications/', { sessionCookie });
  return data ?? [];
}
