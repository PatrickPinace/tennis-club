// Mexicano round progress section — status display + next round generation.
import { getCsrf } from './helpers';
import type { OrgPanelConfig } from './types';

export function initMexicanoRoundSection(cfg: OrgPanelConfig) {
  const section = document.getElementById('mexicano-round-section') as HTMLElement | null;
  if (!section) return;

  const totalRounds  = Number(section.dataset.totalRounds  || 0);
  const labelEl      = document.getElementById('mexicano-round-label')    as HTMLElement;
  const nextWrap     = document.getElementById('mexicano-next-wrap')      as HTMLElement;
  const nextBtn      = document.getElementById('mexicano-next-btn')       as HTMLButtonElement;
  const nextMsg      = document.getElementById('mexicano-next-msg')       as HTMLElement;
  const lastNote     = document.getElementById('mexicano-last-round-note') as HTMLElement;

  function refreshRoundStatus() {
    let matches: Array<{round_number: number; status: string}> = [];
    try {
      const el = document.getElementById('amr-ssr-matches-data') ?? document.getElementById('ssr-matches-data');
      matches = JSON.parse(el?.textContent ?? '[]');
    } catch (_) {}

    const maxRound = matches.reduce((m, x) => Math.max(m, x.round_number || 0), 0);
    const roundMatches = matches.filter(m => m.round_number === maxRound);
    const pending = roundMatches.filter(m => m.status !== 'CMP' && m.status !== 'WDR' && m.status !== 'CNC').length;
    const total   = roundMatches.length;
    const isComplete = total > 0 && pending === 0;
    const isLastRound = totalRounds > 0 && maxRound >= totalRounds;

    if (maxRound === 0) {
      labelEl.textContent = 'Brak meczów — zamknij rejestrację by wygenerować pierwszą rundę.';
      return;
    }

    if (isComplete) {
      labelEl.innerHTML = `Runda <strong>${maxRound}</strong>/${totalRounds || '?'} — <span style="color:var(--success,#22c55e);">kompletna ✓</span>`;
      if (isLastRound) {
        lastNote.style.display = 'block';
        nextWrap.style.display = 'none';
      } else {
        nextWrap.style.display = 'block';
        lastNote.style.display = 'none';
      }
    } else {
      labelEl.innerHTML = `Runda <strong>${maxRound}</strong>/${totalRounds || '?'} — pozostało <strong>${pending}</strong> z ${total} meczów`;
      nextWrap.style.display = 'none';
      lastNote.style.display = 'none';
    }
  }

  refreshRoundStatus();

  document.addEventListener('amr-match-scored', refreshRoundStatus);

  nextBtn.addEventListener('click', async () => {
    nextBtn.disabled = true;
    nextBtn.textContent = 'Generowanie…';
    nextMsg.textContent = '';
    nextMsg.className = 'org-form-msg';

    try {
      const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/amr/next-round/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        nextMsg.textContent = `Wygenerowano ${data.generated} meczów.`;
        nextMsg.className = 'org-form-msg org-form-msg--ok';
        nextWrap.style.display = 'none';
        setTimeout(() => location.reload(), 900);
      } else {
        nextMsg.textContent = data.detail ?? 'Błąd generowania rundy.';
        nextMsg.className = 'org-form-msg org-form-msg--err';
        nextBtn.disabled = false;
        nextBtn.textContent = '⚡ Generuj następną rundę →';
      }
    } catch (_) {
      nextMsg.textContent = 'Błąd sieci.';
      nextMsg.className = 'org-form-msg org-form-msg--err';
      nextBtn.disabled = false;
      nextBtn.textContent = '⚡ Generuj następną rundę →';
    }
  });
}
