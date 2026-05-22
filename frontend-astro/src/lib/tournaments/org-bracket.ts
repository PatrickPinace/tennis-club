// Organizer bracket — load and render SGL bracket with organizer styling.
import { escHtml } from './helpers';
import type { OrgPanelConfig, BracketRound } from './types';

export function renderBracket(rounds: BracketRound[]) {
  const container = document.getElementById('bracket-container');
  if (!container) return;

  if (!rounds.length) {
    container.innerHTML = '<div class="org-matches-empty">Brak danych drabinki.</div>';
    return;
  }

  const cols = rounds.map(r => {
    const matchCards = r.matches.map(m => {
      const p1Name = m.participant1?.display_name ?? (m.is_bye ? 'BYE' : '—');
      const p2Name = m.participant2?.display_name ?? (m.is_bye ? 'BYE' : '—');
      const p1Won  = m.winner_id != null && m.participant1 && m.winner_id === m.participant1.id;
      const p2Won  = m.winner_id != null && m.participant2 && m.winner_id === m.participant2.id;
      const score  = m.score ?? (m.status === 'WDR' ? 'WO' : '');
      const isDone = m.status === 'CMP' || m.status === 'WDR';
      const labelBadge = m.is_third_place
        ? `<span class="bkt-third-label">o 3. miejsce</span>`
        : '';

      return `
        <div class="bkt-match${isDone ? ' bkt-match--done' : ''}" data-match-id="${m.id}">
          ${labelBadge}
          <div class="bkt-player${p1Won ? ' bkt-player--winner' : ''}">
            <span class="bkt-player-name">${escHtml(p1Name)}</span>
            ${p1Won && score ? `<span class="bkt-score">${escHtml(score)}</span>` : ''}
          </div>
          <div class="bkt-player${p2Won ? ' bkt-player--winner' : ''}">
            <span class="bkt-player-name">${escHtml(p2Name)}</span>
            ${p2Won && score ? `<span class="bkt-score">${escHtml(score)}</span>` : ''}
          </div>
          ${isDone && !p1Won && !p2Won && score ? `<div class="bkt-score-neutral">${escHtml(score)}</div>` : ''}
        </div>`;
    }).join('');

    return `
      <div class="bkt-col">
        <div class="bkt-col-label">${escHtml(r.round_label)}</div>
        <div class="bkt-col-matches">${matchCards}</div>
      </div>`;
  }).join('');

  container.innerHTML = `<div class="bkt-wrap">${cols}</div>`;
}

export async function loadBracket(cfg: OrgPanelConfig) {
  const container = document.getElementById('bracket-container');
  try {
    const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/bracket/`, { credentials: 'include' });
    if (!res.ok) return;
    const rounds = await res.json();
    renderBracket(rounds);
  } catch {
    if (container) container.innerHTML = '<div class="org-matches-empty">Błąd ładowania drabinki.</div>';
  }
}
