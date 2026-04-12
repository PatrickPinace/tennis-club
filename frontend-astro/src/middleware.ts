/**
 * middleware.ts — minimalna ochrona tras wymagających logowania
 *
 * Logika:
 * - Chronione trasy: sprawdź obecność sessionid cookie
 *   → brak: redirect /login?next=<ścieżka>
 * - /login: jeśli sessionid już jest → redirect /dashboard
 * - Publiczne trasy: przepuść bez sprawdzania
 *
 * Uwaga: sprawdzamy tylko obecność cookie sessionid, nie weryfikujemy go
 * przez /api/auth/me/ — Django samo odrzuci request jeśli sesja wygasła
 * (strona dostanie wtedy fallback/empty state, nie dane innego usera).
 * Pełna weryfikacja po stronie Django API jest wystarczającym zabezpieczeniem.
 */
import { defineMiddleware } from 'astro:middleware';

// Trasy wymagające zalogowania — sprawdzane jako prefix
const PRIVATE_PATHS = [
  '/dashboard',
  '/matches',
  '/profile',
  '/tournaments/manage',
  '/tournaments/create',
  '/notifications',
];

// Trasy, które zalogowany user powinien opuścić (redirect na dashboard)
const AUTH_ONLY_PATHS = [
  '/login',
];

function hasSession(request: Request): boolean {
  const cookieHeader = request.headers.get('cookie') ?? '';
  return cookieHeader.split(';').some(c => c.trim().startsWith('sessionid='));
}

const BASE = (import.meta.env.BASE_URL ?? '/').replace(/\/$/, '');

export const onRequest = defineMiddleware((context, next) => {
  const { pathname } = context.url;

  // Usuwamy prefix base z pathname by porównywać do logicznych ścieżek
  const path = pathname.startsWith(BASE) ? pathname.slice(BASE.length) || '/' : pathname;

  const isPrivate = PRIVATE_PATHS.some(p => path === p || path.startsWith(p + '/'));
  const isAuthOnly = AUTH_ONLY_PATHS.some(p => path === p || path.startsWith(p + '/'));

  const loggedIn = hasSession(context.request);

  // Zalogowany user wchodzi na /login → dashboard
  if (isAuthOnly && loggedIn) {
    return context.redirect(BASE + '/dashboard');
  }

  // Niezalogowany user wchodzi na chronioną trasę → /login?next=...
  if (isPrivate && !loggedIn) {
    const next_url = encodeURIComponent(pathname);
    return context.redirect(`${BASE}/login?next=${next_url}`);
  }

  return next();
});
