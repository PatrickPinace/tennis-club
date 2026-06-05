// Organizer bracket — load and render SGL / DBE bracket with organizer styling.
import { escHtml } from './helpers';
import type { OrgPanelConfig, BracketRound, DBEBracketData } from './types';

function matchCard(m: BracketRound['matches'][number]): string {
  const p1Name = m.participant1?.display_name ?? '—';
  const p2Name = m.participant2?.display_name ?? '—';
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

  // Karta BYE: p2 = null — renderujemy wiersz BYE żeby karta miała tę samą wysokość
  const p2Row = m.is_bye
    ? `<div class="bkt-player bkt-player--bye"><span class="bkt-player-name"><abbr title="Wolny los — gracz przechodzi dalej bez rozgrywania meczu">BYE</abbr></span></div>`
    : `<div class="bkt-player${p2Won ? ' bkt-player--winner' : ''}">
        ${p2Seed}
        <span class="bkt-player-name">${escHtml(p2Name)}</span>
        ${p2Won && score ? `<span class="bkt-score">${escHtml(score)}</span>` : ''}
      </div>`;

  return `
    <div class="bkt-match${isDone ? ' bkt-match--done' : ''}${isTbd ? ' bkt-match--tbd' : ''}" data-match-id="${m.id}">
      ${labelBadge}
      <div class="bkt-player${p1Won ? ' bkt-player--winner' : ''}">
        ${p1Seed}
        <span class="bkt-player-name">${escHtml(p1Name)}</span>
        ${p1Won && score ? `<span class="bkt-score">${escHtml(score)}</span>` : ''}
      </div>
      ${p2Row}
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
function cleanRoundLabel(label: string): string {
  return label
    .replace(/\b(WB|LB)\b/gi, '')
    .trim()
    .replace(/\s+/g, ' ');
}

function roundsHtml(rounds: BracketRound[], isFirst = false, hideLabels = false): string {
  return rounds.map((r, roundIdx) => {
    const isFinal = roundIdx === rounds.length - 1;
    const hasEntry = roundIdx > 0;

    const matches = r.matches;
    const nextRound = rounds[roundIdx + 1];
    // Parujemy tylko gdy następna runda ma dokładnie połowę meczów (klasyczny bracket)
    const shouldPair = !isFinal && nextRound != null && nextRound.matches.length === Math.ceil(matches.length / 2) && matches.length > 1;

    let html = '';
    const entryClass = hasEntry ? ' bkt-slot--has-entry' : '';

    if (shouldPair) {
      for (let i = 0; i < matches.length; i += 2) {
        const top = matches[i];
        const bot = matches[i + 1];
        if (bot === undefined) {
          html += `<div class="bkt-slot${entryClass}">${matchCard(top)}</div>`;
        } else {
          html += `<div class="bkt-pair">` +
            `<div class="bkt-slot bkt-slot--connector-top${entryClass}">${matchCard(top)}</div>` +
            `<div class="bkt-slot bkt-slot--connector-bottom${entryClass}">${matchCard(bot)}</div>` +
            `</div>`;
        }
      }
    } else {
      // feeding round lub ostatnia runda — brak pionowych connectorów
      for (const m of matches) {
        html += `<div class="bkt-slot${entryClass}">${matchCard(m)}</div>`;
      }
    }
    const slotsHtml = html;

    const labelHtml = hideLabels ? '' : `<div class="bkt-col-label">${escHtml(cleanRoundLabel(r.round_label))}</div>`;

    return `
    <div class="bkt-col${isFinal ? ' bkt-col--final' : ''}">
      ${labelHtml}
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
        <div class="bkt-section-title">Zwycięzcy</div>
        <div class="bkt-wrap">${roundsHtml(dbe.winners, true)}</div>
      </div>`;
    }

    if (hasLosers) {
      html += `<div class="bkt-section bkt-section--losers">
        <div class="bkt-section-title">Przegrani</div>
        <div class="bkt-wrap">${roundsHtml(dbe.losers, true)}</div>
      </div>`;
    }

    if (hasGF && dbe.grand_final) {
      html += `<div class="bkt-section bkt-section--gf">
        <div class="bkt-section-title bkt-section-title--gf">🏆 Wielki Finał</div>
        <div class="bkt-wrap">${roundsHtml([dbe.grand_final], false, true)}</div>
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

  let thirdPlaceMatch: BracketRound['matches'][number] | null = null;
  const cleanRounds = rounds.map(r => {
    const matchesWithoutThird = r.matches.filter(m => {
      if (m.is_third_place) {
        thirdPlaceMatch = m;
        return false;
      }
      return true;
    });
    return {
      ...r,
      matches: matchesWithoutThird
    };
  });

  let html = `<div class="bkt-wrap">${roundsHtml(cleanRounds, true)}</div>`;

  if (thirdPlaceMatch) {
    html += `
      <div class="bkt-third-place-container">
        <div class="bkt-third-place-header">Mecz o 3. miejsce</div>
        <div class="bkt-third-place-box">
          ${matchCard(thirdPlaceMatch)}
        </div>
      </div>`;
  }

  container.innerHTML = html;
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
