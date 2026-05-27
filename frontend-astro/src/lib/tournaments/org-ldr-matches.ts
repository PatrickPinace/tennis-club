// org-ldr-matches.ts — Score entry for LDR challenge matches in the organizer panel.
// LDR challenge matches come from GET /api/tournaments/<pk>/ladder/ (active_challenges + completed),
// not from /detail/ — so we maintain our own state and refresh independently.

import { escHtml, getCsrf, PENDING_STATUSES, DONE_STATUSES } from './helpers';
import type { OrgPanelConfig, MatchData } from './types';
import { buildMatchCard, handleScoreSubmit } from './org-matches';
import type { MatchState, MatchCallbacks } from './org-matches';

// Status codes that count as "pending" for LDR challenges
const LDR_ACTIVE_STATUSES = new Set(['SCH', 'INP', 'WAI', 'PND']);

type LdrChallengeRaw = {
  match_id: number;
  status: string;
  challenger: { id: number | null; display_name: string | null };
  challenged: { id: number | null; display_name: string | null };
  scheduled_time: string | null;
  score?: string | null;
  winner_name?: string | null;
  set1_p1_score?: number | null;
  set1_p2_score?: number | null;
  set2_p1_score?: number | null;
  set2_p2_score?: number | null;
  set3_p1_score?: number | null;
  set3_p2_score?: number | null;
};

function challengeToMatchData(ch: LdrChallengeRaw, index: number): MatchData {
  return {
    id: ch.match_id,
    round_number: 0,
    match_index: index + 1,
    bracket_type: undefined,
    status: ch.status,
    participant1_id: ch.challenger.id,
    participant2_id: ch.challenged.id,
    participant3_id: null,
    participant4_id: null,
    participant1_name: ch.challenger.display_name,
    participant2_name: ch.challenged.display_name,
    participant3_name: null,
    participant4_name: null,
    winner_name: ch.winner_name ?? null,
    score: ch.score ?? null,
    scheduled_time: ch.scheduled_time,
    set1_p1_score: ch.set1_p1_score ?? null,
    set1_p2_score: ch.set1_p2_score ?? null,
    set2_p1_score: ch.set2_p1_score ?? null,
    set2_p2_score: ch.set2_p2_score ?? null,
    set3_p1_score: ch.set3_p1_score ?? null,
    set3_p2_score: ch.set3_p2_score ?? null,
  };
}

// Override round label for LDR challenge cards — "R0 M1" is meaningless,
// show challenger vs challenged context instead.
// We post-process the rendered HTML to swap the label.
function patchMatchLabel(html: string, ch: LdrChallengeRaw): string {
  // Replace "R0 M<n>" or similar with "Wyzwanie"
  return html.replace(
    /<span class="org-match-label">[^<]*<\/span>/,
    `<span class="org-match-label">Wyzwanie</span>`,
  );
}

type LdrMatchState = {
  allChallenges: LdrChallengeRaw[];
  activeFilter: 'all' | 'pending' | 'done';
};

async function fetchChallenges(cfg: OrgPanelConfig): Promise<LdrChallengeRaw[]> {
  const res = await fetch(
    `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/ladder/`,
    { credentials: 'include' },
  );
  if (!res.ok) return [];
  const data = await res.json();
  // Include both active and completed challenges (backend returns both in active_challenges + recent)
  const active: LdrChallengeRaw[] = data.active_challenges ?? [];
  const recent: LdrChallengeRaw[] = data.recent_matches ?? [];
  // Deduplicate by match_id; active takes precedence
  const seen = new Set<number>();
  const merged: LdrChallengeRaw[] = [];
  for (const ch of [...active, ...recent]) {
    if (!seen.has(ch.match_id)) { seen.add(ch.match_id); merged.push(ch); }
  }
  return merged;
}

