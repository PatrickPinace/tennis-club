// Organizer interactive RR matrix — click-to-scroll to match card.
import { escHtml, abbrev } from './helpers';
import type { OrgPanelConfig, MatchData, ParticipantData } from './types';
import type { MatchState } from './org-matches';

export function buildMatrix(cfg: OrgPanelConfig, state: MatchState) {
  const wrap = document.getElementById('rr-matrix-inner');
  if (!wrap) return;

  // If allMatches not yet populated, load from SSR
  if (state.allMatches.length === 0) {
    const matchesEl = document.getElementById('ssr-matches-data');
    if (matchesEl) {
      try { state.allMatches = JSON.parse(matchesEl.textContent ?? '[]'); } catch { /* no data */ }
    }
  }

  const partEl = document.getElementById('ssr-participants-data');
  if (!partEl) return;
  let participants: ParticipantData[] = [];
  try { participants = JSON.parse(partEl.textContent ?? '[]'); } catch { return; }
  if (participants.length < 2) {
    wrap.innerHTML = '<p style="padding:12px;font-size:0.82rem;color:var(--text-dim);">Za mało uczestników do macierzy.</p>';
    return;
  }

  const matchMap = new Map<string, MatchData>();
  for (const m of state.allMatches) {
    if (!m.participant1_id || !m.participant2_id) continue;
    const key = `${Math.min(m.participant1_id, m.participant2_id)}_${Math.max(m.participant1_id, m.participant2_id)}`;
    matchMap.set(key, m);
  }

  let html = '<table class="rr-matrix" role="grid">';

  html += '<thead><tr><th class="rr-matrix__row-head rr-matrix__corner"></th>';
  for (const p of participants) {
    html += `<th class="rr-matrix__col-head" title="${escHtml(p.display_name)}">${escHtml(abbrev(p.display_name))}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const row of participants) {
    html += `<tr><td class="rr-matrix__row-head" title="${escHtml(row.display_name)}">${escHtml(row.display_name)}</td>`;
    for (const col of participants) {
      if (row.id === col.id) {
        html += '<td class="rr-matrix__diag" aria-hidden="true"></td>';
        continue;
      }
      const key = `${Math.min(row.id, col.id)}_${Math.max(row.id, col.id)}`;
      const m = matchMap.get(key);

      if (!m) {
        html += '<td class="rr-matrix__cell rr-matrix__cell--empty" aria-label="brak meczu"><span class="rr-matrix__cell-dash">—</span></td>';
        continue;
      }

      const rowName = row.id === m.participant1_id ? m.participant1_name : m.participant2_name;
      const colName = row.id === m.participant1_id ? m.participant2_name : m.participant1_name;
      let cellCls = 'rr-matrix__cell';
      let label = '';
      let inner = '';

      if (m.status === 'CMP') {
        const rowWon  = m.winner_name !== null && m.winner_name === rowName;
        const colWon  = m.winner_name !== null && m.winner_name === colName;
        const isDraw  = m.winner_name === null;
        cellCls += isDraw ? ' rr-matrix__cell--draw' : rowWon ? ' rr-matrix__cell--win' : ' rr-matrix__cell--loss';
        label = isDraw ? 'remis' : rowWon ? 'wygrana' : 'przegrana';
        const badge = isDraw ? 'R' : rowWon ? 'W' : 'P';
        inner = `<span class="rr-matrix__badge">${badge}</span>`
              + (m.score ? `<span class="rr-matrix__score">${escHtml(m.score).replace(/ /g,' ')}</span>` : '');
      } else if (m.status === 'WDR') {
        cellCls += ' rr-matrix__cell--wdr';
        const rowWon = m.winner_name === rowName;
        label = rowWon ? 'walkover — wygrana' : 'walkover — przegrana';
        inner = `<span class="rr-matrix__badge">WO</span>`;
      } else if (m.status === 'INP') {
        cellCls += ' rr-matrix__cell--live';
        label = 'w trakcie';
        inner = '<span class="rr-matrix__live-dot">●</span>';
      } else {
        cellCls += ' rr-matrix__cell--pending';
        label = m.status === 'SCH' ? 'zaplanowany' : 'oczekuje';
        inner = `<span class="rr-matrix__cell-dash">${m.status === 'SCH' ? '·' : '·'}</span>`;
      }

      const tooltip = `${escHtml(rowName ?? '')} vs ${escHtml(colName ?? '')}${m.score ? ': ' + m.score : ''}`;
      html += `<td class="${cellCls}" data-match-id="${m.id}" role="button" tabindex="0" title="${tooltip}" aria-label="${label}">${inner}</td>`;
    }
    html += '</tr>';
  }

  html += '</tbody></table>';
  wrap.innerHTML = html;

  // Click cell → scroll to match card
  wrap.querySelectorAll<HTMLElement>('[data-match-id]').forEach(cell => {
    const handler = () => {
      const mid = cell.dataset.matchId;
      if (!mid) return;

      wrap.querySelectorAll('.rr-matrix__cell--highlight').forEach(c => c.classList.remove('rr-matrix__cell--highlight'));
      cell.classList.add('rr-matrix__cell--highlight');

      const orgCard = document.querySelector<HTMLElement>(`.org-match[data-match-id="${mid}"]`);
      const pubMatch = document.querySelector<HTMLElement>(`.td-match-anchor[data-match-id="${mid}"]`);

      if (orgCard) {
        orgCard.classList.add('is-open');
        orgCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else if (pubMatch) {
        pubMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
        pubMatch.classList.add('td-match--highlight');
        setTimeout(() => pubMatch.classList.remove('td-match--highlight'), 1500);
      }
    };
    cell.addEventListener('click', handler);
    cell.addEventListener('keydown', (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); } });
  });
}
