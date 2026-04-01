/**
 * Astro Middleware
 * Handles authentication for protected routes
 */

import { defineMiddleware } from 'astro:middleware';
import { verifySession } from '@lib/api/auth';

const PROTECTED_ROUTES = ['/app'];
const PUBLIC_ROUTES = ['/login', '/register', '/'];

export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;

  // Auth enabled - backend is working!
  const BYPASS_AUTH = false;

  // Check if this is a protected route
  const isProtected = PROTECTED_ROUTES.some(route => pathname.startsWith(route));

  if (!isProtected) {
    // Public route - allow access
    return next();
  }

  // Get sessionid cookie
  const sessionCookie = context.cookies.get('sessionid');
  const sessionId = sessionCookie?.value;

  if (!sessionId) {
    // No session cookie - redirect to login
    return context.redirect('/login');
  }

  // Verify session with Django backend
  try {
    const user = await verifySession(sessionId);

    if (!user) {
      // Invalid or expired session - redirect to login
      return context.redirect('/login?error=session_expired');
    }

    // Session is valid - store user in context.locals
    context.locals.user = user;

    return next();
  } catch (error) {
    console.error('Session verification error:', error);
    return context.redirect('/login?error=verification_failed');
  }
});
