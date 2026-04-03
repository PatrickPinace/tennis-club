/**
 * API client
 * Generic HTTP client for making requests to Django backend
 */

const API_BASE_URL = import.meta.env.PUBLIC_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : 'https://tennis.mediprima.pl');

/**
 * Get CSRF token from cookies
 */
function getCsrfToken(): string | null {
  const name = 'csrftoken';
  const cookies = document.cookie.split(';');
  for (let cookie of cookies) {
    cookie = cookie.trim();
    if (cookie.startsWith(name + '=')) {
      return decodeURIComponent(cookie.substring(name.length + 1));
    }
  }
  return null;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers || {})
  };

  // Add CSRF token for non-GET requests
  if (csrfToken && init?.method && init.method !== 'GET') {
    headers['X-CSRFToken'] = csrfToken;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers,
    ...init
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw { status: res.status, body };
  }

  return res.json();
}
