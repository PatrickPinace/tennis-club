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
              <input class="org-set-input" type="number" min="0" max="99"
                name="set${s}_p1" placeholder="—" value="${v1}">
              <span class="org-set-sep">:</span>
              <input class="org-set-input" type="number" min="0" max="99"
                name="set${s}_p2" placeholder="—" value="${v2}">
            </div>
          </div>`;
        }).join('');

        const stVal = m.scheduled_time
          ? (() => { try { return new Date(m.scheduled_time!).toISOString().slice(0,16); } catch { return ''; } })()
          : '';

        const form = (!isCnc) ? `
          <form class="org-score-form sgl-player-form" data-match-id="${m.id}"
            data-p1-id="${m.participant1_id ?? ''}" data-p2-id="${m.participant2_id ?? ''}">
            <div class="org-form-row">
              <div class="org-sets-row">${setsHtml}</div>
              <div class="org-scheduled-group">
                <div class="org-scheduled-label">Termin</div>
                <input id="st-${m.id}" class="org-datetime-input" type="datetime-local"
                  name="scheduled_time" value="${stVal}">
              </div>
            </div>
            <div class="org-form-actions">
              <button type="submit" class="org-save-btn">${isDone ? 'Koryguj' : 'Zapisz wynik'}</button>
              <span class="org-form-msg" data-match-id="${m.id}"></span>
            </div>
          </form>` : '';

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

        // parse scores
        const sets: Array<{p1: number, p2: number}> = [];
        let p1SetsWon: number | string = 0;
        let p2SetsWon: number | string = 0;
        if (m.set1_p1_score !== null && m.set1_p2_score !== null) sets.push({ p1: m.set1_p1_score, p2: m.set1_p2_score });
        if (m.set2_p1_score !== null && m.set2_p2_score !== null) sets.push({ p1: m.set2_p1_score, p2: m.set2_p2_score });
        if (m.set3_p1_score !== null && m.set3_p2_score !== null) sets.push({ p1: m.set3_p1_score, p2: m.set3_p2_score });

        const isWalkover = m.status === 'WDR';
        const hasScore = sets.length > 0 || isWalkover;

        if (isWalkover) {
          const p1Won = m.winner_name === m.participant1_name;
          p1SetsWon = p1Won ? 'W' : 'L';
          p2SetsWon = p1Won ? 'L' : 'W';
        } else if (hasScore) {
          let w1 = 0, w2 = 0;
          for (const s of sets) {
            if (s.p1 > s.p2) w1++;
            else if (s.p1 < s.p2) w2++;
          }
          p1SetsWon = w1;
          p2SetsWon = w2;
        }

        const p1WonClass = isDone && (m.winner_name ? m.winner_name === m.participant1_name : Number(p1SetsWon) > Number(p2SetsWon)) ? 'fs-match__name--winner' : '';
        const p2WonClass = isDone && (m.winner_name ? m.winner_name === m.participant2_name : Number(p2SetsWon) > Number(p1SetsWon)) ? 'fs-match__name--winner' : '';

        let resultCls = '';
        if (isCnc) {
          resultCls = 'td-match--result-cnc';
        } else if (isDone) {
          const myId = myParticipant.id;
          const p1Won = m.winner_name ? m.winner_name === m.participant1_name : Number(p1SetsWon) > Number(p2SetsWon);
          const p2Won = m.winner_name ? m.winner_name === m.participant2_name : Number(p2SetsWon) > Number(p1SetsWon);
          const iWon = (p1Won && m.participant1_id === myId) || (p2Won && m.participant2_id === myId);
          resultCls = iWon ? 'td-match--result-won' : 'td-match--result-lost';
        } else {
          resultCls = m.status === 'INP' ? '' : 'td-match--result-pending';
        }

        const cardCls = [
          'org-match',
          'td-match',
          'td-match--flashscore',
          isDone ? 'org-match--done td-match--done' : '',
          isCnc  ? 'org-match--cancelled' : '',
          resultCls,
        ].filter(Boolean).join(' ');

        const scores1Html = hasScore
          ? `<span class="fs-match__score-overall">${p1SetsWon}</span>` +
            sets.map(s => `<span class="fs-match__score-set ${s.p1 > s.p2 && isDone ? 'fs-match__score-set--won' : ''}">${s.p1}</span>`).join('')
          : `<span class="fs-match__status">${statusBadge}</span>`;

        const scores2Html = hasScore
          ? `<span class="fs-match__score-overall">${p2SetsWon}</span>` +
            sets.map(s => `<span class="fs-match__score-set ${s.p2 > s.p1 && isDone ? 'fs-match__score-set--won' : ''}">${s.p2}</span>`).join('')
          : `<span class="fs-match__status" style="visibility: hidden;">${statusBadge}</span>`;

        const timeChip = m.scheduled_time
          ? (() => { try {
              const d = new Date(m.scheduled_time!);
              return `<span class="org-match-time">${d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})}</span>`;
            } catch { return ''; } })()
          : '';

        return `<div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
          <div class="org-match-header org-match-header--flashscore">
            <div class="fs-match-wrapper">
              <div class="fs-match-meta-col">
                ${roundLabel ? `<span class="fs-match-round-lbl">${roundLabel}</span>` : ''}
                ${timeChip}
              </div>
              <div class="fs-match">
                <div class="fs-match__row">
                  <span class="fs-match__name ${p1WonClass}">${p1}</span>
                  <div class="fs-match__scores">${scores1Html}</div>
                </div>
                <div class="fs-match__row">
                  <span class="fs-match__name ${p2WonClass}">${p2}</span>
                  <div class="fs-match__scores">${scores2Html}</div>
                </div>
              </div>
            </div>
            ${!isCnc ? `<span class="org-match-chevron">▼</span>` : ''}
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

      // Submit formularza
      list.querySelectorAll<HTMLFormElement>('.sgl-player-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const matchId = form.dataset.matchId;
          const btn = form.querySelector<HTMLButtonElement>('.org-save-btn');
          const msg = form.querySelector<HTMLElement>('.org-form-msg');
          if (!btn || !msg || !matchId) return;

          // Disable natychmiast — blokuje podwójne kliknięcie
          btn.disabled = true;

          const fd = new FormData(form);
          const scoreBody: Record<string, number|null> = {};
          ['set1_p1','set1_p2','set2_p1','set2_p2','set3_p1','set3_p2'].forEach(k => {
            const v = fd.get(k);
            scoreBody[k] = (v !== null && v !== '') ? parseInt(v as string, 10) : null;
          });

          const stInput = form.elements.namedItem('scheduled_time') as HTMLInputElement | null;
          let scheduledTimeVal = stInput ? (stInput.value || null) : undefined;
          if (stInput && !scheduledTimeVal) {
            const tzoffset = (new Date()).getTimezoneOffset() * 60000;
            scheduledTimeVal = (new Date(Date.now() - tzoffset)).toISOString().slice(0, 16);
          }

          const body = {
            ...scoreBody,
            ...(scheduledTimeVal !== undefined ? { scheduled_time: scheduledTimeVal } : {}),
          };

          const reject = (text: string) => {
            msg.textContent = text;
            msg.className = 'org-form-msg org-form-msg--err';
            btn.disabled = false;
          };

          // Walidacja: set 1 wymagany
          if (body.set1_p1 === null || body.set1_p2 === null) {
            return reject('Set 1 jest wymagany.');
          }

          // Walidacja tenisowa — taka sama jak w org-matches.ts
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

          const sets: Array<[number, number, number]> = [[body.set1_p1!, body.set1_p2!, 1]];
          if (body.set2_p1 !== null && body.set2_p2 !== null) sets.push([body.set2_p1, body.set2_p2, 2]);
          else if (body.set2_p1 !== null || body.set2_p2 !== null) return reject('Set 2: wpisz wynik dla obu stron.');
          if (body.set3_p1 !== null && body.set3_p2 !== null) sets.push([body.set3_p1, body.set3_p2, 3]);
          else if (body.set3_p1 !== null || body.set3_p2 !== null) return reject('Set 3: wpisz wynik dla obu stron.');
          for (const [a, b, n] of sets) {
            const err = checkSet(a, b, n);
            if (err) return reject(err);
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
