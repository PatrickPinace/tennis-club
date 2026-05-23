// Public bracket rendering for SGL and DBE tournaments.
// Fetches and renders bracket for all users (not just organizer).
import { escHtml, getApiBase } from './helpers';
import { renderBracket } from './org-bracket';

(async () => {
  const panel = document.getElementById('org-panel') ?? document.getElementById('org-panel-dbe');
  if (!panel) return;
  const tType   = panel.dataset.tournamentType ?? 'RND';
  const tStatus = panel.dataset.tournamentStatus ?? '';
  const apiBase = getApiBase();
  const tid     = panel.dataset.tournamentId;

  const isBracketType = tType === 'SGL' || tType === 'DBE';
  if (isBracketType && tStatus !== 'DRF' && tStatus !== 'REG') {
    const container = document.getElementById('bracket-container');
    if (container) {
      try {
        const res = await fetch(`${apiBase}/api/tournaments/${tid}/bracket/`, { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          renderBracket(data);
        }
      } catch { /* cicha degradacja */ }
    }
  }
})();
