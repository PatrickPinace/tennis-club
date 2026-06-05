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
    round_number?: number; match_index?: number; bracket_type?: string;
    scheduled_time?: string | null;
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

      function renderMatchCard(m: PMatch): string {
        // Gracz zawsze po lewej — jeśli user jest participant2, swap stron wizualnie.
        // Wartości inputów setów też zamieniamy (set_p1/set_p2 w formularzu = lewa/prawa strona),
        // ale name atrybuty pozostają oryginalne bo payload do API zawsze idzie p1/p2 wg backendu.
        const iAmP2 = m.participant2_id === myParticipant!.id;
        const leftName  = iAmP2 ? m.participant2_name : m.participant1_name;
        const rightName = iAmP2 ? m.participant1_name : m.participant2_name;
        const leftId    = iAmP2 ? m.participant2_id   : m.participant1_id;
        const rightId   = iAmP2 ? m.participant1_id   : m.participant2_id;

        const p1 = escHtml(leftName  ?? '—');
        const p2 = escHtml(rightName ?? '—');
        const isDone = m.status === 'CMP' || m.status === 'WDR';
        const isCnc  = m.status === 'CNC';
        const v = (n: number|null) => n !== null ? String(n) : '';

        const scoreChip = m.score
          ? `<span class="org-match-score org-match-score--done">${escHtml(m.score)}</span>`
          : isCnc ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">Anulowany</span>`
          : isDone ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">WO</span>`
          : '';

        // Inputy setów: gdy user jest p2, lewy input (set_p1 w formularzu) = wynik p2 z backendu.
        // name atrybuty: lewy input = set${s}_p1 gdy nie swap, set${s}_p2 gdy swap — API czyta
        // set1_p1 jako wynik participant1, set1_p2 jako wynik participant2 i tak zostaje.
        const setsHtml = [1,2,3].map(s => {
          const origL = v(s===1?m.set1_p1_score:s===2?m.set2_p1_score:m.set3_p1_score);
          const origR = v(s===1?m.set1_p2_score:s===2?m.set2_p2_score:m.set3_p2_score);
          const [dispL, dispR] = iAmP2 ? [origR, origL] : [origL, origR];
          const [nameL, nameR] = iAmP2 ? [`set${s}_p2`, `set${s}_p1`] : [`set${s}_p1`, `set${s}_p2`];
          return `<div class="org-set-group">
            <div class="org-set-label">Set ${s}</div>
            <div class="org-set-inputs">
              <input class="org-set-input" type="number" min="0" max="99"
                name="${nameL}" placeholder="—" value="${dispL}">
              <span class="org-set-sep">:</span>
              <input class="org-set-input" type="number" min="0" max="99"
                name="${nameR}" placeholder="—" value="${dispR}">
            </div>
          </div>`;
        }).join('');

        const wdrSection = (leftId && rightId) ? `
          <div class="org-wdr-section">
            <label class="org-wdr-label">
              <input type="checkbox" class="org-wdr-checkbox ps-wdr-cb" data-match-id="${m.id}">
              <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style="color:var(--danger,#ef4444);opacity:0.7;"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
              Walkover (<abbr title="Walkover — zwycięstwo bez gry, gdy przeciwnik się wycofuje lub nie stawi">WDR</abbr>)
            </label>
            <div class="org-wdr-winner" style="display:none;">
              <label style="font-size:0.78rem;color:var(--text-muted);">Kto się wycofuje:</label>
              <select class="org-wdr-select ps-wdr-loser">
                <option value="">— wybierz —</option>
                <option value="${rightId}">${p1} wycofuje się</option>
                <option value="${leftId}">${p2} wycofuje się</option>
              </select>
            </div>
          </div>` : '';

        const stVal = m.scheduled_time
          ? (() => { try { return new Date(m.scheduled_time!).toISOString().slice(0,16); } catch { return ''; } })()
          : '';

        const form = (!isCnc) ? `
          <form class="org-score-form" data-match-id="${m.id}"
            data-p1-id="${m.participant1_id ?? ''}" data-p2-id="${m.participant2_id ?? ''}">
            <div class="org-form-row ps-sets-wrap">
              <div class="org-sets-row">${setsHtml}</div>
              <div class="org-scheduled-group">
                <div class="org-scheduled-label">Termin</div>
                <input id="st-${m.id}" class="org-datetime-input" type="datetime-local"
                  name="scheduled_time" value="${stVal}">
              </div>
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

        const bracketPrefix = m.bracket_type === 'L' ? 'L-' : m.bracket_type === 'GF' ? 'GF ' : '';
        const roundLabel = m.bracket_type === 'GF'
          ? `GF M${m.match_index}`
          : m.round_number != null && m.match_index != null
            ? `${bracketPrefix}R${m.round_number} M${m.match_index}`
            : '';

        const statusBadge = m.status === 'CMP'
          ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">Zakończony</span>`
          : m.status === 'WDR'
            ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">Walkower</span>`
            : m.status === 'CNC'
              ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">Odwołany</span>`
              : m.status === 'INP'
                ? `<span class="tc-badge tc-badge-warning" style="font-size:0.68rem;">W trakcie</span>`
                : m.status === 'SCH'
                  ? `<span class="tc-badge tc-badge-info" style="font-size:0.68rem;">Zaplanowany</span>`
                  : `<span class="tc-badge" style="font-size:0.68rem;background:var(--surface-2);color:var(--text-dim);">Oczekuje</span>`;

        return `<div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
          <div class="org-match-header">
            <div class="org-match-meta">
              ${roundLabel ? `
              <div class="org-match-meta-top">
                <span class="org-match-label">${roundLabel}</span>
                <span class="org-status-mobile">${statusBadge}</span>
              </div>` : ''}
              <span class="org-match-players">${p1} <span class="vs">vs</span> ${p2}</span>
            </div>
            <div class="org-match-right">
              ${scoreChip}<span class="org-status-desktop">${statusBadge}</span>
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

      // Walidacja tenisowa seta — identyczna z org-matches.ts i player-score-sgl.ts
      const checkSet = (a: number, b: number, n: number): string | null => {
        if (a < 0 || b < 0) return `Set ${n}: wynik nie może być ujemny.`;
        const hi = Math.max(a, b), lo = Math.min(a, b);
        if (hi >= 10) {
          if (hi > 20) return `Set ${n}: super tie-break nie może mieć więcej niż 20 punktów (${a}:${b}).`;
          if (hi - lo < 2) return `Set ${n}: super tie-break wymaga przewagi ≥ 2 punktów (${a}:${b}).`;
          if (hi > 10 && lo !== hi - 2) return `Set ${n}: po 10:10 gra trwa do różnicy 2 punktów — ${a}:${b} jest niemożliwe.`;
          return null;
        }
        if (hi < 6) return `Set ${n}: zwycięzca musi mieć co najmniej 6 gemów.`;
        if (hi === 6 && lo <= 4) return null;
        if (hi === 7 && (lo === 5 || lo === 6)) return null;
        return `Set ${n}: wynik ${a}:${b} jest niemożliwy w standardowym secie tenisowym.`;
      };

      // Podepnij handlery formularzy
      list.querySelectorAll<HTMLFormElement>('.org-score-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const matchId = form.dataset.matchId;
          const btn = form.querySelector<HTMLButtonElement>('.org-save-btn');
          const msg = form.querySelector<HTMLElement>('.org-form-msg');
          if (!btn || !msg || !matchId) return;

          // Disable natychmiast — blokuje podwójne kliknięcie
          btn.disabled = true;

          const reject = (text: string) => {
            msg.textContent = text;
            msg.className = 'org-form-msg org-form-msg--err';
            btn.disabled = false;
          };

          // Sprawdź WDR
          const wdrCb = form.querySelector<HTMLInputElement>('.ps-wdr-cb');
          const isWalkover = wdrCb?.checked ?? false;
          const loserSelect = form.querySelector<HTMLSelectElement>('.ps-wdr-loser');
          const loserId = loserSelect?.value ?? '';

          if (isWalkover && !loserId) {
            return reject('Wybierz kto się wycofuje.');
          }

          // winner = ten który NIE jest loser
          const p1Id = form.dataset.p1Id ? parseInt(form.dataset.p1Id, 10) : null;
          const p2Id = form.dataset.p2Id ? parseInt(form.dataset.p2Id, 10) : null;
          const loserIdInt = loserId ? parseInt(loserId, 10) : null;
          const winnerId = loserIdInt === p1Id ? p2Id : p1Id;

          const stInput = form.elements.namedItem('scheduled_time') as HTMLInputElement | null;
          const scheduledTimeVal = stInput ? (stInput.value || null) : undefined;

          let body: Record<string, unknown>;
          if (isWalkover) {
            body = { walkover: true, winner_participant_id: winnerId };
            if (scheduledTimeVal !== undefined) body.scheduled_time = scheduledTimeVal;
          } else {
            const fd = new FormData(form);
            const scoreBody: Record<string, number|null> = {};
            ['set1_p1','set1_p2','set2_p1','set2_p2','set3_p1','set3_p2'].forEach(k => {
              const v = fd.get(k);
              scoreBody[k] = (v !== null && v !== '') ? parseInt(v as string, 10) : null;
            });

            // Walidacja tenisowa setów
            if (scoreBody.set1_p1 === null || scoreBody.set1_p2 === null) {
              return reject('Set 1 jest wymagany.');
            }
            const sets: Array<[number, number, number]> = [[scoreBody.set1_p1!, scoreBody.set1_p2!, 1]];
            if (scoreBody.set2_p1 !== null && scoreBody.set2_p2 !== null) sets.push([scoreBody.set2_p1, scoreBody.set2_p2, 2]);
            else if (scoreBody.set2_p1 !== null || scoreBody.set2_p2 !== null) return reject('Set 2: wpisz wynik dla obu stron.');
            if (scoreBody.set3_p1 !== null && scoreBody.set3_p2 !== null) sets.push([scoreBody.set3_p1, scoreBody.set3_p2, 3]);
            else if (scoreBody.set3_p1 !== null || scoreBody.set3_p2 !== null) return reject('Set 3: wpisz wynik dla obu stron.');
            for (const [a, b, n] of sets) {
              const err = checkSet(a, b, n);
              if (err) return reject(err);
            }

            body = scoreBody;
            if (scheduledTimeVal !== undefined) body.scheduled_time = scheduledTimeVal;
          }

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

