// Organizer AMR config form — number_of_rounds, points_per_match.
import { getCsrf } from './helpers';
import type { OrgPanelConfig } from './types';

export function initAmrConfigForm(cfg: OrgPanelConfig) {
  const form = document.getElementById('org-amr-config-form') as HTMLFormElement | null;
  if (!form) return;
  const msgEl = document.getElementById('org-amr-cfg-msg') as HTMLElement;
  const btn   = document.getElementById('org-amr-cfg-save-btn') as HTMLButtonElement;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const rounds = parseInt((form.elements.namedItem('number_of_rounds') as HTMLInputElement).value, 10);
    const ppm    = parseInt((form.elements.namedItem('points_per_match') as HTMLInputElement).value, 10);
    if (!rounds || rounds < 1) { msgEl.textContent = 'Liczba rund musi wynosić ≥ 1.'; msgEl.className = 'org-form-msg org-form-msg--err'; return; }
    if (!ppm || ppm < 1)       { msgEl.textContent = 'Punkty na mecz muszą wynosić ≥ 1.'; msgEl.className = 'org-form-msg org-form-msg--err'; return; }
    btn.disabled = true;
    msgEl.textContent = '';
    try {
      const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/config/amr/`, {
        method: 'POST', credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ number_of_rounds: rounds, points_per_match: ppm }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        msgEl.textContent = 'Zapisano.';
        msgEl.className = 'org-form-msg org-form-msg--ok';
        setTimeout(() => { msgEl.textContent = ''; msgEl.className = 'org-form-msg'; }, 3000);
      } else {
        msgEl.textContent = data.detail ?? `Błąd ${res.status}`;
        msgEl.className = 'org-form-msg org-form-msg--err';
      }
    } catch {
      msgEl.textContent = 'Błąd sieci.';
      msgEl.className = 'org-form-msg org-form-msg--err';
    } finally {
      btn.disabled = false;
    }
  });
}
