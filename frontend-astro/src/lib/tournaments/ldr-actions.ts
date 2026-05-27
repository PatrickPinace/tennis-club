// ldr-actions.ts — client-side challenge flow dla Drabinki Liderów (LDR)
//
// Obsługuje:
//   - Wyzwanie: klik w .ldr-challenge-btn → POST /api/tournaments/<pk>/challenge/
//   - Accept/Reject: klik w .ldr-accept-btn / .ldr-reject-btn
//       → POST /api/tournaments/<pk>/challenges/<match_id>/<action>/
//
// Po każdej udanej akcji strona jest przeładowywana (najprostszy sposób na
// aktualny ranking SSR). Komunikaty sukcesu/błędu trafiają do #ldr-msg.

import { getCsrf } from './helpers';

(() => {
  const root = document.getElementById('ldr-root') as HTMLDivElement | null;
  if (!root) return;  // nie jesteśmy na widoku LDR

  const tournamentId = root.dataset.tournamentId;
  const API = root.dataset.apiBase ?? '';

  const msgEl = document.getElementById('ldr-msg') as HTMLDivElement | null;

  // ── Helpers ────────────────────────────────────────────────────────────────

  function showMsg(text: string, type: 'ok' | 'err') {
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.className = `ldr-msg ldr-msg--${type} is-visible`;
    msgEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    // auto-hide po 6s (tylko ok)
    if (type === 'ok') setTimeout(() => msgEl.classList.remove('is-visible'), 6000);
  }

  function setLoading(btn: HTMLButtonElement, loading: boolean, original: string) {
    btn.disabled = loading;
    btn.textContent = loading ? '…' : original;
  }

  async function csrf(): Promise<string> {
    // Odśwież CSRF cookie
    await fetch(`${API}/api/auth/csrf/`, { credentials: 'include' }).catch(() => null);
    return getCsrf();
  }

  // ── Challenge (Wyzwij) ─────────────────────────────────────────────────────

  async function handleChallenge(btn: HTMLButtonElement) {
    const participantId = btn.dataset.participantId;
    const participantName = btn.dataset.participantName ?? 'gracza';
    if (!participantId || !tournamentId) return;

    const original = btn.textContent ?? 'Wyzwij';
    setLoading(btn, true, original);

    try {
      const token = await csrf();
      const res = await fetch(`${API}/api/tournaments/${tournamentId}/challenge/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        body: JSON.stringify({ challenged_id: parseInt(participantId, 10) }),
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        showMsg(`Wyzwanie wysłane do ${participantName}. Strona zostanie odświeżona.`, 'ok');
        setTimeout(() => window.location.reload(), 1200);
      } else {
        const detail = data?.detail ?? 'Nie udało się wysłać wyzwania.';
        showMsg(detail, 'err');
        setLoading(btn, false, original);
      }
    } catch {
      showMsg('Błąd połączenia. Sprawdź internet i spróbuj ponownie.', 'err');
      setLoading(btn, false, original);
    }
  }

  // ── Accept / Reject ────────────────────────────────────────────────────────

  async function handleAction(btn: HTMLButtonElement, action: 'accept' | 'reject') {
    const matchId = btn.dataset.matchId;
    if (!matchId || !tournamentId) return;

    const original = btn.textContent ?? action;
    setLoading(btn, true, original);

    // Dezaktywuj sąsiedni przycisk
    const card = btn.closest('.ldr-challenge-card');
    card?.querySelectorAll<HTMLButtonElement>('.ldr-accept-btn, .ldr-reject-btn').forEach(b => {
      b.disabled = true;
    });

    try {
      const token = await csrf();
      const res = await fetch(
        `${API}/api/tournaments/${tournamentId}/challenges/${matchId}/${action}/`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
        }
      );

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        const label = action === 'accept' ? 'zaakceptowano' : 'odrzucono';
        showMsg(`Wyzwanie ${label}. Strona zostanie odświeżona.`, 'ok');
        setTimeout(() => window.location.reload(), 1200);
      } else {
        const detail = data?.detail ?? 'Nie udało się wykonać akcji.';
        showMsg(detail, 'err');
        // Przywróć przyciski
        card?.querySelectorAll<HTMLButtonElement>('.ldr-accept-btn, .ldr-reject-btn').forEach(b => {
          b.disabled = false;
        });
        setLoading(btn, false, original);
      }
    } catch {
      showMsg('Błąd połączenia. Sprawdź internet i spróbuj ponownie.', 'err');
      card?.querySelectorAll<HTMLButtonElement>('.ldr-accept-btn, .ldr-reject-btn').forEach(b => {
        b.disabled = false;
      });
      setLoading(btn, false, original);
    }
  }

  // ── Odśwież ranking po wpisaniu wyniku przez organizer panel ─────────────
  // org-ldr-matches.ts dispatches 'ldr-score-updated' after successful score entry.
  // Ranking is SSR — reload is the simplest correct solution.
  document.addEventListener('ldr-score-updated', () => {
    setTimeout(() => window.location.reload(), 1200);
  });

  // ── Delegacja eventów na root ──────────────────────────────────────────────

  root.addEventListener('click', (e) => {
    const target = e.target as HTMLElement;
    const btn = target.closest('button') as HTMLButtonElement | null;
    if (!btn || btn.disabled) return;

    const action = btn.dataset.action;

    if (action === 'challenge') {
      e.preventDefault();
      handleChallenge(btn);
      return;
    }

    if (action === 'accept' || action === 'reject') {
      e.preventDefault();
      handleAction(btn, action);
      return;
    }
  });
})();
