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

function matchesSearch(m: MatchData, query: string): boolean {
  // Wyszukiwanie jednego lub dwóch tokenów.
  // Jeden token ("rusin") — pasuje jeśli którykolwiek uczestnik zawiera ten token.
  // Dwa tokeny ("dubiel rusin") — pasuje jeśli każdy token trafia w innego uczestnika
  // (czyli: dubiel gra z rusinem, niezależnie od kolejności).
  const names = [
    m.participant1_name ?? '',
    m.participant2_name ?? '',
    m.participant3_name ?? '',
    m.participant4_name ?? '',
  ].map(n => n.toLowerCase());

  const tokens = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return true;
  if (tokens.length === 1) return names.some(n => n.includes(tokens[0]));

  // Dwa lub więcej tokenów: każdy musi pasować do co najmniej jednego uczestnika,
  // przy czym dwa różne tokeny mogą trafić w tego samego gracza (np. "tomasz rusin").
  // Ale dla wyszukiwania pary chcemy żeby KAŻDY token był gdzieś w liście uczestników.
  return tokens.every(tok => names.some(n => n.includes(tok)));
}

function filterMatches(state: MatchState): MatchData[] {
  let list = state.allMatches;
  if (state.activeFilter === 'pending') list = list.filter(isPending);
  else if (state.activeFilter === 'done') list = list.filter(isDone);
  if (state.searchQuery) {
    list = list.filter(m => matchesSearch(m, state.searchQuery));
  }
  return list;
}

