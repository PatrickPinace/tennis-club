// Organizer panel — main entry point.
// Auth check, panel visibility, config, dispatch to sub-modules.
import type { OrgPanelConfig } from './types';
import type { MatchState, MatchCallbacks } from './org-matches';
import { renderMatches, initMatchFilters, applyMatchFilter } from './org-matches';
import { loadStandings, loadAmericanoStandings } from './org-standings';
import { renderBracket, loadBracket } from './org-bracket';
import { initStatusPanel } from './org-status';
import { initFinishButton } from './org-finish';
import { initParticipantsPanel } from './org-participants';
import { initConfigForm } from './org-config-rr';
import { initAmrConfigForm } from './org-config-amr';
import { initMexicanoRoundSection } from './mexicano-round';
import { initViewToggle } from './org-view-toggle';

(async () => {
  // AMR panel has unique id="org-panel-amr"; SGL and RND have id="org-panel".
  const amrPanel = document.getElementById('org-panel-amr') as HTMLElement | null;
  const anyPanel = amrPanel ?? document.getElementById('org-panel') as HTMLElement | null;
  if (!anyPanel) return;

  const tType = anyPanel.dataset.tournamentType ?? 'RND';

  const panel: HTMLElement = amrPanel
    ? amrPanel
    : (document.querySelector<HTMLElement>(`[id="org-panel"][data-panel-type="${tType === 'SGL' ? 'SGL' : tType === 'DBE' ? 'DBE' : 'RND'}"]`) ?? anyPanel);

  const tournamentId   = panel.dataset.tournamentId ?? '';
  const createdBy      = panel.dataset.createdBy ?? '';
  const tStatus        = panel.dataset.tournamentStatus ?? '';
  const setsToWin      = parseInt(panel.dataset.setsToWin ?? '2', 10);
  const pointsPerMatch = parseInt(panel.dataset.pointsPerMatch ?? '32', 10);
  const apiBase        = (document.querySelector('meta[name="api-base"]') as HTMLMetaElement)?.content ?? '';
  const isSGL          = tType === 'SGL';
  const isDBE          = tType === 'DBE';
  const isAMR          = tType === 'AMR';

  // 1. Auth check
  let meData: { authenticated?: boolean; user?: { username?: string; is_staff?: boolean } } = {};
  try {
    const res = await fetch(`${apiBase}/api/auth/me/`, { credentials: 'include' });
    if (res.ok) meData = await res.json();
  } catch { /* backend unavailable */ }

  const me = meData?.user;
  const isOrganizer = meData?.authenticated && me &&
    (me.is_staff || me.username === createdBy);

  if (!isOrganizer) return;

  // Show panel
  panel.style.display = '';

  const lockedHard = tStatus === 'FIN' || tStatus === 'CNC';
  const locked     = lockedHard || tStatus === 'SCH' || tStatus === 'DRF';
  if (lockedHard) {
    const lockedMsg = document.getElementById('org-locked-msg');
    if (lockedMsg) lockedMsg.style.display = '';
  }

  const cfg: OrgPanelConfig = {
    panel, tournamentId, createdBy, tStatus, tType,
    setsToWin, pointsPerMatch, apiBase, isSGL, isDBE, isAMR,
    locked, lockedHard,
  };

  // Shared mutable match state
  const matchState: MatchState = {
    allMatches: [],
    activeFilter: 'pending',
    searchQuery: '',
  };

  // Cross-module callbacks
  const cbs: MatchCallbacks = {
    loadBracket: () => loadBracket(cfg),
    loadStandings: () => loadStandings(cfg),
    loadAmericanoStandings: () => loadAmericanoStandings(cfg),
  };

  // Dispatch per tournament type
  if (isSGL || isDBE) {
    if (tStatus !== 'DRF' && tStatus !== 'REG') {
      await loadBracket(cfg);
    }
    initMatchFilters(matchState, cfg, cbs);
    renderMatches(cfg, matchState);
    applyMatchFilter(cfg, matchState, cbs);
    initFinishButton(cfg, () => loadStandings(cfg));
    initStatusPanel(cfg);
    initParticipantsPanel(cfg);
  } else if (isAMR) {
    if (tStatus !== 'DRF' && tStatus !== 'REG') {
      await loadAmericanoStandings(cfg);
    }
    initAmrConfigForm(cfg);
    initMexicanoRoundSection(cfg);
    initMatchFilters(matchState, cfg, cbs);
    renderMatches(cfg, matchState);
    applyMatchFilter(cfg, matchState, cbs);
    initFinishButton(cfg, () => loadStandings(cfg));
    initStatusPanel(cfg);
    initParticipantsPanel(cfg);
  } else {
    await loadStandings(cfg);
    initMatchFilters(matchState, cfg, cbs);
    renderMatches(cfg, matchState);
    applyMatchFilter(cfg, matchState, cbs);
    initConfigForm(cfg);
    initFinishButton(cfg, () => loadStandings(cfg));
    initStatusPanel(cfg);
    initParticipantsPanel(cfg);
  }
})();
