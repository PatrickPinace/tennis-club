// org-config-ldr.ts — LadderConfig form handler for organizer panel.
// Pattern: analogous to org-config-rr.ts / org-config-amr.ts.
import { getCsrf } from './helpers';
import type { OrgPanelConfig } from './types';

export function initLdrConfigForm(cfg: OrgPanelConfig) {
  const form    = document.getElementById('org-ldr-config-form') as HTMLFormElement | null;
  const saveBtn = document.getElementById('org-ldr-config-save-btn') as HTMLButtonElement | null;
  const msgEl   = document.getElementById('org-ldr-config-msg') as HTMLElement | null;
  if (!form || !saveBtn || !msgEl) return;

  // Spinner buttons (▲▼) for challenge_range
  form.querySelectorAll<HTMLButtonElement>('[data-target]').forEach(btn => {
    btn.addEventListener('click', () => {
      const inputEl = document.getElementById(btn.dataset.target!) as HTMLInputElement | null;
      if (!inputEl) return;
      const dir = btn.classList.contains('org-spin-up') ? 1 : -1;
      const min = parseInt(inputEl.min, 10) || 1;
      const max = parseInt(inputEl.max, 10) || 20;
      const cur = parseInt(inputEl.value, 10) || 1;
      inputEl.value = String(Math.min(max, Math.max(min, cur + dir)));
    });
  });

  // Disable form when locked (FIN/CNC)
  if (cfg.lockedHard) {
    form.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLButtonElement>(
      'input, select, button[type="submit"]'
    ).forEach(el => { el.disabled = true; });
    return;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    saveBtn.disabled = true;
    saveBtn.textContent = 'Zapisywanie…';
    msgEl.textContent = '';
    msgEl.className = 'org-form-msg';

    const rangeEl   = form.elements.namedItem('challenge_range') as HTMLInputElement;
    const seedingEl = form.elements.namedItem('initial_seeding') as HTMLSelectElement;

    const rangeVal = parseInt(rangeEl.value, 10);
    if (!rangeVal || rangeVal < 1) {
      msgEl.textContent = 'Zasięg wyzwania musi być ≥ 1.';
      msgEl.className = 'org-form-msg org-form-msg--err';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Zapisz konfigurację';
      return;
    }

    try {
      const res = await fetch(
        `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/config/ldr/`,
        {
          method: 'PATCH',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
          body: JSON.stringify({
            challenge_range:  rangeVal,
            initial_seeding:  seedingEl.value,
          }),
        }
      );

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        msgEl.textContent = 'Zapisano.';
        msgEl.className = 'org-form-msg org-form-msg--ok';
        setTimeout(() => { if (msgEl) msgEl.textContent = ''; }, 4000);
        // Update data attribute so other modules see the new range
        cfg.panel.dataset.challengeRange = String(data.challenge_range ?? rangeVal);
      } else {
        msgEl.textContent = data.detail ?? `Błąd ${res.status}`;
        msgEl.className = 'org-form-msg org-form-msg--err';
      }
    } catch {
      msgEl.textContent = 'Błąd sieci.';
      msgEl.className = 'org-form-msg org-form-msg--err';
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Zapisz konfigurację';
    }
  });
}
