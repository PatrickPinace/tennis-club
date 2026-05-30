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
  const isTbd  = !m.participant1 && !m.participant2 && !m.is_bye;

  const labelBadge = m.is_third_place
    ? `<span class="bkt-third-label">o 3. miejsce</span>`
    : '';

  const p1Seed = m.participant1?.seed_number ? `<span class="bkt-player-seed">${m.participant1.seed_number}</span>` : '';
  const p2Seed = m.participant2?.seed_number ? `<span class="bkt-player-seed">${m.participant2.seed_number}</span>` : '';

  return `
    <div class="bkt-match${isDone ? ' bkt-match--done' : ''}${isTbd ? ' bkt-match--tbd' : ''}" data-match-id="${m.id}">
      ${labelBadge}
      <div class="bkt-player${p1Won ? ' bkt-player--winner' : ''}">
        ${p1Seed}
        <span class="bkt-player-name">${escHtml(p1Name)}</span>
        ${p1Won && score ? `<span class="bkt-score">${escHtml(score)}</span>` : ''}
      </div>
      <div class="bkt-player${p2Won ? ' bkt-player--winner' : ''}">
        ${p2Seed}
        <span class="bkt-player-name">${escHtml(p2Name)}</span>
        ${p2Won && score ? `<span class="bkt-score">${escHtml(score)}</span>` : ''}
      </div>
      ${isDone && !p1Won && !p2Won && score ? `<div class="bkt-score-neutral">${escHtml(score)}</div>` : ''}
    </div>`;
}

/**
 * Wraps each match card in a `.bkt-slot` which carries the connector-line
 * pseudo-elements.  Slots are paired for connectors:
 *   - slot at even index (0,2,4…) → .bkt-slot--connector-top  (line goes DOWN)
 *   - slot at odd index  (1,3,5…) → .bkt-slot--connector-bottom (line goes UP)
 * Both share the same vertical bar position (right edge of the slot).
 * The right horizontal arm (::after on .bkt-slot) connects to the next column.
 * The left horizontal entry (::after on .bkt-slot--has-entry) connects from
 * the previous column (all columns except the first).
 */
function roundsHtml(rounds: BracketRound[], isFirst = false): string {
  return rounds.map((r, roundIdx) => {
    const isFinal = roundIdx === rounds.length - 1;
    const hasEntry = roundIdx > 0;

    const slotsHtml = r.matches.map((m, i) => {
      const isEven = i % 2 === 0;
      // Mecze BYE nie tworzą par z konektorem — zwycięzca awansuje automatycznie
      const isByeMatch = m.is_bye === true;
      const connectorClass = isByeMatch ? '' : (isEven ? 'bkt-slot--connector-top' : 'bkt-slot--connector-bottom');
      const entryClass = hasEntry ? ' bkt-slot--has-entry' : '';
      return `<div class="bkt-slot ${connectorClass}${entryClass}">${matchCard(m)}</div>`;
    }).join('');

    return `
    <div class="bkt-col${isFinal ? ' bkt-col--final' : ''}">
      <div class="bkt-col-label">${escHtml(r.round_label)}</div>
      <div class="bkt-col-matches">${slotsHtml}</div>
    </div>`;
  }).join('');
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
        <div class="bkt-wrap">${roundsHtml(dbe.winners, true)}</div>
      </div>`;
    }

    if (hasLosers) {
      html += `<div class="bkt-section">
        <div class="bkt-section-title">Losers Bracket</div>
        <div class="bkt-wrap">${roundsHtml(dbe.losers, true)}</div>
      </div>`;
    }

    if (hasGF && dbe.grand_final) {
      html += `<div class="bkt-section bkt-section--gf">
        <div class="bkt-section-title bkt-section-title--gf">Wielki Finał</div>
        <div class="bkt-wrap">${roundsHtml([dbe.grand_final])}</div>
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
  container.innerHTML = `<div class="bkt-wrap">${roundsHtml(rounds, true)}</div>`;
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
