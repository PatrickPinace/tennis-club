// Organizer status panel — tournament status transitions.
import { escHtml, getCsrf } from './helpers';
import type { OrgPanelConfig } from './types';

export function initStatusPanel(cfg: OrgPanelConfig) {
  const statusSection = document.getElementById('org-status-section');
  if (!statusSection) return;
  const actionsEl = document.getElementById('org-status-actions') as HTMLElement;
  const badgeEl   = document.getElementById('org-status-badge') as HTMLElement;
  const msgEl     = document.getElementById('org-status-msg') as HTMLElement;

  const STATUS_LABELS: Record<string, string> = {
    DRF: 'Szkic', REG: 'Rejestracja', SCH: 'Zaplanowany',
    ACT: 'Trwa', FIN: 'Zakończony', CNC: 'Odwołany',
  };
  const STATUS_BADGE_CLS: Record<string, string> = {
    DRF: 'tc-badge-neutral', REG: 'tc-badge-success', SCH: 'tc-badge-info',
    ACT: 'tc-badge-warning', FIN: 'tc-badge-neutral', CNC: 'tc-badge-neutral',
  };

  const TRANSITIONS: Record<string, Array<{label: string; target: string; confirm?: string}>> = {
    DRF: [{ label: 'Otwórz rejestrację →', target: 'REG' }],
    REG: [
      { label: 'Zamknij zapisy i generuj mecze →', target: 'SCH' },
      { label: '← Cofnij do szkicu', target: 'DRF' },
    ],
    SCH: [
      { label: 'Rozpocznij turniej →', target: 'ACT' },
      {
        label: '← Otwórz zapisy ponownie',
        target: 'REG',
        confirm: 'Uwaga: wszystkie wygenerowane mecze zostaną usunięte. Kontynuować?',
      },
    ],
    ACT: [],
    FIN: [],
    CNC: [],
  };

  function renderStatusActions(currentStatus: string) {
    const transitions = TRANSITIONS[currentStatus] ?? [];
    if (!transitions.length) {
      actionsEl.innerHTML = '';
      return;
    }
    actionsEl.innerHTML = transitions.map(t =>
      `<button class="org-status-btn" data-target="${t.target}" data-confirm="${escHtml(t.confirm ?? '')}" type="button">${escHtml(t.label)}</button>`
    ).join('');

    actionsEl.querySelectorAll<HTMLButtonElement>('[data-target]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const confirmMsg = btn.dataset.confirm ?? '';
        if (confirmMsg && !window.confirm(confirmMsg)) return;

        btn.disabled = true;
        msgEl.textContent = '';
        try {
          const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/status/`, {
            method: 'PATCH', credentials: 'include',
            headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: btn.dataset.target }),
          });
          const data = await res.json().catch(() => ({}));
          if (res.ok) {
            const ns = data.status;
            cfg.panel.dataset.tournamentStatus = ns;
            badgeEl.textContent = STATUS_LABELS[ns] ?? ns;
            badgeEl.className = `tc-badge ${STATUS_BADGE_CLS[ns] ?? 'tc-badge-neutral'}`;
            renderStatusActions(ns);

            if (ns === 'SCH') {
              const matchesGenerated = data.matches_generated ?? 0;
              msgEl.textContent = `Wygenerowano ${matchesGenerated} meczów. Ładowanie…`;
              msgEl.className = 'org-form-msg org-form-msg--ok';
              setTimeout(() => window.location.reload(), 600);
              return;
            } else if (ns === 'REG') {
              msgEl.textContent = 'Mecze usunięte. Ładowanie…';
              msgEl.className = 'org-form-msg org-form-msg--ok';
              setTimeout(() => window.location.reload(), 600);
              return;
            } else if (ns === 'ACT') {
              msgEl.textContent = 'Turniej rozpoczęty. Ładowanie…';
              msgEl.className = 'org-form-msg org-form-msg--ok';
              setTimeout(() => window.location.reload(), 600);
              return;
            } else {
              msgEl.textContent = `Status zmieniony na: ${STATUS_LABELS[ns] ?? ns}`;
            }

            msgEl.className = 'org-form-msg org-form-msg--ok';
            setTimeout(() => { msgEl.textContent = ''; }, 4000);
          } else {
            msgEl.textContent = data.detail ?? `Błąd ${res.status}`;
            msgEl.className = 'org-form-msg org-form-msg--err';
            btn.disabled = false;
          }
        } catch {
          msgEl.textContent = 'Błąd sieci.';
          msgEl.className = 'org-form-msg org-form-msg--err';
          btn.disabled = false;
        }
      });
    });
  }

  renderStatusActions(cfg.tStatus);
}
