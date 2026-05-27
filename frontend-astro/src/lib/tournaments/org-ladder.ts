// org-ladder.ts — Organizer panel entry point for Ladder (LDR) tournaments.
// Analogous to org-panel.ts; handles auth, reveals panel, dispatches to sub-modules.
//
// Sub-modules reused from other tournament types:
//   initStatusPanel    — status transitions (DRF→REG→SCH→ACT→FIN)
//   initParticipantsPanel — add/remove participants, close registration
//   initFinishButton   — finish/cancel tournament
//   initLdrConfigForm  — LDR-specific config (challenge_range, initial_seeding)
//
// LDR-specific additions:
//   initLdrMatches     — fetches challenge matches, renders score cards (org-ldr-matches.ts)
//   LDR status panel uses custom TRANSITIONS (no "generuj mecze" label)

import type { OrgPanelConfig } from './types';
import { initStatusPanel }      from './org-status';
import { initFinishButton }     from './org-finish';
import { initParticipantsPanel } from './org-participants';
import { initLdrConfigForm }    from './org-config-ldr';
import { initLdrMatches }       from './org-ldr-matches';
import { initLdrSeeds }        from './org-ldr-seeds';

// ── Custom status transitions for LDR ────────────────────────────────────────
// Override: REG→SCH should say "Zamknij zapisy" not "generuj mecze" (no bracket).

// ── Main entry point ──────────────────────────────────────────────────────────
(async () => {
  const panel = document.getElementById('org-panel-ldr') as HTMLElement | null;
  if (!panel) return;

  const tournamentId = panel.dataset.tournamentId ?? '';
  const createdBy    = panel.dataset.createdBy ?? '';
  const tStatus      = panel.dataset.tournamentStatus ?? '';
  const tType        = panel.dataset.tournamentType ?? 'LDR';
  const apiBase      = (document.querySelector('meta[name="api-base"]') as HTMLMetaElement)?.content ?? '';

  // 1. Auth check
  let meData: { authenticated?: boolean; user?: { username?: string; is_staff?: boolean } } = {};
  try {
    const res = await fetch(`${apiBase}/api/auth/me/`, { credentials: 'include' });
    if (res.ok) meData = await res.json();
  } catch { /* backend unavailable */ }

  const me = meData?.user;
  const isOrganizer = meData?.authenticated && me && (me.is_staff || me.username === createdBy);
  if (!isOrganizer) return;

  // 2. Show panel
  panel.style.display = '';

  const lockedHard = tStatus === 'FIN' || tStatus === 'CNC';
  const locked     = lockedHard || tStatus === 'SCH' || tStatus === 'DRF';

  if (lockedHard) {
    const lockedMsg = document.getElementById('org-locked-msg');
    if (lockedMsg) lockedMsg.style.display = '';
  }

  const cfg: OrgPanelConfig = {
    panel, tournamentId, createdBy, tStatus, tType,
    setsToWin: 2,       // not used for LDR but required by OrgPanelConfig type
    pointsPerMatch: 0,  // not used for LDR
    apiBase,
    isSGL: false, isDBE: false, isAMR: false,
    locked, lockedHard,
  };

  // 3. Patch status transitions label — LDR has no match generation
  // We use a monkey-patch: inject a custom data attribute so org-status reads it.
  // Simpler: just fix the label client-side after initStatusPanel renders.
  // initStatusPanel renders from TRANSITIONS constant — we override via DOM after render.
  initStatusPanel(cfg);

  // Fix "Zamknij zapisy i generuj mecze" → "Zamknij zapisy i ustaw pozycje startowe" for LDR
  requestAnimationFrame(() => {
    document.querySelectorAll<HTMLButtonElement>('.org-status-btn[data-target="SCH"]').forEach(btn => {
      if (btn.textContent?.includes('generuj mecze')) {
        btn.textContent = 'Zamknij zapisy i ustaw pozycje startowe →';
      }
    });
  });

  // 4. Seed management (DRF/REG/SCH — przed startem)
  await initLdrSeeds(cfg);

  // 5. LDR matches / score entry (only when ACT)
  await initLdrMatches(cfg);

  // 6. Config form
  initLdrConfigForm(cfg);

  // 7. Finish / cancel
  initFinishButton(cfg, async () => { /* no standings for LDR */ });

  // 8. Participants
  initParticipantsPanel(cfg);
})();
