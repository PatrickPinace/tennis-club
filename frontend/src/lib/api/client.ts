/**
 * API client
 * Generic HTTP client for making requests to Django backend
 */

const API_BASE_URL = import.meta.env.PUBLIC_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : 'https://tennis.mediprima.pl');

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {})
    },
    ...init
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw { status: res.status, body };
  }

  return res.json();
}
