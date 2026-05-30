// Player score entry — participant enters match scores for SGL / DBE tournaments.
// Self-reported flow, trust-first: zapis od razu jako CMP.
// Uczestnik nie może CNC ani WDR — tylko zwykły wynik setów.
import { getCsrf, escHtml, getApiBase } from './helpers';

(() => {
  const panel = document.getElementById('sgl-player-score-panel');
  if (!panel) return;

  const tId   = panel.dataset.tournamentId;
  const tType = panel.dataset.tournamentType;
  if (tType !== 'SGL' && tType !== 'DBE') return;

  const apiBase = getApiBase();

  type PMatch = {
    id: number; status: string;
    participant1_id: number | null; participant2_id: number | null;
    participant1_name: string | null; participant2_name: string | null;
    score: string | null;
    set1_p1_score: number|null; set1_p2_score: number|null;
    set2_p1_score: number|null; set2_p2_score: number|null;
    set3_p1_score: number|null; set3_p2_score: number|null;
  };
  type PPart = { id: number; user_id: number | null };

  let matches: PMatch[] = [];
  let participants: PPart[] = [];
  try {
    const me = document.getElementById('ssr-matches-data');
    if (me) matches = JSON.parse(me.textContent ?? '[]');
    const pe = document.getElementById('ssr-participants-data');
    if (pe) participants = JSON.parse(pe.textContent ?? '[]');
  } catch { return; }

  fetch(`${apiBase}/api/auth/me/`, { credentials: 'include' })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data?.authenticated || !data?.user?.id) return;
      const myId: number = data.user.id;
      const createdBy = panel.closest('[data-created-by]')?.getAttribute('data-created-by');
      const isOrg: boolean = data.user.is_staff || data.user.username === createdBy;

      // Organizer ma swój panel — nie duplikuj
      if (isOrg) return;

      // Znajdź uczestnika odpowiadającego zalogowanemu userowi
      const myParticipant = participants.find(p => p.user_id === myId);
      if (!myParticipant) return;

      // Tylko mecze bezpośrednie (p1 lub p2), nie BYE
      const myMatches = matches.filter(
        m => (m.participant1_id === myParticipant.id || m.participant2_id === myParticipant.id)
          && m.participant1_id !== null && m.participant2_id !== null,
      );
      if (!myMatches.length) return;

      panel.style.display = '';
      const list = document.getElementById('sgl-player-matches-list');
      if (!list) return;

      function spinner(name: string, val: string): string {
        return `<div class="org-score-spinner">
          <button type="button" class="org-spin-btn org-spin-up" tabindex="-1">▲</button>
          <input class="org-set-input" type="number" min="0" max="99"
            name="${name}" placeholder="—" value="${escHtml(val)}">
          <button type="button" class="org-spin-btn org-spin-down" tabindex="-1">▼</button>
        </div>`;
      }

      function renderMatchCard(m: PMatch): string {
        const p1 = escHtml(m.participant1_name ?? '—');
        const p2 = escHtml(m.participant2_name ?? '—');
        const isDone = m.status === 'CMP' || m.status === 'WDR';
        const isCnc  = m.status === 'CNC';
        const v = (n: number|null) => n !== null ? String(n) : '';

        const scoreChip = m.score
          ? `<span class="org-match-score org-match-score--done">${escHtml(m.score)}</span>`
          : isCnc ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">Anulowany</span>`
          : isDone ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">WO</span>`
          : '';

        const setsHtml = [1,2,3].map(s => {
          const v1 = v(s===1?m.set1_p1_score:s===2?m.set2_p1_score:m.set3_p1_score);
          const v2 = v(s===1?m.set1_p2_score:s===2?m.set2_p2_score:m.set3_p2_score);
          return `<div class="org-set-group">
            <div class="org-set-label">Set ${s}</div>
            <div class="org-set-inputs">
              ${spinner(`set${s}_p1`, v1)}
              <span class="org-set-sep">:</span>
              ${spinner(`set${s}_p2`, v2)}
            </div>
          </div>`;
        }).join('');

        const form = (!isCnc) ? `
          <form class="org-score-form sgl-player-form" data-match-id="${m.id}"
            data-p1-id="${m.participant1_id ?? ''}" data-p2-id="${m.participant2_id ?? ''}">
            <div class="org-form-row">
              <div class="org-sets-row">${setsHtml}</div>
            </div>
            <div class="org-form-actions">
              <button type="submit" class="org-save-btn">${isDone ? 'Koryguj' : 'Zapisz wynik'}</button>
              <span class="org-form-msg" data-match-id="${m.id}"></span>
            </div>
          </form>` : '';

        const cardCls = [
          'org-match',
          isDone ? 'org-match--done' : '',
          isCnc  ? 'org-match--cancelled' : '',
          (!isDone && !isCnc) ? 'org-match--pending' : '',
        ].filter(Boolean).join(' ');

        return `<div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
          <div class="org-match-header">
            <div class="org-match-meta">
              <span class="org-match-players">${p1} <span class="vs">vs</span> ${p2}</span>
            </div>
            <div class="org-match-right">
              ${scoreChip}
              ${!isCnc ? `<span class="org-match-chevron">▼</span>` : ''}
            </div>
          </div>
          ${form}
        </div>`;
      }

      list.innerHTML = myMatches.map(renderMatchCard).join('');

      // Toggle collapse
      list.querySelectorAll<HTMLElement>('.org-match-header').forEach(header => {
        header.addEventListener('click', () => {
          const card = header.closest<HTMLElement>('.org-match');
          if (!card || card.dataset.status === 'CNC') return;
          card.classList.toggle('is-open');
        });
      });

      // Spinnery ▲/▼
      list.querySelectorAll<HTMLButtonElement>('.org-spin-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const input = btn.closest('.org-score-spinner')?.querySelector<HTMLInputElement>('.org-set-input');
          if (!input) return;
          const cur = input.value === '' ? 0 : parseInt(input.value, 10);
          input.value = String(btn.classList.contains('org-spin-up')
            ? Math.min(cur + 1, 99) : Math.max(cur - 1, 0));
        });
      });

      // Submit formularza
      list.querySelectorAll<HTMLFormElement>('.sgl-player-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const matchId = form.dataset.matchId;
          const btn = form.querySelector<HTMLButtonElement>('.org-save-btn');
          const msg = form.querySelector<HTMLElement>('.org-form-msg');
          if (!btn || !msg || !matchId) return;

          const fd = new FormData(form);
          const body: Record<string, number|null> = {};
          ['set1_p1','set1_p2','set2_p1','set2_p2','set3_p1','set3_p2'].forEach(k => {
            const v = fd.get(k);
            body[k] = (v !== null && v !== '') ? parseInt(v as string, 10) : null;
          });

          // Walidacja: set 1 wymagany
          if (body.set1_p1 === null || body.set1_p2 === null) {
            msg.textContent = 'Set 1 jest wymagany.';
            msg.className = 'org-form-msg org-form-msg--err';
            return;
          }

          btn.disabled = true;
          btn.textContent = 'Zapisuję…';
          msg.textContent = '';
          msg.className = 'org-form-msg';

          try {
            const res = await fetch(`${apiBase}/api/tournaments/${tId}/matches/${matchId}/score/`, {
              method: 'PATCH',
              credentials: 'include',
              headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
              body: JSON.stringify(body),
            });
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
              msg.textContent = d.winner_name ? `Zapisano! Wygrał: ${d.winner_name}` : 'Zapisano wynik.';
              msg.className = 'org-form-msg org-form-msg--ok';
              btn.textContent = 'Koryguj';
              btn.disabled = false;
              // Odśwież bracket po zapisie wyniku
              const bracketContainer = document.getElementById('bracket-container');
              if (bracketContainer) {
                import('./org-bracket').then(({ renderBracket }) => {
                  fetch(`${apiBase}/api/tournaments/${tId}/bracket/`, { credentials: 'include' })
                    .then(r => r.ok ? r.json() : null)
                    .then(data => { if (data) renderBracket(data); })
                    .catch(() => {});
                }).catch(() => {});
              }
            } else {
              msg.textContent = d.detail ?? d.error ?? `Błąd ${res.status}`;
              msg.className = 'org-form-msg org-form-msg--err';
              btn.disabled = false;
              btn.textContent = 'Zapisz wynik';
            }
          } catch {
            msg.textContent = 'Błąd połączenia.';
            msg.className = 'org-form-msg org-form-msg--err';
            btn.disabled = false;
            btn.textContent = 'Zapisz wynik';
          }
        });
      });
    })
    .catch(() => {});
})();
