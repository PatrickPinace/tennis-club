// Public bracket rendering for SGL tournaments.
// Fetches and renders bracket for all users (not just organizer).
import { escHtml, getApiBase } from './helpers';

(async () => {
  const panel = document.getElementById('org-panel');
  if (!panel) return;
  const tType   = panel.dataset.tournamentType ?? 'RND';
  const tStatus = panel.dataset.tournamentStatus ?? '';
  const apiBase = getApiBase();
  const tid     = panel.dataset.tournamentId;

  if (tType === 'SGL' && tStatus !== 'DRF' && tStatus !== 'REG') {
    const container = document.getElementById('bracket-container');
    if (container) {
      try {
        const res = await fetch(`${apiBase}/api/tournaments/${tid}/bracket/`, { credentials: 'include' });
        if (res.ok) {
          const rounds = await res.json();
          if (!rounds.length) {
            container.innerHTML = '<div style="padding:16px;color:var(--text-dim);font-size:0.85rem;">Brak danych drabinki.</div>';
          } else {
            const cols = rounds.map((r: {round_label:string; matches: Array<{id:number;match_index:number;status:string;is_bye:boolean;is_third_place:boolean;participant1:{display_name:string;id?:number}|null;participant2:{display_name:string;id?:number}|null;winner_id:number|null;score:string|null}>}) => {
              const cards = r.matches.map(m => {
                const p1Name = m.participant1?.display_name ?? (m.is_bye ? 'BYE' : '—');
                const p2Name = m.participant2?.display_name ?? (m.is_bye ? 'BYE' : '—');
                const p1Won  = m.winner_id != null && m.participant1 && (m.winner_id === m.participant1.id);
                const p2Won  = m.winner_id != null && m.participant2 && (m.winner_id === m.participant2.id);
                const score  = m.score ?? (m.status === 'WDR' ? 'WO' : '');
                const isDone = m.status === 'CMP' || m.status === 'WDR';
                const third  = m.is_third_place ? `<span class="bkt-third-label">o 3. miejsce</span>` : '';
                return `<div class="bkt-match${isDone?' bkt-match--done':''}">${third}<div class="bkt-player${p1Won?' bkt-player--winner':''}"><span class="bkt-player-name">${escHtml(p1Name)}</span>${p1Won&&score?`<span class="bkt-score">${escHtml(score)}</span>`:''}</div><div class="bkt-player${p2Won?' bkt-player--winner':''}"><span class="bkt-player-name">${escHtml(p2Name)}</span>${p2Won&&score?`<span class="bkt-score">${escHtml(score)}</span>`:''}</div>${isDone&&!p1Won&&!p2Won&&score?`<div class="bkt-score-neutral">${escHtml(score)}</div>`:''}</div>`;
              }).join('');
              return `<div class="bkt-col"><div class="bkt-col-label">${escHtml(r.round_label)}</div><div class="bkt-col-matches">${cards}</div></div>`;
            }).join('');
            container.innerHTML = `<div class="bkt-wrap">${cols}</div>`;
          }
        }
      } catch { /* cicha degradacja */ }
    }
  }
})();
