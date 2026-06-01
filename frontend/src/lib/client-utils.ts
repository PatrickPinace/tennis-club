/**
 * client-utils.ts — shared client-side utilities.
 *
 * Importowalny w blokach <script> Astro:
 *   import { getCsrf, escHtml } from '@/lib/client-utils';
 *
 * UWAGA: Ten plik trafia do bundle klienta — nie używaj tu Node.js API.
 */

/**
 * Odczytuje wartość tokenu CSRF z cookie (csrftoken=...).
 * Zwraca pusty string gdy cookie nie istnieje.
 */
export function getCsrf(): string {
  return document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? '';
}

/**
 * Escapuje znaki specjalne HTML, zapobiegając XSS przy wstawianiu
 * treści przez innerHTML.
 */
export function escHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
