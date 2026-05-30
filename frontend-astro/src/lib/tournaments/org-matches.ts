// Organizer matches — render match list, filtering, score submit, CNC cancel.
import { escHtml, getCsrf, valStr, PENDING_STATUSES, DONE_STATUSES } from './helpers';
import type { OrgPanelConfig, MatchData } from './types';

export type MatchState = {
  allMatches: MatchData[];
  activeFilter: string;
  searchQuery: string;
};

export type MatchCallbacks = {
  loadBracket: () => Promise<void>;
  loadStandings: () => Promise<void>;
  loadAmericanoStandings: () => Promise<void>;
};

function isPending(m: MatchData) { return PENDING_STATUSES.has(m.status); }
function isDone(m: MatchData)    { return DONE_STATUSES.has(m.status); }

function filterMatches(state: MatchState): MatchData[] {
  let list = state.allMatches;
  if (state.activeFilter === 'pending') list = list.filter(isPending);
  else if (state.activeFilter === 'done') list = list.filter(isDone);
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    list = list.filter(m =>
      (m.participant1_name ?? '').toLowerCase().includes(q) ||
      (m.participant2_name ?? '').toLowerCase().includes(q)
    );
  }
  return list;
}

export function buildMatchCard(m: MatchData, cfg: OrgPanelConfig): string {
  const isDoubles = m.participant3_id != null || m.participant4_id != null;
  const p1 = isDoubles
    ? escHtml(`${m.participant1_name ?? 'BYE'} / ${m.participant4_name ?? 'BYE'}`)
    : escHtml(m.participant1_name ?? 'BYE');
  const p2 = isDoubles
    ? escHtml(`${m.participant2_name ?? 'BYE'} / ${m.participant3_name ?? 'BYE'}`)
    : escHtml(m.participant2_name ?? 'BYE');
  const bracketPrefix = m.bracket_type === 'L' ? 'L-' : m.bracket_type === 'GF' ? 'GF ' : '';
  const roundLabel = m.bracket_type === 'GF'
    ? `GF M${m.match_index}`
    : `${bracketPrefix}R${m.round_number} M${m.match_index}`;

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

  const scoreChip = m.score
    ? `<span class="org-match-score org-match-score--done">${escHtml(m.score)}</span>`
    : m.status === 'WDR' && m.winner_name
      ? `<span class="org-match-score" style="font-size:0.72rem;">WO: ${escHtml(m.winner_name)}</span>`
      : '';

  const timeChip = m.scheduled_time
    ? (() => { try {
        const d = new Date(m.scheduled_time!);
        return `<span class="org-match-time">${d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})} ${d.toLocaleTimeString('pl-PL',{hour:'2-digit',minute:'2-digit'})}</span>`;
      } catch { return ''; } })()
    : '';

  const isPendingMatch = PENDING_STATUSES.has(m.status);
  const cardCls = [
    'org-match',
    isDone(m) ? 'org-match--done' : '',
    m.status === 'CNC' ? 'org-match--cancelled' : '',
    isPendingMatch ? 'org-match--pending' : '',
  ].filter(Boolean).join(' ');

  // BYE — mecz bez jednego z uczestników (może być p1 lub p2), zawsze read-only
  const isBye = !m.participant1_id || !m.participant2_id;
  if (isBye) {
    return `
      <div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
        <div class="org-match-header">
          <div class="org-match-meta">
            <span class="org-match-label">${roundLabel}</span>
            <span class="org-match-players">${m.participant1_id ? p1 : p2}<span class="vs" style="opacity:0.4;">vs</span><span style="color:var(--text-dim);font-style:italic;">BYE</span></span>
          </div>
          <div class="org-match-right">
            ${statusBadge}
            <span style="font-size:0.72rem;color:var(--text-dim);margin-left:4px;">wolny los</span>
          </div>
        </div>
      </div>`;
  }

  // Read-only for CNC or locked panel
  if (m.status === 'CNC' || cfg.locked) {
    return `
      <div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
        <div class="org-match-header">
          <div class="org-match-meta">
            <span class="org-match-label">${roundLabel}</span>
            <span class="org-match-players">${p1}<span class="vs">vs</span>${p2}</span>
          </div>
          <div class="org-match-right">
            ${timeChip}${scoreChip}${statusBadge}
          </div>
        </div>
      </div>`;
  }

  const v = valStr;
  const stVal = m.scheduled_time
    ? (() => { try { return new Date(m.scheduled_time!).toISOString().slice(0,16); } catch { return ''; } })()
    : '';

  const hasParticipants = m.participant1_id && m.participant2_id;

  // Skrócone nazwy graczy do etykiet nad polami setów
  const p1Short = isDoubles
    ? escHtml(`${(m.participant1_name ?? '?').split(' ').pop()}`)
    : escHtml((m.participant1_name ?? '?'));
  const p2Short = isDoubles
    ? escHtml(`${(m.participant2_name ?? '?').split(' ').pop()}`)
    : escHtml((m.participant2_name ?? '?'));

  const wdrSection = hasParticipants ? `
    <div class="org-wdr-section">
      <label class="org-wdr-label">
        <input type="checkbox" name="walkover" class="org-wdr-checkbox" data-match-id="${m.id}">
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style="color:var(--danger,#ef4444);opacity:0.7;"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
        Walkover (WDR)
      </label>
      <div class="org-wdr-winner" style="display:none;">
        <label style="font-size:0.78rem;color:var(--tc-muted);font-weight:600;">Zwycięzca:</label>
        <select name="winner_participant_id" class="org-wdr-select">
          <option value="">— wybierz —</option>
          <option value="${m.participant1_id}">${p1}</option>
          <option value="${m.participant2_id}">${p2}</option>
        </select>
      </div>
    </div>` : '';

  const cancelSection = (m.status !== 'CNC') ? `
    <div class="org-cancel-section">
      <button type="button" class="org-cancel-match-btn" data-match-id="${m.id}"
        title="Anuluj mecz (CNC)">
        <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
        Anuluj mecz
      </button>
    </div>` : '';

  const btnLabel = (m.status === 'CMP' || m.status === 'WDR') ? 'Koryguj wynik' : 'Zapisz wynik';

  // Formularz setów — bez spinnerów, czyste inputy z etykietami graczy
  const setsHtml = cfg.isAMR ? `
    <div class="org-sets-row">
      <div class="org-set-group">
        <div class="org-set-label">Gemy</div>
        <div class="org-set-inputs">
          <input class="org-set-input" type="number" min="0" max="${cfg.pointsPerMatch}"
            name="set1_p1" placeholder="—" value="${v(m.set1_p1_score)}" title="${p1Short}">
          <span class="org-set-sep">:</span>
          <input class="org-set-input" type="number" min="0" max="${cfg.pointsPerMatch}"
            name="set1_p2" placeholder="—" value="${v(m.set1_p2_score)}" title="${p2Short}">
        </div>
      </div>
    </div>
    <div style="font-size:0.72rem;color:var(--tc-muted);margin-bottom:8px;">
      Suma musi wynosić ${cfg.pointsPerMatch} gemów
    </div>` : `
    <div class="org-score-players-row">
      <span class="org-score-player-label" title="${p1}">${p1Short}</span>
      <span class="org-score-player-label--vs">vs</span>
      <span class="org-score-player-label" title="${p2}">${p2Short}</span>
    </div>
    <div class="org-sets-row">
      ${[1,2,3].map(s => {
        const v1 = v(s===1?m.set1_p1_score:s===2?m.set2_p1_score:m.set3_p1_score);
        const v2 = v(s===1?m.set1_p2_score:s===2?m.set2_p2_score:m.set3_p2_score);
        return `
        <div class="org-set-group">
          <div class="org-set-label">Set ${s}</div>
          <div class="org-set-inputs">
            <input class="org-set-input" type="number" min="0" max="99"
              name="set${s}_p1" placeholder="—" value="${v1}">
            <span class="org-set-sep">:</span>
            <input class="org-set-input" type="number" min="0" max="99"
              name="set${s}_p2" placeholder="—" value="${v2}">
          </div>
        </div>`;
      }).join('')}
    </div>`;

  return `
    <div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
      <div class="org-match-header">
        <div class="org-match-meta">
          <span class="org-match-label">${roundLabel}</span>
          <span class="org-match-players">${p1}<span class="vs">vs</span>${p2}</span>
        </div>
        <div class="org-match-right">
          ${timeChip}${scoreChip}${statusBadge}
          <span class="org-match-chevron">▼</span>
        </div>
      </div>
      <form class="org-score-form" data-match-id="${m.id}">
        <div class="org-form-row">
          ${setsHtml}
          <div class="org-scheduled-group">
            <div class="org-scheduled-label">Termin</div>
            <input id="st-${m.id}" class="org-datetime-input" type="datetime-local"
              name="scheduled_time" value="${stVal}">
          </div>
        </div>
        ${wdrSection}
        <div class="org-form-actions">
          <button type="submit" class="org-save-btn">${btnLabel}</button>
          <span class="org-form-msg" data-match-id="${m.id}"></span>
        </div>
        ${cancelSection}
      </form>
    </div>`;
}

