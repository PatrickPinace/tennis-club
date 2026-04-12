/**
 * url.ts — helper do budowania ścieżek z uwzględnieniem base URL.
 *
 * W dev (base = '/'):       url('/tournaments') → '/tournaments'
 * W prod (base = '/astro'): url('/tournaments') → '/astro/tournaments'
 *
 * Użycie: import { url } from '@/lib/url';
 *         href={url('/tournaments')}
 */

const BASE = import.meta.env.BASE_URL ?? '/';

/**
 * Zwraca ścieżkę z prefiksem base URL.
 * path musi zaczynać się od '/'.
 */
export function url(path: string): string {
  // BASE kończy się '/' gdy ustawione, np. '/astro/'
  // Usuwamy trailing slash z BASE i leading slash z path by uniknąć '/astro//tournaments'
  const base = BASE.endsWith('/') ? BASE.slice(0, -1) : BASE;
  return base + path;
}
