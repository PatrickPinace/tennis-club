// Organizer finish tournament — confirm and POST /finish/.
import { escHtml, getCsrf } from './helpers';
import type { OrgPanelConfig } from './types';

let finishHandlersBound = false;

function bindFinishHandlers(finishSection: HTMLElement, cfg: OrgPanelConfig, loadStandings: () => Promise<void>) {
  if (finishHandlersBound) return;
  finishHandlersBound = true;

  const panel = document.getElementById('org-panel') as HTMLElement;
  const triggerWrap   = document.getElementById('org-finish-trigger-wrap') as HTMLElement;
  const confirmBox    = document.getElementById('org-finish-confirm') as HTMLElement;
  const finishBtn     = document.getElementById('org-finish-btn') as HTMLButtonElement;
  const yesBtn        = document.getElementById('org-finish-yes-btn') as HTMLButtonElement;
  const cancelBtn     = document.getElementById('org-finish-cancel-btn') as HTMLButtonElement;
  const msgEl         = document.getElementById('org-finish-msg') as HTMLElement;

  const unplayedWarnEl = document.getElementById('org-finish-unplayed-warn') as HTMLElement | null;
  finishBtn.addEventListener('click', () => {
    triggerWrap.style.display = 'none';

    if (unplayedWarnEl) {
      try {
        const ssrMatches: Array<{ status: string }> =
          JSON.parse(document.getElementById('ssr-matches-data')?.textContent ?? '[]');
        const unplayed = ssrMatches.filter(m =>
          m.status === 'WAI' || m.status === 'SCH' || m.status === 'INP'
        ).length;
        if (unplayed > 0) {
          const noun = unplayed === 1 ? 'mecz nie został rozegrany' : 'meczów nie zostało rozegranych';
          const pronoun = unplayed === 1 ? 'jego wynik' : 'ich wyniki';
          unplayedWarnEl.innerHTML =
            `<svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style="flex-shrink:0;color:#f59e0b;">`
            + `<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`
            + `<span><strong>${unplayed} ${noun}</strong> — ${pronoun} nie będą liczone do rankingu.</span>`;
          unplayedWarnEl.style.display = 'flex';
        } else {
          unplayedWarnEl.style.display = 'none';
        }
      } catch (_) { unplayedWarnEl.style.display = 'none'; }
    }

    confirmBox.style.display = 'block';
  });

  cancelBtn.addEventListener('click', () => {
    confirmBox.style.display = 'none';
    triggerWrap.style.display = 'block';
    msgEl.textContent = '';
    msgEl.className = 'org-form-msg';
  });

  yesBtn.addEventListener('click', async () => {
    yesBtn.disabled = true;
    yesBtn.textContent = 'Kończenie…';

    try {
      const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/finish/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        confirmBox.style.display = 'none';
        finishSection.style.cssText = 'padding:16px 20px 20px;border-top:1px solid var(--border);';
        const warnings: string[] = [];
        if (data.unplayed_count > 0) {
          const noun = data.unplayed_count === 1 ? 'mecz nie został rozegrany' : 'meczów nie zostało rozegranych';
          const pronoun = data.unplayed_count === 1 ? 'jego wynik' : 'ich wyniki';
          warnings.push(`${data.unplayed_count} ${noun} — ${pronoun} nie zostały zliczone.`);
        }
        if (data.warning) warnings.push(escHtml(data.warning));
        finishSection.innerHTML = `
          <div class="org-finish-success">
            <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>
            <span>Turniej zakończony. Ranking zostanie przeliczony.</span>
            ${warnings.map(w => `<span class="org-finish-warning">${w}</span>`).join('')}
          </div>`;

        const statusBadges = document.querySelectorAll<HTMLElement>('.tc-badge');
        statusBadges.forEach(el => {
          if (el.textContent?.trim() === 'Trwa') {
            el.textContent = 'Zakończony';
            el.className = 'tc-badge tc-badge-neutral';
          }
        });

        panel.dataset.tournamentStatus = 'FIN';
        setTimeout(() => loadStandings(), 1200);

      } else {
        confirmBox.style.display = 'none';
        triggerWrap.style.display = 'block';
        yesBtn.disabled = false;
        yesBtn.textContent = 'Tak, zakończ turniej';
        msgEl.textContent = data.detail ?? 'Błąd serwera.';
        msgEl.className = 'org-form-msg org-form-msg--err';
      }

    } catch (e) {
      confirmBox.style.display = 'none';
      triggerWrap.style.display = 'block';
      yesBtn.disabled = false;
      yesBtn.textContent = 'Tak, zakończ turniej';
      msgEl.textContent = 'Błąd połączenia z API.';
      msgEl.className = 'org-form-msg org-form-msg--err';
    }
  });
}

export function initFinishButton(cfg: OrgPanelConfig, loadStandings: () => Promise<void>) {
  const panel = document.getElementById('org-panel') as HTMLElement | null;
  if (!panel) return;
  const finishSection = document.getElementById('org-finish-section') as HTMLElement | null;
  if (!finishSection) return;
  if (panel.dataset.tournamentStatus === 'ACT') {
    finishSection.style.display = 'block';
    bindFinishHandlers(finishSection, cfg, loadStandings);
  }
}
