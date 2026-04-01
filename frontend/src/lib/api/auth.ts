/**
 * Authentication API functions
 */

import type { APIRoute } from 'astro';

const API_BASE_URL = import.meta.env.PUBLIC_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : 'https://tennis.mediprima.pl');

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
}

export interface LoginResponse {
  success: boolean;
  user?: User;
  error?: string;
}

/**
 * Verify session by checking /api/auth/me/
 * Returns user data if authenticated, null otherwise
 */
export async function verifySession(sessionId: string): Promise<User | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me/`, {
      headers: {
        Cookie: `sessionid=${sessionId}`,
      },
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    return data.authenticated ? data.user : null;
  } catch (error) {
    console.error('Session verification failed:', error);
    return null;
  }
}

/**
 * Login user
 * POST /api/auth/login/
 */
export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: data.error || 'Login failed',
      };
    }

    return {
      success: true,
      user: data.user,
    };
  } catch (error) {
    console.error('Login error:', error);
    return {
      success: false,
      error: 'Network error',
    };
  }
}

/**
 * Logout user
 * POST /api/auth/logout/
 */
export async function logout(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/logout/`, {
      method: 'POST',
      credentials: 'include',
    });

    return response.ok;
  } catch (error) {
    console.error('Logout error:', error);
    return false;
  }
}
