// org-ldr-seeds.ts — Seed management dla organizatora turnieju LDR.
//
// Organizer widzi listę uczestników z ich pozycjami (seed_number).
// Może:
//   - kliknąć "Zamień" przy dwóch uczestnikach → POST /ladder/seeds/ (swap)
//   - edytować seed_number bezpośrednio w polu input → PATCH /ladder/seeds/
//
// Sekcja widoczna gdy tStatus ∈ {DRF, REG, SCH} (przed ACT).
// Po ACT pozycje zmieniają się tylko przez wyzwania.

import { escHtml, getCsrf, getInitials } from './helpers';
import type { OrgPanelConfig } from './types';

type SeedParticipant = {
  id: number;
  display_name: string;
  seed_number: number | null;
  status: string;
};

async function fetchParticipants(cfg: OrgPanelConfig): Promise<SeedParticipant[]> {
  try {
    const res = await fetch(
      `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/ladder/`,
      { credentials: 'include' },
    );
    if (!res.ok) return [];
    const data = await res.json();
    return (data.ranking ?? []) as SeedParticipant[];
  } catch {
    return [];
  }
}

function renderSeeds(
  cfg: OrgPanelConfig,
  container: HTMLElement,
  msgEl: HTMLElement,
  participants: SeedParticipant[],
  onRefresh: () => Promise<void>,
) {
  if (!participants.length) {
    container.innerHTML = '<div class="org-loading">Brak uczestników.</div>';
    return;
  }

  // Sortuj: mający seed na górze (rosnąco), bez seedu na dole
  const sorted = [...participants].sort((a, b) => {
    if (a.seed_number == null && b.seed_number == null) return 0;
    if (a.seed_number == null) return 1;
    if (b.seed_number == null) return -1;
    return a.seed_number - b.seed_number;
  });

  container.innerHTML = `
    <div class="org-seed-list">
      ${sorted.map(p => `
        <div class="org-seed-row" data-pid="${p.id}">
          <div class="org-seed-pos">
            <input
              class="org-seed-input"
              type="number"
              min="1"
              max="${sorted.length}"
              value="${p.seed_number ?? ''}"
              placeholder="—"
              data-pid="${p.id}"
              data-original="${p.seed_number ?? ''}"
              ${cfg.lockedHard ? 'disabled' : ''}
            >
          </div>
          <div class="tc-avatar tc-avatar-sm" aria-hidden="true">${escHtml(getInitials(p.display_name))}</div>
          <span class="org-seed-name">${escHtml(p.display_name)}</span>
          <div class="org-seed-actions">
            ${!cfg.lockedHard ? `
              <button class="org-seed-save-btn" data-pid="${p.id}" type="button" style="display:none;">Zapisz</button>
              <button class="org-seed-swap-btn" data-pid="${p.id}" type="button" title="Zaznacz do zamiany pozycji">Zamień</button>
            ` : ''}
          </div>
        </div>
      `).join('')}
    </div>
    ${!cfg.lockedHard ? `
      <div class="org-seed-hint">
        <strong>Zamień:</strong> kliknij „Zamień" przy dwóch uczestnikach, żeby zamienić ich pozycje.
        <strong>Edytuj:</strong> zmień liczbę w polu i kliknij „Zapisz".
      </div>
    ` : ''}
  `;

  // ── Inline edit: pokaż "Zapisz" gdy wartość się zmieni ───────────────────
  container.querySelectorAll<HTMLInputElement>('.org-seed-input').forEach(input => {
    const pid = input.dataset.pid!;
    const saveBtn = container.querySelector<HTMLButtonElement>(`.org-seed-save-btn[data-pid="${pid}"]`);

    input.addEventListener('input', () => {
      const changed = input.value !== (input.dataset.original ?? '');
      if (saveBtn) saveBtn.style.display = changed ? '' : 'none';
    });

    saveBtn?.addEventListener('click', async () => {
      const newSeed = parseInt(input.value, 10);
      if (!newSeed || newSeed < 1) {
        showMsg(msgEl, 'seed_number musi być ≥ 1.', 'err');
        return;
      }
      saveBtn.disabled = true;
      saveBtn.textContent = '…';
      msgEl.textContent = '';
      msgEl.className = 'org-form-msg';

      try {
        const res = await fetch(
          `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/ladder/seeds/`,
          {
            method: 'PATCH',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({ participant_id: parseInt(pid, 10), seed_number: newSeed }),
          },
        );
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          showMsg(msgEl, `Zapisano pozycję ${data.seed_number} dla „${data.display_name}".`, 'ok');
          await onRefresh();
        } else {
          showMsg(msgEl, data.detail ?? `Błąd ${res.status}`, 'err');
          saveBtn.disabled = false;
          saveBtn.textContent = 'Zapisz';
        }
      } catch {
        showMsg(msgEl, 'Błąd sieci.', 'err');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Zapisz';
      }
    });
  });

  // ── Swap: zaznacz pierwszego, potem drugiego → wyślij swap ───────────────
  let swapCandidate: { pid: string; row: HTMLElement; btn: HTMLButtonElement } | null = null;

  container.querySelectorAll<HTMLButtonElement>('.org-seed-swap-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const pid = btn.dataset.pid!;
      const row = btn.closest<HTMLElement>('.org-seed-row')!;

      if (!swapCandidate) {
        // Pierwszy wybór — zaznacz
        swapCandidate = { pid, row, btn };
        row.classList.add('org-seed-row--selected');
        btn.textContent = 'Anuluj';
        btn.classList.add('org-seed-swap-btn--active');
        showMsg(msgEl, 'Wybierz drugiego uczestnika do zamiany pozycji.', 'ok');
        return;
      }

      if (swapCandidate.pid === pid) {
        // Klik na tego samego — anuluj
        swapCandidate.row.classList.remove('org-seed-row--selected');
        swapCandidate.btn.textContent = 'Zamień';
        swapCandidate.btn.classList.remove('org-seed-swap-btn--active');
        swapCandidate = null;
        msgEl.textContent = '';
        return;
      }

      // Drugi wybór — wykonaj swap
      const a = swapCandidate;
      swapCandidate = null;
      a.row.classList.remove('org-seed-row--selected');
      a.btn.textContent = 'Zamień';
      a.btn.classList.remove('org-seed-swap-btn--active');

      // Dezaktywuj oba przyciski na czas operacji
      a.btn.disabled = true;
      btn.disabled = true;
      msgEl.textContent = '';
      msgEl.className = 'org-form-msg';

      try {
        const res = await fetch(
          `${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/ladder/seeds/`,
          {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
            body: JSON.stringify({
              participant_a_id: parseInt(a.pid, 10),
              participant_b_id: parseInt(pid, 10),
            }),
          },
        );
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          const na = data.participant_a?.display_name ?? '?';
          const nb = data.participant_b?.display_name ?? '?';
          const sa = data.participant_a?.seed_number ?? '—';
          const sb = data.participant_b?.seed_number ?? '—';
          showMsg(msgEl, `Zamieniono: „${na}" (#${sb}) ↔ „${nb}" (#${sa})`, 'ok');
          await onRefresh();
        } else {
          showMsg(msgEl, data.detail ?? `Błąd ${res.status}`, 'err');
          a.btn.disabled = false;
          btn.disabled = false;
        }
      } catch {
        showMsg(msgEl, 'Błąd sieci.', 'err');
        a.btn.disabled = false;
        btn.disabled = false;
      }
    });
  });
}