function renderLdrMatches(cfg: OrgPanelConfig, ldrState: LdrMatchState, state: MatchState, cbs: MatchCallbacks) {
  const container = document.getElementById('org-ldr-matches-list');
  if (!container) return;

  const { allChallenges, activeFilter } = ldrState;

  // Update filter button counts
  const pending = allChallenges.filter(ch => PENDING_STATUSES.has(ch.status) || LDR_ACTIVE_STATUSES.has(ch.status));
  const done    = allChallenges.filter(ch => DONE_STATUSES.has(ch.status));
  document.querySelectorAll<HTMLButtonElement>('.org-ldr-filter-btn').forEach(btn => {
    const f = btn.dataset.filter!;
    const count = f === 'pending' ? pending.length : f === 'done' ? done.length : allChallenges.length;
    btn.textContent = f === 'pending' ? `Aktywne${count ? ` (${count})` : ''}`
                    : f === 'done'    ? `Zakończone${count ? ` (${count})` : ''}`
                    :                   `Wszystkie (${count})`;
  });

  let filtered = allChallenges;
  if (activeFilter === 'pending') filtered = pending;
  else if (activeFilter === 'done') filtered = done;

  if (!filtered.length) {
    container.innerHTML = `<div class="org-matches-empty">Brak wyzwań${activeFilter !== 'all' ? ' dla wybranego filtra' : ''}.</div>`;
    return;
  }

  container.innerHTML = filtered.map((ch, i) => {
    const matchData = challengeToMatchData(ch, i);
    const html = buildMatchCard(matchData, cfg);
    return patchMatchLabel(html, ch);
  }).join('');

  // Toggle collapse on header click
  container.querySelectorAll<HTMLElement>('.org-match-header').forEach(header => {
    header.addEventListener('click', () => {
      const card = header.closest<HTMLElement>('.org-match');
      if (!card || card.dataset.status === 'CNC' || cfg.locked) return;
      card.classList.toggle('is-open');
    });
  });

  // Wire score forms
  const refreshMatchesData = async () => {
    ldrState.allChallenges = await fetchChallenges(cfg);
    renderLdrMatches(cfg, ldrState, state, cbs);
    // Also refresh the public ladder view (ranking table) if present on page
    const ldrRoot = document.getElementById('ldr-root');
    if (ldrRoot) {
      // Trigger a custom event so ldr-actions.ts or other listeners can re-render ranking
      document.dispatchEvent(new CustomEvent('ldr-score-updated'));
    }
  };

  container.querySelectorAll<HTMLFormElement>('.org-score-form').forEach(form => {
    form.addEventListener('submit', (e) => handleScoreSubmit(e, cfg, state, cbs, refreshMatchesData));
  });

  // CNC cancel handler
  container.querySelectorAll<HTMLButtonElement>('.org-cancel-match-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Anulować mecz? Wyniki zostaną usunięte.')) return;
      btn.disabled = true;
      const matchId = btn.dataset.matchId;
      const msgEl = btn.closest('form')?.querySelector<HTMLElement>('.org-form-msg');
      try {
        const res = await fetch(
          `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/matches/${matchId}/score/`,
          {
            method: 'PATCH', credentials: 'include',
            headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ cancel: true }),
          },
        );
        const d = await res.json().catch(() => ({}));
        if (res.ok) {
          ldrState.allChallenges = await fetchChallenges(cfg);
          renderLdrMatches(cfg, ldrState, state, cbs);
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

export async function initLdrMatches(cfg: OrgPanelConfig) {
  const section = document.getElementById('org-ldr-matches-section');
  if (!section) return;

  // Only show in ACT status
  if (cfg.tStatus !== 'ACT') return;
  section.style.display = '';

  const ldrState: LdrMatchState = {
    allChallenges: [],
    activeFilter: 'all',
  };

  // Shared MatchState for handleScoreSubmit signature compatibility (empty — not used for LDR)
  const state: MatchState = { allMatches: [], activeFilter: 'all', searchQuery: '' };
  // LDR has no bracket/standings to refresh — provide no-op callbacks
  const cbs: MatchCallbacks = {
    loadBracket: async () => {},
    loadStandings: async () => {},
    loadAmericanoStandings: async () => {},
  };

  // Filter buttons
  section.querySelectorAll<HTMLButtonElement>('.org-ldr-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      section.querySelectorAll('.org-ldr-filter-btn').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      ldrState.activeFilter = (btn.dataset.filter ?? 'all') as LdrMatchState['activeFilter'];
      renderLdrMatches(cfg, ldrState, state, cbs);
    });
  });

  ldrState.allChallenges = await fetchChallenges(cfg);
  renderLdrMatches(cfg, ldrState, state, cbs);
}
