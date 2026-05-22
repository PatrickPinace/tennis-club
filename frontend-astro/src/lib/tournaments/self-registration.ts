// Self-registration — allows logged-in users to join a tournament in REG status.
import { getCsrf, getApiBase } from './helpers';

(() => {
  const panel = document.getElementById('join-panel');
  if (!panel) return; // turniej nie jest w REG

  const tournamentId = panel.dataset.tournamentId;
  const apiBase = getApiBase();

  // Parsuj uczestników z SSR — sprawdź czy user jest już zapisany
  type JoinParticipant = { id: number; user_id: number | null; status: string };
  let participants: JoinParticipant[] = [];
  try {
    const el = document.getElementById('ssr-participants-data');
    if (el) participants = JSON.parse(el.textContent ?? '[]');
  } catch { /* brak */ }

  // Sprawdź czy user jest zalogowany i pobierz jego ID
  fetch(`${apiBase}/api/auth/me/`, { credentials: 'include' })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data?.authenticated || !data?.user) return;
      const myId: number | null = data.user.id ?? null;
      if (!myId) return;

      // Sprawdź czy user jest już aktywnym uczestnikiem
      const alreadyIn = participants.some(p => p.user_id === myId);
      if (alreadyIn) return;

      // Pokaż panel
      panel.style.display = '';

      const btn = document.getElementById('join-btn') as HTMLButtonElement | null;
      const msg = document.getElementById('join-msg');
      if (!btn || !msg) return;

      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.textContent = 'Zapisuję…';
        msg.textContent = '';
        msg.className = 'org-form-msg';
        try {
          const res = await fetch(`${apiBase}/api/tournaments/${tournamentId}/join/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
          });
          if (res.ok) {
            msg.textContent = 'Dołączono! Strona zostanie odświeżona…';
            msg.classList.add('org-form-msg--ok');
            setTimeout(() => window.location.reload(), 1200);
          } else {
            const err = await res.json().catch(() => ({}));
            msg.textContent = err.detail ?? err.error ?? `Błąd ${res.status}`;
            msg.classList.add('org-form-msg--err');
            btn.disabled = false;
            btn.textContent = 'Dołącz';
          }
        } catch {
          msg.textContent = 'Błąd połączenia.';
          msg.classList.add('org-form-msg--err');
          btn.disabled = false;
          btn.textContent = 'Dołącz';
        }
      });
    })
    .catch(() => { /* niezalogowany lub brak połączenia */ });
})();
