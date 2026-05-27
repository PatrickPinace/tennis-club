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
  const wdrSection = hasParticipants ? `
    <div class="org-wdr-section">
      <label class="org-wdr-label">
        <input type="checkbox" name="walkover" class="org-wdr-checkbox" data-match-id="${m.id}">
        Walkover (WDR)
      </label>
      <div class="org-wdr-winner" style="display:none;">
        <label style="font-size:0.78rem;color:var(--text-muted);">Zwycięzca:</label>
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
        title="Anuluj mecz (CNC)">Anuluj mecz</button>
    </div>` : '';

  const btnLabel = (m.status === 'CMP' || m.status === 'WDR') ? 'Koryguj' : 'Zapisz wynik';

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
          ${cfg.isAMR ? `
          <div class="org-sets-row">
            <div class="org-set-group">
              <div class="org-set-label">Gemy</div>
              <div class="org-set-inputs">
                <div class="org-score-spinner">
                  <button type="button" class="org-spin-btn org-spin-up" tabindex="-1">▲</button>
                  <input class="org-set-input" type="number" min="0" max="${cfg.pointsPerMatch}"
                    name="set1_p1" placeholder="—" value="${v(m.set1_p1_score)}">
                  <button type="button" class="org-spin-btn org-spin-down" tabindex="-1">▼</button>
                </div>
                <span class="org-set-sep">:</span>
                <div class="org-score-spinner">
                  <button type="button" class="org-spin-btn org-spin-up" tabindex="-1">▲</button>
                  <input class="org-set-input" type="number" min="0" max="${cfg.pointsPerMatch}"
                    name="set1_p2" placeholder="—" value="${v(m.set1_p2_score)}">
                  <button type="button" class="org-spin-btn org-spin-down" tabindex="-1">▼</button>
                </div>
              </div>
            </div>
          </div>
          <div style="font-size:0.72rem;color:var(--text-dim);margin-bottom:8px;">
            Suma musi wynosić ${cfg.pointsPerMatch} gemów
          </div>` : `
          <div class="org-sets-row">
            ${[1,2,3].map(s => {
              const v1 = v(s===1?m.set1_p1_score:s===2?m.set2_p1_score:m.set3_p1_score);
              const v2 = v(s===1?m.set1_p2_score:s===2?m.set2_p2_score:m.set3_p2_score);
              return `
              <div class="org-set-group">
                <div class="org-set-label">Set ${s}</div>
                <div class="org-set-inputs">
                  <div class="org-score-spinner">
                    <button type="button" class="org-spin-btn org-spin-up" tabindex="-1">▲</button>
                    <input class="org-set-input" type="number" min="0" max="99"
                      name="set${s}_p1" placeholder="—" value="${v1}">
                    <button type="button" class="org-spin-btn org-spin-down" tabindex="-1">▼</button>
                  </div>
                  <span class="org-set-sep">:</span>
                  <div class="org-score-spinner">
                    <button type="button" class="org-spin-btn org-spin-up" tabindex="-1">▲</button>
                    <input class="org-set-input" type="number" min="0" max="99"
                      name="set${s}_p2" placeholder="—" value="${v2}">
                    <button type="button" class="org-spin-btn org-spin-down" tabindex="-1">▼</button>
                  </div>
                </div>
              </div>`;
            }).join('')}
          </div>`}
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
    body = {
      set1_p1: getVal('set1_p1'), set1_p2: getVal('set1_p2'),
      set2_p1: getVal('set2_p1'), set2_p2: getVal('set2_p2'),
      set3_p1: getVal('set3_p1'), set3_p2: getVal('set3_p2'),
    };
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

  // Spin buttons ▲/▼
  container.querySelectorAll<HTMLButtonElement>('.org-spin-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.closest('.org-score-spinner')?.querySelector<HTMLInputElement>('.org-set-input');
      if (!input) return;
      const cur = input.value === '' ? 0 : parseInt(input.value, 10);
      const max = parseInt(input.max || '99', 10);
      const min = parseInt(input.min || '0', 10);
      if (btn.classList.contains('org-spin-up')) {
        input.value = String(Math.min(cur + 1, max));
      } else {
        input.value = String(Math.max(cur - 1, min));
      }
      input.dispatchEvent(new Event('input'));
    });
  });

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
