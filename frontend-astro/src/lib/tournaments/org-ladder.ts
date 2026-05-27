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
//   loadLdrChallenges  — fetches active challenges, displays them in org view
//   LDR status panel uses custom TRANSITIONS (no "generuj mecze" label)

import type { OrgPanelConfig } from './types';
import { initStatusPanel }      from './org-status';
import { initFinishButton }     from './org-finish';
import { initParticipantsPanel } from './org-participants';
import { initLdrConfigForm }    from './org-config-ldr';
import { escHtml }              from './helpers';

// ── Custom status transitions for LDR ────────────────────────────────────────
// Override: REG→SCH should say "Zamknij zapisy" not "generuj mecze" (no bracket).
// We patch org-status TRANSITIONS after initStatusPanel mounts by re-rendering,
// but it's cleaner to export a small helper used only here.

async function loadLdrChallenges(cfg: OrgPanelConfig) {
  const section = document.getElementById('org-ldr-challenges-section');
  const listEl  = document.getElementById('org-ldr-challenges-list');
  if (!section || !listEl) return;

  // Only show when ACT
  if (cfg.tStatus !== 'ACT') return;
  section.style.display = '';

  try {
    const res = await fetch(
      `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/ladder/`,
      { credentials: 'include' }
    );
    if (!res.ok) { listEl.textContent = 'Błąd ładowania wyzwań.'; return; }
    const data = await res.json();

    const challenges: Array<{
      match_id: number;
      status: string;
      challenger: { id: number | null; display_name: string | null };
      challenged: { id: number | null; display_name: string | null };
      scheduled_time: string | null;
    }> = data.active_challenges ?? [];

    if (!challenges.length) {
      listEl.innerHTML = '<span style="font-size:0.84rem;color:var(--tc-muted);">Brak aktywnych wyzwań.</span>';
      return;
    }

    const STATUS_LABEL: Record<string, string> = {
      SCH: 'Oczekuje na akceptację',
      INP: 'W trakcie',
      WAI: 'Oczekuje',
    };
    const STATUS_CLS: Record<string, string> = {
      SCH: 'ldr-status-sch',
      INP: 'ldr-status-inp',
      WAI: 'ldr-status-sch',
    };

    listEl.innerHTML = challenges.map(ch => `
      <div class="ldr-challenge-card" style="margin-bottom:8px;">
        <div class="ldr-challenge-card__info">
          <div class="ldr-challenge-card__title">
            ${escHtml(ch.challenger.display_name ?? '—')}
            <span style="font-weight:400;color:var(--tc-muted);margin:0 4px;">vs</span>
            ${escHtml(ch.challenged.display_name ?? '—')}
          </div>
          <div class="ldr-challenge-card__meta">
            <span class="ldr-status-badge ${STATUS_CLS[ch.status] ?? ''}">${escHtml(STATUS_LABEL[ch.status] ?? ch.status)}</span>
            ${ch.scheduled_time
              ? `<span style="margin-left:8px;font-size:0.78rem;color:var(--tc-sub);">${escHtml(
                  new Date(ch.scheduled_time).toLocaleDateString('pl-PL', {
                    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                  })
                )}</span>`
              : ''}
          </div>
        </div>
      </div>
    `).join('');
  } catch {
    listEl.textContent = 'Błąd sieci.';
  }
}

// ── Main entry point ──────────────────────────────────────────────────────────
(async () => {
  const panel = document.getElementById('org-panel-ldr') as HTMLElement | null;
  if (!panel) return;

  const tournamentId   = panel.dataset.tournamentId ?? '';
  const createdBy      = panel.dataset.createdBy ?? '';
  const tStatus        = panel.dataset.tournamentStatus ?? '';
  const tType          = panel.dataset.tournamentType ?? 'LDR';
  const matchFormat    = panel.dataset.matchFormat ?? 'SNG';
  const apiBase        = (document.querySelector('meta[name="api-base"]') as HTMLMetaElement)?.content ?? '';

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

  // 4. Active challenges (only when ACT)
  await loadLdrChallenges(cfg);

  // 5. Config form
  initLdrConfigForm(cfg);

  // 6. Finish / cancel
  initFinishButton(cfg, async () => { /* no standings for LDR */ });

  // 7. Participants
  initParticipantsPanel(cfg);
})();