function getMatchResultClass(
  m: MatchData,
  isDoneVal: boolean,
  p1SetsWon: number | string,
  p2SetsWon: number | string,
  p1: string,
  myParticipantId: number | null | undefined,
): string {
  if (m.status === 'CNC') return 'td-match--result-cnc';
  if (!isDoneVal) {
    return m.status === 'INP' ? '' : 'td-match--result-pending';
  }
  if (!myParticipantId) {
    return 'td-match--result-neutral';
  }

  const isDoubles = m.participant3_id != null || m.participant4_id != null;
  const userInTeamA = m.participant1_id === myParticipantId || (isDoubles && m.participant4_id === myParticipantId);
  const userInTeamB = m.participant2_id === myParticipantId || (isDoubles && m.participant3_id === myParticipantId);

  if (!userInTeamA && !userInTeamB) {
    return 'td-match--result-neutral';
  }

  const teamAWon = m.winner_name
    ? (m.winner_name === p1)
    : (Number(p1SetsWon) > Number(p2SetsWon));

  const userWon = (userInTeamA && teamAWon) || (userInTeamB && !teamAWon);
  return userWon ? 'td-match--result-won' : 'td-match--result-lost';
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

  const timeChip = m.scheduled_time
    ? (() => { try {
        const d = new Date(m.scheduled_time!);
        return `<span class="org-match-time">${d.toLocaleDateString('pl-PL',{day:'2-digit',month:'2-digit'})}</span>`;
      } catch { return ''; } })()
    : '';

  // BYE — mecz bez jednego z uczestników (może być p1 lub p2), zawsze read-only
  const isBye = !m.participant1_id || !m.participant2_id;
  if (isBye) {
    const statusBadge = m.status === 'CMP'
      ? `<span class="tc-badge tc-badge-neutral" style="font-size:0.68rem;">Zakończony</span>`
      : `<span class="tc-badge" style="font-size:0.68rem;background:var(--surface-2);color:var(--text-dim);">Oczekuje</span>`;
    const byeCls = [
      'org-match',
      'td-match',
      'td-match--flashscore',
      m.status === 'CMP' ? 'org-match--done td-match--done td-match--result-neutral' : 'org-match--pending td-match--result-pending',
    ].join(' ');
    return `
      <div class="${byeCls}" data-match-id="${m.id}" data-status="${m.status}">
        <div class="org-match-header">
          <div class="org-match-meta">
            <div class="org-match-meta-top">
              <span class="org-match-label">${roundLabel}</span>
            </div>
            <span class="org-match-players">${m.participant1_id ? p1 : p2}<span class="vs" style="opacity:0.4;">vs</span><span style="color:var(--text-dim);font-style:italic;">BYE</span></span>
          </div>
          <div class="org-match-right">
            <span style="font-size:0.72rem;color:var(--text-dim);margin-left:4px;">wolny los</span>
          </div>
        </div>
      </div>`;
  }

  // Parse match score values for flashscore display
  const sets = [];
  let p1SetsWon: number | string = 0;
  let p2SetsWon: number | string = 0;

  if (m.set1_p1_score !== null && m.set1_p2_score !== null) {
    sets.push({ p1: m.set1_p1_score, p2: m.set1_p2_score });
  }
  if (m.set2_p1_score !== null && m.set2_p2_score !== null) {
    sets.push({ p1: m.set2_p1_score, p2: m.set2_p2_score });
  }
  if (m.set3_p1_score !== null && m.set3_p2_score !== null) {
    sets.push({ p1: m.set3_p1_score, p2: m.set3_p2_score });
  }

  const isWalkover = m.status === 'WDR';
  const hasScore = sets.length > 0 || isWalkover;

  if (isWalkover) {
    const p1WonVal = m.winner_name === p1;
    p1SetsWon = p1WonVal ? 'W' : 'L';
    p2SetsWon = p1WonVal ? 'L' : 'W';
  } else if (hasScore) {
    let w1 = 0, w2 = 0;
    for (const s of sets) {
      if (s.p1 > s.p2) w1++;
      else if (s.p1 < s.p2) w2++;
    }
    p1SetsWon = w1;
    p2SetsWon = w2;
  }

  const isDoneVal = m.status === 'CMP' || m.status === 'WDR';
  const p1Won = isDoneVal && (m.winner_name ? m.winner_name === p1 : Number(p1SetsWon) > Number(p2SetsWon));
  const p2Won = isDoneVal && (m.winner_name ? m.winner_name === p2 : Number(p2SetsWon) > Number(p1SetsWon));

  const resultCls = getMatchResultClass(m, isDoneVal, p1SetsWon, p2SetsWon, p1, cfg.myParticipantId);

  const cardCls = [
    'org-match',
    'td-match',
    'td-match--flashscore',
    isDoneVal ? 'org-match--done td-match--done' : '',
    m.status === 'CNC' ? 'org-match--cancelled td-match--result-cnc' : '',
    resultCls,
  ].filter(Boolean).join(' ');

  const MATCH_STATUS_LABEL: Record<string, string> = {
    WAI: 'Oczekuje', SCH: 'Zaplanowany', INP: 'W trakcie',
    CMP: 'Zakończony', WDR: 'Walkower', CNC: 'Odwołany',
  };

  const statusLabel = m.status === 'INP' ? '● Live' : MATCH_STATUS_LABEL[m.status] ?? m.status;

  const setsHtmlP1 = sets.map(s => {
    return `<span class="fs-match__score-set ${s.p1 > s.p2 && isDoneVal ? 'fs-match__score-set--won' : ''}">${s.p1}</span>`;
  }).join('');

  const setsHtmlP2 = sets.map(s => {
    return `<span class="fs-match__score-set ${s.p2 > s.p1 && isDoneVal ? 'fs-match__score-set--won' : ''}">${s.p2}</span>`;
  }).join('');

  const scoreScoresHtmlP1 = hasScore ? `
    <span class="fs-match__score-overall ${isDoneVal ? (p1Won ? 'fs-match__score-overall--won' : 'fs-match__score-overall--lost') : ''}">${p1SetsWon}</span>
    ${setsHtmlP1}
  ` : `
    <span class="fs-match__status">${statusLabel}</span>
  `;

  const scoreScoresHtmlP2 = hasScore ? `
    <span class="fs-match__score-overall ${isDoneVal ? (p2Won ? 'fs-match__score-overall--won' : 'fs-match__score-overall--lost') : ''}">${p2SetsWon}</span>
    ${setsHtmlP2}
  ` : `
    <span class="fs-match__status" style="visibility: hidden;">${statusLabel}</span>
  `;

  const headerHtml = `
    <div class="org-match-header org-match-header--flashscore">
      <div class="fs-match-wrapper">
        <div class="fs-match-meta-col">
          <span class="fs-match-round-lbl">${roundLabel}</span>
          ${timeChip}
        </div>
        <div class="fs-match">
          <div class="fs-match__row">
            <span class="fs-match__name ${p1Won ? 'fs-match__name--winner' : ''}">${p1}</span>
            <div class="fs-match__scores">
              ${scoreScoresHtmlP1}
            </div>
          </div>
          <div class="fs-match__row">
            <span class="fs-match__name ${p2Won ? 'fs-match__name--winner' : ''}">${p2}</span>
            <div class="fs-match__scores">
              ${scoreScoresHtmlP2}
            </div>
          </div>
        </div>
      </div>
      <div class="org-match-right">
        ${(m.status !== 'CNC' && !cfg.locked) ? '<span class="org-match-chevron">▼</span>' : ''}
      </div>
    </div>
  `;

  // Read-only for CNC or locked panel
  if (m.status === 'CNC' || cfg.locked) {
    return `
      <div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
        ${headerHtml}
      </div>`;
  }

  const v = valStr;
  const stVal = m.scheduled_time
    ? (() => { try { return new Date(m.scheduled_time!).toISOString().slice(0,16); } catch { return ''; } })()
    : '';

  const hasParticipants = m.participant1_id && m.participant2_id;

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

  const wdrSection = hasParticipants ? `
    <div class="org-wdr-section">
      <label class="org-wdr-label">
        <input type="checkbox" name="walkover" class="org-wdr-checkbox" data-match-id="${m.id}">
        <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style="color:var(--danger,#ef4444);opacity:0.7;"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
        Walkover (<abbr title="Walkover — zwycięstwo bez gry, gdy przeciwnik się wycofuje lub nie stawi">WDR</abbr>)
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

  const cancelButtonHtml = (m.status !== 'CNC') ? `
    <button type="button" class="org-cancel-match-btn" data-match-id="${m.id}"
      style="margin: 0; padding: 4px 8px; border: none; background: none; font-size: 0.72rem;"
      title="Anuluj mecz (CNC)">
      <svg width="12" height="12" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" style="display: inline-block; vertical-align: middle; margin-right: 4px;"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
      Anuluj mecz
    </button>` : '';

  const btnLabel = (m.status === 'CMP' || m.status === 'WDR') ? 'Koryguj wynik' : 'Zapisz wynik';

  // Formularz setów — bez spinnerów, czyste inputy z etykietami graczy
  const setsHtml = cfg.isAMR ? `
    <div style="width: 100%;">
      <div class="amr-scoreboard-grid" style="background: var(--tc-chip-bg); border: 1px solid var(--tc-card-border); border-radius: 8px; overflow: hidden; margin-bottom: 6px; display: grid; grid-template-columns: 1fr 80px; align-items: center; width: 100%;">
        <div style="padding: 10px 14px; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Gracz</div>
        <div style="text-align: center; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Punkty</div>
        
        <div style="padding: 10px 14px; font-size: 0.88rem; font-weight: 600; color: var(--tc-ink); border-top: 1px solid var(--tc-card-border-soft); text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <span class="player-name-full">${p1}</span>
          <span class="player-name-short">${p1Short}</span>
        </div>
        <div style="padding: 6px; display: flex; justify-content: center; border-top: 1px solid var(--tc-card-border-soft);">
          <input class="org-set-input" type="number" min="0" max="${cfg.pointsPerMatch}"
            name="set1_p1" placeholder="—" value="${v(m.set1_p1_score)}"
            style="width: 48px; height: 32px; text-align: center; background: var(--tc-card-bg); border: 1px solid var(--tc-card-border); border-radius: 4px; color: var(--tc-ink); font-weight: 600;">
        </div>

        <div style="padding: 10px 14px; font-size: 0.88rem; font-weight: 600; color: var(--tc-ink); border-top: 1px solid var(--tc-card-border-soft); text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <span class="player-name-full">${p2}</span>
          <span class="player-name-short">${p2Short}</span>
        </div>
        <div style="padding: 6px; display: flex; justify-content: center; border-top: 1px solid var(--tc-card-border-soft);">
          <input class="org-set-input" type="number" min="0" max="${cfg.pointsPerMatch}"
            name="set1_p2" placeholder="—" value="${v(m.set1_p2_score)}"
            style="width: 48px; height: 32px; text-align: center; background: var(--tc-card-bg); border: 1px solid var(--tc-card-border); border-radius: 4px; color: var(--tc-ink); font-weight: 600;">
        </div>
      </div>
      <div style="font-size:0.72rem;color:var(--tc-muted);margin-bottom:8px;margin-left:2px;">
        * Suma musi wynosić ${cfg.pointsPerMatch} punktów
      </div>
    </div>` : `
    <div style="width: 100%;">
      <div class="scoreboard-grid" style="background: var(--tc-chip-bg); border: 1px solid var(--tc-card-border); border-radius: 8px; overflow: hidden; margin-bottom: 8px; display: grid; grid-template-columns: 1fr 60px 60px 60px; align-items: center; width: 100%;">
        <div style="padding: 10px 14px; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Gracz</div>
        <div style="text-align: center; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Set 1</div>
        <div style="text-align: center; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Set 2</div>
        <div style="text-align: center; font-size: 0.68rem; font-weight: 700; color: var(--tc-muted); text-transform: uppercase;">Set 3</div>
        
        <div style="padding: 10px 14px; font-size: 0.88rem; font-weight: 600; color: var(--tc-ink); border-top: 1px solid var(--tc-card-border-soft); text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <span class="player-name-full">${p1}</span>
          <span class="player-name-short">${p1Short}</span>
        </div>
        ${[1,2,3].map(s => {
          const val = v(s===1?m.set1_p1_score:s===2?m.set2_p1_score:m.set3_p1_score);
          return `
          <div style="padding: 6px; display: flex; justify-content: center; border-top: 1px solid var(--tc-card-border-soft);">
            <input class="org-set-input" type="number" min="0" max="99"
              name="set${s}_p1" placeholder="—" value="${val}"
              style="width: 42px; height: 32px; text-align: center; background: var(--tc-card-bg); border: 1px solid var(--tc-card-border); border-radius: 4px; color: var(--tc-ink); font-weight: 600;">
          </div>`;
        }).join('')}

        <div style="padding: 10px 14px; font-size: 0.88rem; font-weight: 600; color: var(--tc-ink); border-top: 1px solid var(--tc-card-border-soft); text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <span class="player-name-full">${p2}</span>
          <span class="player-name-short">${p2Short}</span>
        </div>
        ${[1,2,3].map(s => {
          const val = v(s===1?m.set1_p2_score:s===2?m.set2_p2_score:m.set3_p2_score);
          return `
          <div style="padding: 6px; display: flex; justify-content: center; border-top: 1px solid var(--tc-card-border-soft);">
            <input class="org-set-input" type="number" min="0" max="99"
              name="set${s}_p2" placeholder="—" value="${val}"
              style="width: 42px; height: 32px; text-align: center; background: var(--tc-card-bg); border: 1px solid var(--tc-card-border); border-radius: 4px; color: var(--tc-ink); font-weight: 600;">
          </div>`;
        }).join('')}
      </div>
    </div>`;
 
  return `
    <div class="${cardCls}" data-match-id="${m.id}" data-status="${m.status}">
      ${headerHtml}
      <form class="org-score-form" data-match-id="${m.id}">
        <div class="org-form-row">
          ${setsHtml}
          <div class="org-scheduled-group" style="width: 100%;">
            <div class="org-scheduled-label">Termin</div>
            <input id="st-${m.id}" class="org-datetime-input" type="datetime-local"
              name="scheduled_time" value="${stVal}" style="width: 100%; box-sizing: border-box;">
          </div>
        </div>
        ${wdrSection}
        <div class="org-form-actions" style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
          <div>
            ${cancelButtonHtml}
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="org-form-msg" data-match-id="${m.id}"></span>
            <button type="submit" class="org-save-btn">${btnLabel}</button>
          </div>
        </div>
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
  // Super tie-break (do 10, z przewagą ≥ 2; realistyczny max ~20)
  if (hi >= 10) {
    if (hi > 20) return `Set ${setNum}: super tie-break nie może mieć więcej niż 20 punktów (${a}:${b}).`;
    if (hi - lo < 2) return `Set ${setNum}: super tie-break wymaga przewagi co najmniej 2 punktów (${a}:${b}).`;
    // przy hi > 10 loser musi mieć przynajmniej hi-2 (kontynuujemy aż ktoś wygra 2)
    if (hi > 10 && lo !== hi - 2) return `Set ${setNum}: po 10:10 gra trwa do różnicy 2 punktów — ${a}:${b} jest niemożliwe.`;
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

  // Disable natychmiast — blokuje podwójne kliknięcie zanim cokolwiek sprawdzimy
  if (btn) btn.disabled = true;

  const getVal = (name: string): number | null => {
    const v = (form.elements.namedItem(name) as HTMLInputElement)?.value;
    return v !== '' && v != null ? parseInt(v, 10) : null;
  };

  const wdrCheckbox = form.querySelector<HTMLInputElement>('.org-wdr-checkbox');
  const isWalkover = wdrCheckbox?.checked ?? false;

  const stInput = form.elements.namedItem('scheduled_time') as HTMLInputElement | null;
  let scheduledTimeVal = stInput ? (stInput.value || null) : undefined;
  if (stInput && !scheduledTimeVal) {
    const tzoffset = (new Date()).getTimezoneOffset() * 60000;
    scheduledTimeVal = (new Date(Date.now() - tzoffset)).toISOString().slice(0, 16);
  }

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

    // Walidacja tenisowa dla SGL / DBE / LDR / RND — AMR ma własne reguły backendowe
    if (cfg.isSGL || cfg.isDBE || cfg.isLDR || (!cfg.isAMR)) {
      // Set 1 wymagany
      const rejectValidation = (msg: string) => {
        if (msgEl) { msgEl.textContent = msg; msgEl.className = 'org-form-msg org-form-msg--err'; }
        if (btn) btn.disabled = false;
      };
      if (s1p1 === null || s1p2 === null) { rejectValidation('Set 1 jest wymagany.'); return; }
      const checks: Array<[number, number, number]> = [[s1p1, s1p2, 1]];
      if (s2p1 !== null && s2p2 !== null) checks.push([s2p1, s2p2, 2]);
      else if (s2p1 !== null || s2p2 !== null) { rejectValidation('Set 2: wpisz wynik dla obu stron.'); return; }
      if (s3p1 !== null && s3p2 !== null) checks.push([s3p1, s3p2, 3]);
      else if (s3p1 !== null || s3p2 !== null) { rejectValidation('Set 3: wpisz wynik dla obu stron.'); return; }
      for (const [a, b, n] of checks) {
        const err = validateTennisSet(a, b, n);
        if (err) { rejectValidation(err); return; }
      }
    }

    body = { set1_p1: s1p1, set1_p2: s1p2, set2_p1: s2p1, set2_p2: s2p2, set3_p1: s3p1, set3_p2: s3p2 };
    if (scheduledTimeVal !== undefined) body.scheduled_time = scheduledTimeVal;
  }

  if (msgEl) { msgEl.textContent = ''; msgEl.className = 'org-form-msg'; }

  const csrf = getCsrf();

  // Usuwa inline confirm jeśli był wyświetlony (np. anuluj)
  const clearForceConfirm = () => {
    form.querySelector('.org-force-confirm')?.remove();
  };

  // Opis downstream meczu w czytelnej formie: "WB R2 mecz 1 (CMP)"
  const downstreamLabel = (d: {bracket: string; round: number; index: number; status: string}): string => {
    const brackets: Record<string, string> = { W: 'WB', L: 'LB', GF: 'Wielki Finał' };
    const b = brackets[d.bracket] ?? d.bracket;
    const statusLabel: Record<string, string> = { CMP: 'zakończony', WDR: 'walkover' };
    const s = statusLabel[d.status] ?? d.status;
    return d.bracket === 'GF' ? `Wielki Finał (${s})` : `${b} R${d.round} mecz ${d.index} (${s})`;
  };

  const doFetch = async (withForce: boolean) => {
    const sendBody = withForce ? { ...body, force: true } : body;
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
          body: JSON.stringify(sendBody),
        }
      );

      if (res.ok) {
        clearForceConfirm();
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
          setTimeout(() => {
            window.location.reload();
          }, 800);
        }
        if (btn) btn.disabled = false;
        return;
      }

      const err = await res.json().catch(() => ({}));

      // Hard-lock LDR
      if (res.status === 409 && err?.code === 'ladder_locked') {
        clearForceConfirm();
        if (msgEl) { msgEl.textContent = err.detail ?? 'Mecze ladder nie mogą być edytowane po zakończeniu.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
        if (btn) btn.disabled = false;
        return;
      }

      // Downstream lock — organizer widzi confirm, nie-org widzi komunikat
      if (res.status === 409 && err?.code === 'downstream_locked') {
        clearForceConfirm();
        if (!err?.force_allowed) {
          if (msgEl) { msgEl.textContent = 'Wynik nie może być już zmieniony — skontaktuj się z organizatorem.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
          if (btn) btn.disabled = false;
          return;
        }

        // Organizer: pokaż inline confirm z opisem downstream
        const actionsEl = form.querySelector<HTMLElement>('.org-form-actions');
        if (!actionsEl) { if (btn) btn.disabled = false; return; }

        const downstream: Array<{bracket: string; round: number; index: number; status: string}> = err?.downstream ?? [];
        const listText = downstream.length
          ? downstream.map(downstreamLabel).join(', ')
          : 'kolejne mecze';

        const confirmEl = document.createElement('div');
        confirmEl.className = 'org-force-confirm';
        confirmEl.innerHTML = `
          <div class="org-force-confirm__msg">
            Następujące mecze są już rozegrane: <strong>${listText}</strong>.
            Po zapisie ich uczestnicy mogą się zmienić, ale wyniki zostaną.
          </div>
          <div class="org-force-confirm__actions">
            <button type="button" class="org-force-cancel tc-btn tc-btn-ghost">Anuluj</button>
            <button type="button" class="org-force-confirm-btn tc-btn tc-btn-danger">Zapisz mimo to</button>
          </div>`;

        actionsEl.after(confirmEl);
        if (msgEl) { msgEl.textContent = ''; msgEl.className = 'org-form-msg'; }
        if (btn) btn.disabled = false;

        confirmEl.querySelector<HTMLButtonElement>('.org-force-cancel')!.addEventListener('click', () => {
          clearForceConfirm();
        });
        confirmEl.querySelector<HTMLButtonElement>('.org-force-confirm-btn')!.addEventListener('click', () => {
          clearForceConfirm();
          if (btn) btn.disabled = true;
          doFetch(true);
        });
        return;
      }

      // Pozostałe błędy
      clearForceConfirm();
      const msg = err?.detail || err?.error || `Błąd ${res.status}`;
      if (msgEl) { msgEl.textContent = msg; msgEl.className = 'org-form-msg org-form-msg--err'; }
      if (btn) btn.disabled = false;
    } catch {
      clearForceConfirm();
      if (msgEl) { msgEl.textContent = 'Błąd sieci.'; msgEl.className = 'org-form-msg org-form-msg--err'; }
      if (btn) btn.disabled = false;
    }
  };

  await doFetch(false);
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
  document.querySelectorAll<HTMLButtonElement>('#org-filter-group .org-filter-btn').forEach(btn => {
    const f = btn.dataset.filter!;
    const count = f === 'pending' ? pendingCount : f === 'done' ? doneCount : state.allMatches.length;
    btn.innerHTML = f === 'pending' ? `Do wpisania${count ? ` <span class="org-filter-count">(${count})</span>` : ''}`
                  : f === 'done'    ? `Zakończone${count ? ` <span class="org-filter-count">(${count})</span>` : ''}`
                  :                   `Wszystkie <span class="org-filter-count">(${count})</span>`;
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
        const oldMaxRound = state.allMatches.reduce((m, x) => Math.max(m, x.round_number || 0), 0);
        const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/detail/`, { credentials: 'include' });
        if (!res.ok) return;
        const detail = await res.json();
        const el = document.getElementById('ssr-matches-data');
        if (el) el.textContent = JSON.stringify(detail.matches ?? []);
        const amrEl = document.getElementById('amr-ssr-matches-data');
        if (amrEl) amrEl.textContent = JSON.stringify(detail.matches ?? []);
        renderMatches(cfg, state, cbs);

        if (cfg.isAMR) {
          const newMaxRound = state.allMatches.reduce((m, x) => Math.max(m, x.round_number || 0), 0);
          if (newMaxRound > oldMaxRound && oldMaxRound > 0) {
            setTimeout(() => location.reload(), 1000);
          }
        }
      } catch { /* silent degradation */ }
    };

    container.querySelectorAll<HTMLFormElement>('.org-score-form').forEach(form => {
      form.addEventListener('submit', (e) => handleScoreSubmit(e, cfg, state, cbs, refreshMatchesData));

      if (cfg.isAMR) {
        const p1Input = form.querySelector<HTMLInputElement>('input[name="set1_p1"]');
        const p2Input = form.querySelector<HTMLInputElement>('input[name="set1_p2"]');
        if (p1Input && p2Input) {
          const total = cfg.pointsPerMatch;
          p1Input.addEventListener('input', () => {
            if (p1Input.value === '') { p2Input.value = ''; return; }
            const val = parseInt(p1Input.value, 10);
            if (!isNaN(val) && val >= 0 && val <= total) p2Input.value = String(total - val);
          });
          p2Input.addEventListener('input', () => {
            if (p2Input.value === '') { p1Input.value = ''; return; }
            const val = parseInt(p2Input.value, 10);
            if (!isNaN(val) && val >= 0 && val <= total) p1Input.value = String(total - val);
          });
        }
      }
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
            if (cfg.isSGL || cfg.isDBE) {
               await cbs.loadBracket();
             } else if (cfg.isAMR) {
               await cbs.loadAmericanoStandings();
               document.dispatchEvent(new CustomEvent('amr-match-scored'));
             } else {
               await cbs.loadStandings();
               setTimeout(() => {
                 window.location.reload();
               }, 800);
             }
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
  document.querySelectorAll<HTMLButtonElement>('#org-filter-group .org-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#org-filter-group .org-filter-btn').forEach(b => b.classList.remove('org-filter-btn--active'));
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