/**
 * Walidacja tenisowa seta: czy wynik (a:b) jest możliwy w standardowym secie?
 * Dozwolone: 6:0–6:4, 7:5, 7:6, 6:7, 5:7, 0:6–4:6, lub super tie-break (≥10).
 * Zwraca null jeśli OK, string z błędem jeśli nie.
 */
function validateTennisSet(a: number, b: number, setNum: number): string | null {
  if (a < 0 || b < 0) return `Set ${setNum}: wynik nie może być ujemny.`;
  const hi = Math.max(a, b), lo = Math.min(a, b);
  // Super tie-break (do 10+)
  if (hi >= 10) {
    if (hi - lo < 2) return `Set ${setNum}: super tie-break wymaga przewagi co najmniej 2 punktów (${a}:${b}).`;
    return null;
  }
  // Standardowy set: zwycięzca musi mieć 6 lub 7
  if (hi < 6) return `Set ${setNum}: wynik ${a}:${b} jest nieprawidłowy — zwycięzca musi mieć co najmniej 6 gemów.`;
  if (hi === 6 && lo <= 4) return null;   // 6:0–6:4 ✓
  if (hi === 7 && (lo === 5 || lo === 6)) return null; // 7:5, 7:6 ✓
  if (hi === 6 && lo === 5) return `Set ${setNum}: przy wyniku 6:5 kontynuuje się grę — wynik niemożliwy.`;
  return `Set ${setNum}: wynik ${a}:${b} jest niemożliwy w standardowym secie tenisowym.`;
}

