// Player score entry — participant enters match scores for AMR tournaments.
// Only visible for AMR tournaments in ACT or FIN status, for non-organizer participants.
import { getCsrf, escHtml, getApiBase } from './helpers';

(() => {
  const panel = document.getElementById('amr-player-score-panel');
  if (!panel) return;

  const tId            = panel.dataset.tournamentId;
  const tType          = panel.dataset.tournamentType;
  const pointsPerMatch = parseInt(panel.dataset.pointsPerMatch ?? '32', 10);
  if (tType !== 'AMR') return;

  const apiBase = getApiBase();

  type AMatch = {
    id: number; status: string;
    participant1_id: number|null; participant2_id: number|null;
    participant3_id: number|null; participant4_id: number|null;
    participant1_name: string|null; participant2_name: string|null;
    participant3_name: string|null; participant4_name: string|null;
    score: string|null;
    set1_p1_score: number|null; set1_p2_score: number|null;
    winner_name?: string | null;
    scheduled_time?: string | null;
  };
  type APart = { id: number; user_id: number|null };

  let matches: AMatch[] = [];
  let participants: APart[] = [];
  try {
    const me = document.getElementById('amr-ssr-matches-data');
    if (me) matches = JSON.parse(me.textContent ?? '[]');
    const pe = document.getElementById('amr-ssr-participants-data');
    if (pe) participants = JSON.parse(pe.textContent ?? '[]');
  } catch { return; }

  fetch(`${apiBase}/api/auth/me/`, { credentials: 'include' })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data?.authenticated || !data?.user?.id) return;
      const myId: number = data.user.id;
      const isOrg = data.user.is_staff ||
        data.user.username === panel.closest('[data-created-by]')?.getAttribute('data-created-by');
      if (isOrg) return;

      const myParticipant = participants.find(p => p.user_id === myId);
      if (!myParticipant) return;

      const myMatches = matches.filter(
        m => m.participant1_id === myParticipant.id
          || m.participant2_id === myParticipant.id
          || m.participant3_id === myParticipant.id
          || m.participant4_id === myParticipant.id
      );
      if (!myMatches.length) return;

      panel.style.display = '';
      const list = document.getElementById('amr-player-matches-list');
      if (!list) return;

      function renderCard(m: AMatch): string {
        const isDoubles = m.participant3_id != null || m.participant4_id != null;
        // AMR debel: Team A = p1+p4, Team B = p2+p3
        const p1 = isDoubles
          ? escHtml(`${m.participant1_name ?? '—'} / ${m.participant4_name ?? '—'}`)
          : escHtml(m.participant1_name ?? '—');
        const p2 = isDoubles
          ? escHtml(`${m.participant2_name ?? '—'} / ${m.participant3_name ?? '—'}`)
          : escHtml(m.participant2_name ?? '—');
        const isDone = m.status === 'CMP' || m.status === 'WDR';
        const isCnc  = m.status === 'CNC';
        const isWalkover = m.status === 'WDR';
        const v1 = m.set1_p1_score != null ? String(m.set1_p1_score) : '';
        const v2 = m.set1_p2_score != null ? String(m.set1_p2_score) : '';

        const scoreChip = m.score
          ? `<span class="org-match-score org-match-score--done">${escHtml(m.score)}</span>`
          : isCnc ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">Anulowany</span>`
          : isDone ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">WO</span>`
          : '';

        const stVal = m.scheduled_time
          ? (() => { try { return new Date(m.scheduled_time!).toISOString().slice(0,16); } catch { return ''; } })()
          : '';

        const formatNameShort = (fullName: string | null | undefined): string => {
          if (!fullName) return '';
          const parts = fullName.trim().split(/\s+/);
          if (parts.length < 2) return fullName;
          return `${parts[0]} ${parts[parts.length - 1].charAt(0)}.`;
        };

        const p1Short = isDoubles
          ? escHtml(`${formatNameShort(m.participant1_name)} / ${formatNameShort(m.participant4_name)}`)
          : escHtml(formatNameShort(m.participant1_name));
        const p2Short = isDoubles
          ? escHtml(`${formatNameShort(m.participant2_name)} / ${formatNameShort(m.participant3_name)}`)
          : escHtml(formatNameShort(m.participant2_name));

        const setsHtml = `
          <div style="width: 100%;">
            <div class="amr-scoreboard-grid" style="background: var(--tc-chip-bg); border: 1px solid var(--tc-card-border); border-radius: 8px; overflow: hidden; margin-bottom: 6px; display: grid; grid-template-columns: 1fr 80px; align-items: center; width: 100%;">
              <div style="padding: 10px 14px; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Gracz</div>
              <div style="text-align: center; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Punkty</div>
              
              <div style="padding: 10px 14px; font-size: 0.88rem; font-weight: 600; color: var(--tc-ink); border-top: 1px solid var(--tc-card-border-soft); text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <span class="player-name-full">${p1}</span>
                <span class="player-name-short">${p1Short}</span>
              </div>
              <div style="padding: 6px; display: flex; justify-content: center; border-top: 1px solid var(--tc-card-border-soft);">
                <input class="org-set-input" type="number" min="0" max="${pointsPerMatch}"
                  name="set1_p1" placeholder="—" value="${v1}"
                  style="width: 48px; height: 32px; text-align: center; background: var(--tc-card-bg); border: 1px solid var(--tc-card-border); border-radius: 4px; color: var(--tc-ink); font-weight: 600;">
              </div>

              <div style="padding: 10px 14px; font-size: 0.88rem; font-weight: 600; color: var(--tc-ink); border-top: 1px solid var(--tc-card-border-soft); text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <span class="player-name-full">${p2}</span>
                <span class="player-name-short">${p2Short}</span>
              </div>
              <div style="padding: 6px; display: flex; justify-content: center; border-top: 1px solid var(--tc-card-border-soft);">
                <input class="org-set-input" type="number" min="0" max="${pointsPerMatch}"
                  name="set1_p2" placeholder="—" value="${v2}"
                  style="width: 48px; height: 32px; text-align: center; background: var(--tc-card-bg); border: 1px solid var(--tc-card-border); border-radius: 4px; color: var(--tc-ink); font-weight: 600;">
              </div>
            </div>
            <div style="font-size:0.72rem;color:var(--tc-muted);margin-bottom:8px;margin-left:2px;">
              * Suma musi wynosić ${pointsPerMatch} punktów
            </div>
          </div>`;

        const wdrSection = (m.participant1_id && m.participant2_id) ? `
          <div class="org-wdr-section">
            <label class="org-wdr-label">
              <input type="checkbox" class="org-wdr-checkbox ps-wdr-cb" data-match-id="${m.id}" ${isWalkover ? 'checked' : ''}>
              <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style="color:var(--danger,#ef4444);opacity:0.7;"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
              Walkover (<abbr title="Walkover — zwycięstwo bez gry, gdy przeciwnik się wycofuje lub nie stawi">WDR</abbr>)
            </label>
            <div class="org-wdr-winner" style="${isWalkover ? 'display:flex;' : 'display:none;'}">
              <label style="font-size:0.78rem;color:var(--tc-muted);font-weight:600;">Zwycięzca:</label>
              <select name="winner_participant_id" class="org-wdr-select ps-wdr-winner-select">
                <option value="">— wybierz zwycięzcę —</option>
                <option value="${m.participant1_id}" ${m.winner_name === m.participant1_name || (isDoubles && m.winner_name === `${m.participant1_name ?? ''} / ${m.participant4_name ?? ''}`) ? 'selected' : ''}>${p1}</option>
                <option value="${m.participant2_id}" ${m.winner_name === m.participant2_name || (isDoubles && m.winner_name === `${m.participant2_name ?? ''} / ${m.participant3_name ?? ''}`) ? 'selected' : ''}>${p2}</option>
              </select>
            </div>
          </div>` : '';

        const form = (!isCnc) ? `
          <form class="org-score-form amr-ps-form" data-match-id="${m.id}">
            <div class="org-form-row" style="width: 100%;">
              ${setsHtml}
              <div class="org-scheduled-group" style="width: 100%;">
                <div class="org-scheduled-label">Termin</div>
                <input id="st-${m.id}" class="org-datetime-input" type="datetime-local"
                  name="scheduled_time" value="${stVal}" style="width: 100%; box-sizing: border-box;">
              </div>
            </div>
            ${wdrSection}
            <div class="org-form-actions" style="display: flex; justify-content: flex-end; align-items: center; width: 100%;">
              <span class="org-form-msg" data-match-id="${m.id}" style="margin-right: 10px;"></span>
              <button type="submit" class="org-save-btn">${isDone ? 'Koryguj' : 'Zapisz wynik'}</button>
            </div>
          </form>` : '';

        const roundLabel = ''; // AMR matches list does not define round in simple layout, but we can keep structure consistent

        const MATCH_STATUS_LABEL: Record<string, string> = {
          WAI: 'Oczekuje', SCH: 'Zaplanowany', INP: 'W trakcie',
          CMP: 'Zakończony', WDR: 'Walkower', CNC: 'Odwołany',
        };
        const statusBadge = m.status === 'INP' ? '● Live' : MATCH_STATUS_LABEL[m.status] ?? m.status;

        // parse scores
        const sets: Array<{p1: number, p2: number}> = [];
        let p1SetsWon: number | string = 0;
        let p2SetsWon: number | string = 0;
        if (m.set1_p1_score !== null && m.set1_p2_score !== null) sets.push({ p1: m.set1_p1_score, p2: m.set1_p2_score });

        const hasScore = sets.length > 0 || isWalkover;

        if (isWalkover) {
          const p1Won = m.winner_name === m.participant1_name || (isDoubles && m.winner_name === `${m.participant1_name ?? ''} / ${m.participant4_name ?? ''}`);
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

        const p1WonClass = isDone && (m.winner_name ? (m.winner_name === m.participant1_name || m.winner_name === p1) : Number(p1SetsWon) > Number(p2SetsWon)) ? 'fs-match__name--winner' : '';
        const p2WonClass = isDone && (m.winner_name ? (m.winner_name === m.participant2_name || m.winner_name === p2) : Number(p2SetsWon) > Number(p1SetsWon)) ? 'fs-match__name--winner' : '';

        let resultCls = '';
        if (isCnc) {
          resultCls = 'td-match--result-cnc';
        } else if (isDone) {
          const myId = myParticipant!.id;
          const p1Won = m.winner_name ? (m.winner_name === m.participant1_name || m.winner_name === p1) : Number(p1SetsWon) > Number(p2SetsWon);
          const p2Won = m.winner_name ? (m.winner_name === m.participant2_name || m.winner_name === p2) : Number(p2SetsWon) > Number(p1SetsWon);
          const myTeamWon = (p1Won && (m.participant1_id === myId || m.participant4_id === myId)) ||
                             (p2Won && (m.participant2_id === myId || m.participant3_id === myId));
          const myTeamLost = (p1Won && (m.participant2_id === myId || m.participant3_id === myId)) ||
                              (p2Won && (m.participant1_id === myId || m.participant4_id === myId));
          resultCls = myTeamWon ? 'td-match--result-won' : (myTeamLost ? 'td-match--result-lost' : '');
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
          ? sets.map(s => {
              const colorStyle = s.p1 > s.p2 && isDone ? 'color: var(--tc-win, #22c55e); font-weight: 700;' : (s.p1 < s.p2 && isDone ? 'color: var(--tc-hot, #ef4444);' : 'color: var(--tc-ink);');
              return `<span class="fs-match__score-set" style="${colorStyle}">${s.p1}</span>`;
            }).join('')
          : `<span class="fs-match__status">${statusBadge}</span>`;

        const scores2Html = hasScore
          ? sets.map(s => {
              const colorStyle = s.p2 > s.p1 && isDone ? 'color: var(--tc-win, #22c55e); font-weight: 700;' : (s.p2 < s.p1 && isDone ? 'color: var(--tc-hot, #ef4444);' : 'color: var(--tc-ink);');
              return `<span class="fs-match__score-set" style="${colorStyle}">${s.p2}</span>`;
            }).join('')
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

      list.innerHTML = myMatches.map(renderCard).join('');

      // Toggle collapse
      list.querySelectorAll<HTMLElement>('.org-match-header').forEach(header => {
        header.addEventListener('click', () => {
          const card = header.closest<HTMLElement>('.org-match');
          if (!card || card.dataset.status === 'CNC') return;
          card.classList.toggle('is-open');
        });
      });

      // Odśwież standings AMR po zapisie — z detalu turnieju (endpoint /standings/ jest tylko dla RND)
      function refreshAmrStandings() {
        fetch(`${apiBase}/api/tournaments/${tId}/`, { credentials: 'include' })
          .then(r => r.ok ? r.json() : null)
          .then(data => {
            const rows: {display_name:string;points:string|number;matches_played:number}[] = data?.standings ?? [];
            const tbody = document.getElementById('amr-standings-body');
            if (!tbody || !rows.length) return;
            tbody.innerHTML = rows.map((r, idx) => `
              <tr>
                <td><span class="rank-pos${idx < 3 ? ` rank-pos--${idx+1}` : ''}">${idx+1}</span></td>
                <td>${escHtml(r.display_name)}</td>
                <td class="col-num td-pts">${r.points}</td>
                <td class="col-num col-muted">${r.matches_played}</td>
              </tr>`).join('');
          }).catch(() => {});
      }

      // WDR checkbox toggle — wyłącza wpisywanie setów, pokazuje select "zwycięzca"
      list.querySelectorAll<HTMLInputElement>('.ps-wdr-cb').forEach(cb => {
        cb.addEventListener('change', () => {
          const form = cb.closest('form') as HTMLFormElement;
          const wdrWinner = form?.querySelector<HTMLElement>('.org-wdr-winner');
          if (!wdrWinner) return;

          const setInputs = form.querySelectorAll<HTMLInputElement>('.org-set-input');
          const scoreboardGrid = form.querySelector<HTMLElement>('.amr-scoreboard-grid');

          if (cb.checked) {
            wdrWinner.style.display = 'flex';
            setInputs.forEach(input => {
              input.disabled = true;
              input.dataset.oldValue = input.value;
              input.value = '';
            });
            if (scoreboardGrid) {
              scoreboardGrid.style.opacity = '0.5';
              scoreboardGrid.style.pointerEvents = 'none';
            }
          } else {
            wdrWinner.style.display = 'none';
            setInputs.forEach(input => {
              input.disabled = false;
              if (input.dataset.oldValue !== undefined) {
                input.value = input.dataset.oldValue;
              }
            });
            if (scoreboardGrid) {
              scoreboardGrid.style.opacity = '1';
              scoreboardGrid.style.pointerEvents = 'auto';
            }
          }
        });
      });

      // Formularze submit
      list.querySelectorAll<HTMLFormElement>('.amr-ps-form').forEach(form => {
        const p1Input = form.querySelector<HTMLInputElement>('input[name="set1_p1"]');
        const p2Input = form.querySelector<HTMLInputElement>('input[name="set1_p2"]');
        if (p1Input && p2Input) {
          p1Input.addEventListener('input', () => {
            if (p1Input.value === '') { p2Input.value = ''; return; }
            const val = parseInt(p1Input.value, 10);
            if (!isNaN(val) && val >= 0 && val <= pointsPerMatch) p2Input.value = String(pointsPerMatch - val);
          });
          p2Input.addEventListener('input', () => {
            if (p2Input.value === '') { p1Input.value = ''; return; }
            const val = parseInt(p2Input.value, 10);
            if (!isNaN(val) && val >= 0 && val <= pointsPerMatch) p1Input.value = String(pointsPerMatch - val);
          });
        }

        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          const matchId = form.dataset.matchId;
          const btn = form.querySelector<HTMLButtonElement>('.org-save-btn');
          const msg = form.querySelector<HTMLElement>('.org-form-msg');
          if (!btn || !msg || !matchId) return;

          // Check WDR
          const wdrCb = form.querySelector<HTMLInputElement>('.ps-wdr-cb');
          const isWalkover = wdrCb?.checked ?? false;
          const winnerSelect = form.querySelector<HTMLSelectElement>('.ps-wdr-winner-select');
          const winnerIdStr = winnerSelect?.value ?? '';

          if (isWalkover && !winnerIdStr) {
            msg.textContent = 'Wybierz zwycięzcę.';
            msg.className = 'org-form-msg org-form-msg--err';
            return;
          }

          const fd = new FormData(form);
          const stInput = form.elements.namedItem('scheduled_time') as HTMLInputElement | null;
          let scheduledTimeVal = stInput ? (stInput.value || null) : undefined;
          if (stInput && !scheduledTimeVal) {
            const tzoffset = (new Date()).getTimezoneOffset() * 60000;
            scheduledTimeVal = (new Date(Date.now() - tzoffset)).toISOString().slice(0, 16);
          }

          let body: Record<string, any>;
          if (isWalkover) {
            body = {
              walkover: true,
              winner_participant_id: parseInt(winnerIdStr, 10),
              ...(scheduledTimeVal !== undefined ? { scheduled_time: scheduledTimeVal } : {}),
            };
          } else {
            const g1 = fd.get('set1_p1');
            const g2 = fd.get('set1_p2');
            body = {
              set1_p1: (g1 !== null && g1 !== '') ? parseInt(g1 as string, 10) : null,
              set1_p2: (g2 !== null && g2 !== '') ? parseInt(g2 as string, 10) : null,
              set2_p1: null, set2_p2: null,
              set3_p1: null, set3_p2: null,
              ...(scheduledTimeVal !== undefined ? { scheduled_time: scheduledTimeVal } : {}),
            };
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
              const idx = myMatches.findIndex(m => m.id === Number(matchId));
              if (idx !== -1) {
                myMatches[idx] = { ...myMatches[idx], status: d.status, score: d.score ?? null };
              }
              refreshAmrStandings();
              setTimeout(() => location.reload(), 1000);
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

