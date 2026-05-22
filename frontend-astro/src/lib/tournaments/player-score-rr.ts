// Player score entry — participant enters match scores for RR tournaments.
// Only visible for RR tournaments in ACT or FIN status, for non-organizer participants.
import { getCsrf, escHtml, getApiBase } from './helpers';

(() => {
  const panel = document.getElementById('player-score-panel');
  if (!panel) return;

  const tId   = panel.dataset.tournamentId;
  const tType = panel.dataset.tournamentType;
  if (tType !== 'RND') return;

  const apiBase = getApiBase();

  // Parsuj SSR data
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

  // Pobierz zalogowanego usera
  fetch(`${apiBase}/api/auth/me/`, { credentials: 'include' })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data?.authenticated || !data?.user?.id) return;
      const myId: number = data.user.id;
      const isOrg: boolean = data.user.is_staff || data.user.username === panel.closest('[data-created-by]')?.getAttribute('data-created-by');

      // Organizer widzi już swój panel — nie duplikuj
      if (isOrg) return;

      // Znajdź Participant odpowiadający zalogowanemu userowi
      const myParticipant = participants.find(p => p.user_id === myId);
      if (!myParticipant) return; // user nie jest uczestnikiem turnieju

      // Znajdź mecze, w których ten uczestnik gra
      const myMatches = matches.filter(
        m => m.participant1_id === myParticipant.id || m.participant2_id === myParticipant.id
      );
      if (!myMatches.length) return;

      // Pokaż panel i wypełnij listę
      panel.style.display = '';
      const list = document.getElementById('player-matches-list');
      if (!list) return;

      function spinner(name: string, val: string): string {
        return `<div class="org-score-spinner">
          <button type="button" class="org-spin-btn org-spin-up" tabindex="-1">▲</button>
          <input class="org-set-input" type="number" min="0" max="99"
            name="${name}" placeholder="—" value="${val}">
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

        const wdrSection = (m.participant1_id && m.participant2_id) ? `
          <div class="org-wdr-section">
            <label class="org-wdr-label">
              <input type="checkbox" class="org-wdr-checkbox ps-wdr-cb" data-match-id="${m.id}">
              Walkover — ktoś się wycofuje
            </label>
            <div class="org-wdr-winner" style="display:none;">
              <label style="font-size:0.78rem;color:var(--text-muted);">Kto się wycofuje:</label>
              <select class="org-wdr-select ps-wdr-loser">
                <option value="">— wybierz —</option>
                <option value="${m.participant2_id}">${p1} wycofuje się</option>
                <option value="${m.participant1_id}">${p2} wycofuje się</option>
              </select>
            </div>
          </div>` : '';

        const form = (!isCnc) ? `
          <form class="org-score-form" data-match-id="${m.id}"
            data-p1-id="${m.participant1_id ?? ''}" data-p2-id="${m.participant2_id ?? ''}">
            <div class="org-form-row ps-sets-wrap">
              <div class="org-sets-row">${setsHtml}</div>
            </div>
            ${wdrSection}
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
              <span class="org-match-players">${p1}<span class="vs">vs</span>${p2}</span>
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

      // Toggle collapse kliknięciem w header
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
            ? Math.min(cur + 1, 99)
            : Math.max(cur - 1, 0));
          input.dispatchEvent(new Event('input'));
        });
      });

      // WDR checkbox toggle — chowa sety, pokazuje select "kto się wycofuje"
      list.querySelectorAll<HTMLInputElement>('.ps-wdr-cb').forEach(cb => {
        cb.addEventListener('change', () => {
          const form = cb.closest('form') as HTMLFormElement;
          const wdrWinner = form?.querySelector<HTMLElement>('.org-wdr-winner');
          const setsWrap  = form?.querySelector<HTMLElement>('.ps-sets-wrap');
          if (!wdrWinner || !setsWrap) return;
          if (cb.checked) {
            setsWrap.style.display = 'none';
            wdrWinner.style.display = 'flex';
          } else {
            setsWrap.style.display = '';
            wdrWinner.style.display = 'none';
          }
        });
      });

      // Standings refresh — reuse org-panel function if available, else no-op
      function refreshStandings() {
        const tbody = document.getElementById('org-standings-body');
        if (tbody) {
          // Org panel jest załadowany — odśwież standings przez endpoint
          fetch(`${apiBase}/api/tournaments/${tId}/standings/`, { credentials: 'include' })
            .then(r => r.ok ? r.json() : [])
            .then(rows => {
              if (!rows.length) return;
              tbody.innerHTML = rows.map((r: {position:number;display_name:string;points:string|number;matches_played:number;wins:number;losses:number;win_rate:number|null;sets_won:number;sets_lost:number}) => `
                <tr>
                  <td style="text-align:center;font-weight:700;">${r.position}</td>
                  <td>${escHtml(r.display_name)}</td>
                  <td class="col-num" style="font-weight:700;">${Number(r.points).toFixed(1).replace('.0','')}</td>
                  <td class="col-num">${r.matches_played}</td>
                  <td class="col-num">${r.wins}</td>
                  <td class="col-num">${r.losses}</td>
                  <td class="col-num">${r.win_rate != null ? r.win_rate + '%' : '—'}</td>
                  <td class="col-num">${r.sets_won}:${r.sets_lost}</td>
                </tr>`).join('');
            }).catch(() => {});
        }
      }

      // Podepnij handlery formularzy
      list.querySelectorAll<HTMLFormElement>('.org-score-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const matchId = form.dataset.matchId;
          const btn = form.querySelector<HTMLButtonElement>('.org-save-btn');
          const msg = form.querySelector<HTMLElement>('.org-form-msg');
          if (!btn || !msg || !matchId) return;

          // Sprawdź WDR
          const wdrCb = form.querySelector<HTMLInputElement>('.ps-wdr-cb');
          const isWalkover = wdrCb?.checked ?? false;
          const loserSelect = form.querySelector<HTMLSelectElement>('.ps-wdr-loser');
          const loserId = loserSelect?.value ?? '';

          if (isWalkover && !loserId) {
            msg.textContent = 'Wybierz kto się wycofuje.';
            msg.className = 'org-form-msg org-form-msg--err';
            return;
          }

          // winner = ten który NIE jest loser
          const p1Id = form.dataset.p1Id ? parseInt(form.dataset.p1Id, 10) : null;
          const p2Id = form.dataset.p2Id ? parseInt(form.dataset.p2Id, 10) : null;
          const loserIdInt = loserId ? parseInt(loserId, 10) : null;
          const winnerId = loserIdInt === p1Id ? p2Id : p1Id;

          let body: Record<string, unknown>;
          if (isWalkover) {
            body = { walkover: true, winner_participant_id: winnerId };
          } else {
            const fd = new FormData(form);
            const scoreBody: Record<string, number|null> = {};
            ['set1_p1','set1_p2','set2_p1','set2_p2','set3_p1','set3_p2'].forEach(k => {
              const v = fd.get(k);
              scoreBody[k] = (v !== null && v !== '') ? parseInt(v as string, 10) : null;
            });
            body = scoreBody;
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
              msg.textContent = 'Zapisano!';
              msg.className = 'org-form-msg org-form-msg--ok';
              btn.textContent = 'Koryguj';
              btn.disabled = false;
              // Zaktualizuj lokalny stan meczu
              const idx = myMatches.findIndex(m => m.id === Number(matchId));
              if (idx !== -1) {
                myMatches[idx] = { ...myMatches[idx], status: d.status, score: d.score ?? null };
              }
              refreshStandings();
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