export async function handleScoreSubmit(
  e: Event,
  cfg: OrgPanelConfig,
  state: MatchState,
  cbs: MatchCallbacks,
  refreshMatchesData: () => Promise<void>,
) {
  e.preventDefault();
  const form = e.currentTarget as HTMLFormElement;
  const matchId = form.dataset.matchId;
  const msgEl = document.querySelector<HTMLElement>(`.org-form-msg[data-match-id="${matchId}"]`);
  const btn = form.querySelector<HTMLButtonElement>('.org-save-btn');

  const getVal = (name: string): number | null => {
    const v = (form.elements.namedItem(name) as HTMLInputElement)?.value;
    return v !== '' && v != null ? parseInt(v, 10) : null;
  };

  const wdrCheckbox = form.querySelector<HTMLInputElement>('.org-wdr-checkbox');
  const isWalkover = wdrCheckbox?.checked ?? false;

  const stInput = form.elements.namedItem('scheduled_time') as HTMLInputElement | null;
  const scheduledTimeVal = stInput ? (stInput.value || null) : undefined;

  let body: Record<string, unknown>;

  if (isWalkover) {
    const winnerSelect = form.elements.namedItem('winner_participant_id') as HTMLSelectElement | null;
    const winnerId = winnerSelect?.value ?? '';
    if (!winnerId) {
      if (msgEl) { msgEl.textContent = 'Wybierz zwycięzcę walkowera.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
      if (btn) btn.disabled = false;
      return;
    }
    body = { walkover: true, winner_participant_id: parseInt(winnerId, 10) };
    if (scheduledTimeVal !== undefined) body.scheduled_time = scheduledTimeVal;
  } else {
    const s1p1 = getVal('set1_p1'), s1p2 = getVal('set1_p2');
    const s2p1 = getVal('set2_p1'), s2p2 = getVal('set2_p2');
    const s3p1 = getVal('set3_p1'), s3p2 = getVal('set3_p2');

    // Walidacja tenisowa dla SGL / DBE / LDR — AMR i RND mają własne reguły backendowe
    if (cfg.isSGL || cfg.isDBE || cfg.isLDR) {
      // Set 1 wymagany
      if (s1p1 === null || s1p2 === null) {
        if (msgEl) { msgEl.textContent = 'Set 1 jest wymagany.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
        return;
      }
      const checks: Array<[number, number, number]> = [[s1p1, s1p2, 1]];
      if (s2p1 !== null && s2p2 !== null) checks.push([s2p1, s2p2, 2]);
      else if (s2p1 !== null || s2p2 !== null) {
        if (msgEl) { msgEl.textContent = 'Set 2: wpisz wynik dla obu stron.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
        return;
      }
      if (s3p1 !== null && s3p2 !== null) checks.push([s3p1, s3p2, 3]);
      else if (s3p1 !== null || s3p2 !== null) {
        if (msgEl) { msgEl.textContent = 'Set 3: wpisz wynik dla obu stron.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
        return;
      }
      for (const [a, b, n] of checks) {
        const err = validateTennisSet(a, b, n);
        if (err) {
          if (msgEl) { msgEl.textContent = err; msgEl.className = 'org-form-msg org-form-msg--err'; }
          return;
        }
      }
    }

    body = { set1_p1: s1p1, set1_p2: s1p2, set2_p1: s2p1, set2_p2: s2p2, set3_p1: s3p1, set3_p2: s3p2 };
    if (scheduledTimeVal !== undefined) body.scheduled_time = scheduledTimeVal;
  }

  if (btn) btn.disabled = true;
  if (msgEl) { msgEl.textContent = ''; msgEl.className = 'org-form-msg'; }

  const csrf = getCsrf();

  try {
    const res = await fetch(
      `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/matches/${matchId}/score/`,
      {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(csrf ? { 'X-CSRFToken': csrf } : {}),
        },
        body: JSON.stringify(body),
      }
    );

    if (res.ok) {
      const data = await res.json();
      if (msgEl) {
        msgEl.textContent = data.winner_name
          ? `Zapisano! Zwycięzca: ${data.winner_name}`
          : 'Zapisano wynik.';
        msgEl.className = 'org-form-msg org-form-msg--ok';
      }
      await refreshMatchesData();
      if (cfg.isSGL || cfg.isDBE) {
        await cbs.loadBracket();
      } else if (cfg.isAMR) {
        await cbs.loadAmericanoStandings();
        document.dispatchEvent(new CustomEvent('amr-match-scored'));
      } else {
        await cbs.loadStandings();
      }
    } else {
      const err = await res.json().catch(() => ({}));
      const msg = err?.detail || err?.error || `Błąd ${res.status}`;
      if (msgEl) { msgEl.textContent = msg; msgEl.className = 'org-form-msg org-form-msg--err'; }
    }
  } catch {
    if (msgEl) { msgEl.textContent = 'Błąd sieci.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

export function renderMatches(cfg: OrgPanelConfig, state: MatchState, cbs?: MatchCallbacks) {
  const container = document.getElementById('org-matches-list');
  if (!container) return;

  const matchesEl = document.getElementById('ssr-matches-data');
  if (!matchesEl) { container.innerHTML = '<div class="org-matches-empty">Brak danych meczów.</div>'; return; }
  try { state.allMatches = JSON.parse(matchesEl.textContent ?? '[]'); } catch { return; }

  applyMatchFilter(cfg, state, cbs);
}

export function applyMatchFilter(
  cfg: OrgPanelConfig,
  state: MatchState,
  cbs?: MatchCallbacks,
) {
  const container = document.getElementById('org-matches-list');
  if (!container) return;

  if (!state.allMatches.length) {
    container.innerHTML = '<div class="org-matches-empty">Mecze zostaną zaplanowane po zamknięciu zapisów.</div>';
    return;
  }

  const filtered = filterMatches(state);

  const pendingCount = state.allMatches.filter(isPending).length;
  const doneCount    = state.allMatches.filter(isDone).length;
  document.querySelectorAll<HTMLButtonElement>('.org-filter-btn').forEach(btn => {
    const f = btn.dataset.filter!;
    const count = f === 'pending' ? pendingCount : f === 'done' ? doneCount : state.allMatches.length;
    btn.textContent = f === 'pending' ? `Do wpisania${count ? ` (${count})` : ''}`
                    : f === 'done'    ? `Zakończone${count ? ` (${count})` : ''}`
                    :                   `Wszystkie (${count})`;
  });

  if (!filtered.length) {
    container.innerHTML = `<div class="org-matches-empty">Brak meczów dla wybranego filtra.</div>`;
    return;
  }

  container.innerHTML = filtered.map(m => buildMatchCard(m, cfg)).join('');

  // Toggle collapse
  container.querySelectorAll<HTMLElement>('.org-match-header').forEach(header => {
    header.addEventListener('click', () => {
      const card = header.closest<HTMLElement>('.org-match');
      if (!card || card.dataset.status === 'CNC' || cfg.locked) return;
      card.classList.toggle('is-open');
    });
  });

  // Score form submit handlers
  if (cbs) {
    const refreshMatchesData = async () => {
      try {
        const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/detail/`, { credentials: 'include' });
        if (!res.ok) return;
        const detail = await res.json();
        const el = document.getElementById('ssr-matches-data');
        if (el) el.textContent = JSON.stringify(detail.matches ?? []);
        renderMatches(cfg, state, cbs);
      } catch { /* silent degradation */ }
    };

    container.querySelectorAll<HTMLFormElement>('.org-score-form').forEach(form => {
      form.addEventListener('submit', (e) => handleScoreSubmit(e, cfg, state, cbs, refreshMatchesData));
    });

    // CNC cancel handler
    container.querySelectorAll<HTMLButtonElement>('.org-cancel-match-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm('Anulować mecz? Wyniki zostaną usunięte, mecz nie będzie brany pod uwagę w standings.')) return;
        btn.disabled = true;
        const matchId = btn.dataset.matchId;
        const msgEl = btn.closest('form')?.querySelector<HTMLElement>('.org-form-msg');
        try {
          const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/matches/${matchId}/score/`, {
            method: 'PATCH', credentials: 'include',
            headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ cancel: true }),
          });
          const d = await res.json().catch(() => ({}));
          if (res.ok) {
            const card = btn.closest<HTMLElement>('.org-match');
            if (card) {
              card.dataset.status = 'CNC';
              card.classList.remove('is-open');
            }
            const idx = state.allMatches.findIndex(m => m.id === Number(matchId));
            if (idx !== -1) {
              state.allMatches[idx] = { ...state.allMatches[idx], status: 'CNC', score: null,
                set1_p1_score: null, set1_p2_score: null,
                set2_p1_score: null, set2_p2_score: null,
                set3_p1_score: null, set3_p2_score: null,
                winner_name: null };
              renderMatches(cfg, state);
            }
            if (cfg.isSGL || cfg.isDBE) { await cbs.loadBracket(); } else if (cfg.isAMR) { await cbs.loadAmericanoStandings(); document.dispatchEvent(new CustomEvent('amr-match-scored')); } else { await cbs.loadStandings(); }
          } else {
            if (msgEl) { msgEl.textContent = d.detail ?? 'Błąd anulowania.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
            btn.disabled = false;
          }
        } catch {
          if (msgEl) { msgEl.textContent = 'Błąd sieci.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
          btn.disabled = false;
        }
      });
    });
  }

  // WDR checkbox toggle
  container.querySelectorAll<HTMLInputElement>('.org-wdr-checkbox').forEach(cb => {
    cb.addEventListener('change', () => {
      const form = cb.closest('form') as HTMLFormElement;
      const wdrWinner = form?.querySelector<HTMLElement>('.org-wdr-winner');
      const sets = form?.querySelector<HTMLElement>('.org-sets-row');
      if (!wdrWinner) return;
      wdrWinner.style.display = cb.checked ? '' : 'none';
      if (sets) sets.style.opacity = cb.checked ? '0.35' : '';
    });
  });
}

export function initMatchFilters(state: MatchState, cfg: OrgPanelConfig, cbs: MatchCallbacks) {
  document.querySelectorAll<HTMLButtonElement>('.org-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.org-filter-btn').forEach(b => b.classList.remove('org-filter-btn--active'));
      btn.classList.add('org-filter-btn--active');
      state.activeFilter = btn.dataset.filter ?? 'all';
      applyMatchFilter(cfg, state, cbs);
    });
  });

  const searchInput = document.getElementById('org-match-search') as HTMLInputElement | null;
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      state.searchQuery = searchInput.value.trim();
      applyMatchFilter(cfg, state, cbs);
    });
  }
}