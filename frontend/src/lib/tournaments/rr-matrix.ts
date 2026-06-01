// RR Matrix toggle — public view (list ↔ matrix).
// Works for all users, reads SSR JSON data, no auth required.
import { escHtml, abbrev } from './helpers';

(() => {
  const toggle = document.getElementById('matches-view-toggle');
  if (!toggle) return; // nie ma toggle → nie RR lub brak meczów

  const roundEls   = document.querySelectorAll<HTMLElement>('.td-round');
  const matrixWrap = document.getElementById('rr-matrix-wrap');
  if (!matrixWrap) return;

  // Parsuj mecze z SSR
  type PubMatchData = {
    id: number; participant1_id: number | null; participant2_id: number | null;
    participant1_name: string | null; participant2_name: string | null;
    winner_name: string | null; score: string | null; status: string;
  };
  let pubMatches: PubMatchData[] = [];
  const matchesEl = document.getElementById('ssr-matches-data');
  if (matchesEl) {
    try { pubMatches = JSON.parse(matchesEl.textContent ?? '[]'); } catch { /* brak */ }
  }

  // Parsuj uczestników z SSR
  type PubParticipant = { id: number; display_name: string };
  let pubParticipants: PubParticipant[] = [];
  const partEl = document.getElementById('ssr-participants-data');
  if (partEl) {
    try { pubParticipants = JSON.parse(partEl.textContent ?? '[]'); } catch { /* brak */ }
  }

  function buildPublicMatrix() {
    const wrap = document.getElementById('rr-matrix-inner');
    if (!wrap) return;
    if (pubParticipants.length < 2) {
      wrap.innerHTML = '<p style="padding:16px;font-size:0.82rem;color:var(--text-dim);">Za mało uczestników do macierzy.</p>';
      return;
    }
    const matchMap = new Map<string, PubMatchData>();
    for (const m of pubMatches) {
      if (!m.participant1_id || !m.participant2_id) continue;
      const key = `${Math.min(m.participant1_id, m.participant2_id)}_${Math.max(m.participant1_id, m.participant2_id)}`;
      matchMap.set(key, m);
    }
    let html = '<table class="rr-matrix" role="grid">';
    html += '<thead><tr><th class="rr-matrix__row-head rr-matrix__corner"></th>';
    for (const p of pubParticipants) {
      html += `<th class="rr-matrix__col-head" title="${escHtml(p.display_name)}">${escHtml(abbrev(p.display_name))}</th>`;
    }
    html += '</tr></thead><tbody>';
    for (const row of pubParticipants) {
      html += `<tr><td class="rr-matrix__row-head" title="${escHtml(row.display_name)}">${escHtml(row.display_name)}</td>`;
      for (const col of pubParticipants) {
        if (row.id === col.id) { html += '<td class="rr-matrix__diag" aria-hidden="true"></td>'; continue; }
        const key = `${Math.min(row.id, col.id)}_${Math.max(row.id, col.id)}`;
        const m = matchMap.get(key);
        if (!m) {
          html += '<td class="rr-matrix__cell rr-matrix__cell--empty" aria-label="brak meczu"><span class="rr-matrix__cell-dash">—</span></td>';
          continue;
        }
        const rowName = row.id === m.participant1_id ? m.participant1_name : m.participant2_name;
        const colName = row.id === m.participant1_id ? m.participant2_name : m.participant1_name;
        let cls = 'rr-matrix__cell';
        let inner = '';
        let label = '';
        if (m.status === 'CMP') {
          const rowWon = m.winner_name !== null && m.winner_name === rowName;
          const isDraw = m.winner_name === null;
          cls += isDraw ? ' rr-matrix__cell--draw' : rowWon ? ' rr-matrix__cell--win' : ' rr-matrix__cell--loss';
          label = isDraw ? 'remis' : rowWon ? 'wygrana' : 'przegrana';
          const badge = isDraw ? 'R' : rowWon ? 'W' : 'P';
          inner = `<span class="rr-matrix__badge">${badge}</span>`
                + (m.score ? `<span class="rr-matrix__score">${escHtml(m.score).replace(/ /g,' ')}</span>` : '');
        } else if (m.status === 'WDR') {
          const rowWon = m.winner_name === rowName;
          cls += ' rr-matrix__cell--wdr';
          label = rowWon ? 'walkover — wygrana' : 'walkover — przegrana';
          inner = '<span class="rr-matrix__badge">WO</span>';
        } else if (m.status === 'INP') {
          cls += ' rr-matrix__cell--live';
          label = 'w trakcie';
          inner = '<span class="rr-matrix__live-dot">●</span>';
        } else {
          cls += ' rr-matrix__cell--pending';
          label = 'oczekuje';
          inner = '<span class="rr-matrix__cell-dash">·</span>';
        }
        const tooltip = `${escHtml(rowName ?? '')} vs ${escHtml(colName ?? '')}${m.score ? ': ' + m.score : ''}`;
        html += `<td class="${cls}" title="${tooltip}" aria-label="${label}">${inner}</td>`;
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    wrap.innerHTML = html;
  }

  let matrixBuilt = false;
  toggle.querySelectorAll<HTMLButtonElement>('.view-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      toggle.querySelectorAll('.view-toggle__btn').forEach(b => b.classList.remove('view-toggle__btn--active'));
      btn.classList.add('view-toggle__btn--active');
      if (view === 'matrix') {
        roundEls.forEach(el => el.style.display = 'none');
        matrixWrap.style.display = '';
        if (!matrixBuilt) { buildPublicMatrix(); matrixBuilt = true; }
      } else {
        roundEls.forEach(el => el.style.display = '');
        matrixWrap.style.display = 'none';
      }
    });
  });
})();
