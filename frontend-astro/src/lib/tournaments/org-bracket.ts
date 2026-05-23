// Organizer bracket — load and render SGL / DBE bracket with organizer styling.
import { escHtml } from './helpers';
import type { OrgPanelConfig, BracketRound, DBEBracketData } from './types';

function matchCard(m: BracketRound['matches'][number]): string {
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
}

function roundsHtml(rounds: BracketRound[]): string {
  return rounds.map(r => `
    <div class="bkt-col">
      <div class="bkt-col-label">${escHtml(r.round_label)}</div>
      <div class="bkt-col-matches">${r.matches.map(matchCard).join('')}</div>
    </div>`).join('');
}

export function renderBracket(data: BracketRound[] | DBEBracketData) {
  const container = document.getElementById('bracket-container');
  if (!container) return;

  // DBE response: { type: 'dbe', winners, losers, grand_final }
  if (!Array.isArray(data) && (data as DBEBracketData).type === 'dbe') {
    const dbe = data as DBEBracketData;
    const hasWinners = dbe.winners.length > 0;
    const hasLosers  = dbe.losers.length > 0;
    const hasGF      = dbe.grand_final != null;

    if (!hasWinners && !hasLosers && !hasGF) {
      container.innerHTML = '<div class="org-matches-empty">Brak danych drabinki.</div>';
      return;
    }

    let html = '';

    if (hasWinners) {
      html += `<div class="bkt-section">
        <div class="bkt-section-title">Winners Bracket</div>
        <div class="bkt-wrap">${roundsHtml(dbe.winners)}</div>
      </div>`;
    }

    if (hasLosers) {
      html += `<div class="bkt-section">
        <div class="bkt-section-title">Losers Bracket</div>
        <div class="bkt-wrap">${roundsHtml(dbe.losers)}</div>
      </div>`;
    }

    if (hasGF && dbe.grand_final) {
      const gfCols = roundsHtml([dbe.grand_final]);
      html += `<div class="bkt-section bkt-section--gf">
        <div class="bkt-section-title bkt-section-title--gf">Wielki Finał</div>
        <div class="bkt-wrap">${gfCols}</div>
      </div>`;
    }

    container.innerHTML = html;
    return;
  }

  // SGL response: flat array of rounds
  const rounds = data as BracketRound[];
  if (!rounds.length) {
    container.innerHTML = '<div class="org-matches-empty">Brak danych drabinki.</div>';
    return;
  }
  container.innerHTML = `<div class="bkt-wrap">${roundsHtml(rounds)}</div>`;
}

export async function loadBracket(cfg: OrgPanelConfig) {
  const container = document.getElementById('bracket-container');
  try {
    const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/bracket/`, { credentials: 'include' });
    if (!res.ok) return;
    const data = await res.json();
    renderBracket(data);
  } catch {
    if (container) container.innerHTML = '<div class="org-matches-empty">Błąd ładowania drabinki.</div>';
  }
}
