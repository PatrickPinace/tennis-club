// Organizer RR config form — sets_to_win, games_per_set, points config.
import { getCsrf } from './helpers';
import type { OrgPanelConfig, StandingsRowRR } from './types';
import { renderStandingsRows } from './org-standings';

export function initConfigForm(cfg: OrgPanelConfig) {
  const form = document.getElementById('org-config-form') as HTMLFormElement | null;
  if (!form) return;

  const cfgEl = document.getElementById('ssr-config-data');
  if (cfgEl) {
    try {
      const cfgData: Record<string, string | number> = JSON.parse(cfgEl.textContent ?? '{}');
      for (const [k, v] of Object.entries(cfgData)) {
        const el = form.elements.namedItem(k) as HTMLInputElement | HTMLSelectElement | null;
        if (el) el.value = String(v);
      }
    } catch { /* don't block */ }
  }

  const started = ['ACT', 'FIN', 'CNC', 'SCH'].includes(cfg.tStatus);
  if (started) {
    ['sets_to_win', 'games_per_set'].forEach(name => {
      const el = form.elements.namedItem(name) as HTMLInputElement | null;
      if (el) {
        el.disabled = true;
        const lbl = document.getElementById(`lbl-${name.replaceAll('_', '-')}`);
        if (lbl) lbl.title = 'Nie można zmieniać po rozpoczęciu turnieju';
      }
    });
  }

  form.addEventListener('submit', (e) => handleConfigSubmit(e, cfg));

  // Spin buttons for config numeric fields
  form.querySelectorAll<HTMLButtonElement>('.org-cfg-spin').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.closest('.org-score-spinner')?.querySelector<HTMLInputElement>('.org-cfg-input');
      if (!input) return;
      const step = parseFloat(input.step || '1');
      const cur  = input.value === '' ? 0 : parseFloat(input.value);
      const max  = parseFloat(input.max || '100');
      const min  = parseFloat(input.min || '-100');
      const next = btn.classList.contains('org-spin-up')
        ? Math.min(parseFloat((cur + step).toFixed(10)), max)
        : Math.max(parseFloat((cur - step).toFixed(10)), min);
      input.value = String(next);
      input.dispatchEvent(new Event('input'));
    });
  });
}

async function handleConfigSubmit(e: Event, cfg: OrgPanelConfig) {
  e.preventDefault();
  const form = e.currentTarget as HTMLFormElement;
  const btn = document.getElementById('org-config-save-btn') as HTMLButtonElement | null;
  const msgEl = document.getElementById('org-config-msg');

  if (btn) btn.disabled = true;
  if (msgEl) { msgEl.textContent = ''; msgEl.className = 'org-form-msg'; }

  const body: Record<string, string | number> = {};
  for (const el of Array.from(form.elements) as (HTMLInputElement | HTMLSelectElement)[]) {
    if (!el.name || el.disabled || el.value === '') continue;
    body[el.name] = el.value;
  }

  const csrf = getCsrf();
  try {
    const res = await fetch(
      `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/config/`,
      {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(csrf ? { 'X-CSRFToken': csrf } : {}),
        },
        body: JSON.stringify(body),
      }
    );

    if (res.ok) {
      const data = await res.json();

      const cfgEl = document.getElementById('ssr-config-data');
      if (cfgEl && data.config) cfgEl.textContent = JSON.stringify(data.config);

      if (data.standings) {
        renderStandingsRows(data.standings as StandingsRowRR[]);
      } else {
        const { loadStandings } = await import('./org-standings');
        await loadStandings(cfg);
      }

      if (msgEl) { msgEl.textContent = 'Konfiguracja zapisana.'; msgEl.className = 'org-form-msg org-form-msg--ok'; }
      setTimeout(() => { if (msgEl) { msgEl.textContent = ''; msgEl.className = 'org-form-msg'; } }, 4000);
    } else {
      const err = await res.json().catch(() => ({}));
      const firstErr = Object.values(err as Record<string, unknown>)
        .map(v => Array.isArray(v) ? v[0] : String(v))
        .find(Boolean);
      if (msgEl) { msgEl.textContent = firstErr || `Błąd ${res.status}`; msgEl.className = 'org-form-msg org-form-msg--err'; }
    }
  } catch {
    if (msgEl) { msgEl.textContent = 'Błąd sieci.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}