function showMsg(el: HTMLElement, text: string, type: 'ok' | 'err') {
  el.textContent = text;
  el.className = `org-form-msg org-form-msg--${type}`;
  if (type === 'ok') setTimeout(() => { if (el.textContent === text) el.textContent = ''; }, 5000);
}

export async function initLdrSeeds(cfg: OrgPanelConfig) {
  const section = document.getElementById('org-ldr-seeds-section');
  if (!section) return;

  // FIN/CNC — nie pokazujemy
  if (cfg.lockedHard) return;

  // W ACT normalnie seedy zmieniają się przez wyzwania.
  // Wyjątek: jeśli są uczestnicy bez seed_number (błąd inicjalizacji) — pozwól naprawić.
  // Sprawdzimy to po pobraniu uczestników poniżej.
  const isAct = cfg.tStatus === 'ACT';

  const container = document.getElementById('org-ldr-seeds-list');
  const msgEl     = document.getElementById('org-ldr-seeds-msg');
  if (!container || !msgEl) return;

  let participants: SeedParticipant[] = [];

  const refresh = async () => {
    participants = await fetchParticipants(cfg);

    // W ACT: pokaż sekcję tylko gdy ktoś nie ma seedu (naprawczy edge case)
    if (isAct) {
      const hasMissing = participants.some(p => p.seed_number == null);
      if (!hasMissing) return; // wszystko OK — nie pokazuj
      section.style.display = '';
      // Dodaj ostrzeżenie na górze sekcji
      const label = section.querySelector('.org-section-label');
      if (label && !section.querySelector('.org-seed-warn')) {
        const warn = document.createElement('div');
        warn.className = 'org-seed-warn';
        warn.style.cssText = 'font-size:0.78rem;color:var(--tc-warning,#b45309);margin-bottom:8px;';
        warn.textContent = 'Turniej jest aktywny, ale niektórzy uczestnicy nie mają przypisanych pozycji — uzupełnij je, żeby challenge flow działał poprawnie.';
        label.after(warn);
      }
    } else {
      section.style.display = '';
    }

    renderSeeds(cfg, container, msgEl, participants, refresh);
  };

  await refresh();
}
