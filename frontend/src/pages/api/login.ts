/**
 * Login API endpoint
 * Handles form submission and authenticates with Django
 */

import type { APIRoute } from 'astro';

const API_BASE_URL = import.meta.env.PUBLIC_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : 'https://tennis.mediprima.pl');

export const POST: APIRoute = async ({ request, cookies, redirect }) => {
  const formData = await request.formData();
  const username = formData.get('username') as string;
  const password = formData.get('password') as string;

  if (!username || !password) {
    return redirect('/login?error=missing_fields');
  }

  try {
    // Authenticate with Django
    const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      // Login failed - redirect back to login with error
      const errorMsg = encodeURIComponent(data.error || 'Login failed');
      return redirect(`/login?error=${errorMsg}`);
    }

    // Login successful - get sessionid cookie from Django response
    const setCookieHeader = response.headers.get('set-cookie');

    if (setCookieHeader) {
      // Parse sessionid from Set-Cookie header
      const sessionMatch = setCookieHeader.match(/sessionid=([^;]+)/);

      if (sessionMatch) {
        const sessionId = sessionMatch[1];

        // Set sessionid cookie in Astro
        cookies.set('sessionid', sessionId, {
          path: '/',
          httpOnly: true,
          secure: import.meta.env.PROD, // Only secure in production
          sameSite: 'lax',
          maxAge: 60 * 60 * 24 * 7, // 7 days
        });
      }
    }

    // Redirect to dashboard
    return redirect('/app');
  } catch (error) {
    console.error('Login error:', error);
    return redirect('/login?error=network_error');
  }
};
