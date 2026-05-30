// Organizer participants — CRUD, autocomplete, singiel/debel add, close registration.
import { escHtml, getCsrf, getInitials } from './helpers';
import type { OrgPanelConfig, UserItem } from './types';

function makeAutocomplete(
  inputEl: HTMLInputElement,
  dropEl: HTMLElement,
  apiBase: string,
  onSelect: (user: {id:number; display:string}) => void,
  tournamentId?: string,
  onConfirm?: () => void,
) {
  let timer: ReturnType<typeof setTimeout>;
  let abort: AbortController | null = null;
  let highlightIdx = -1;

  function getItems() {
    return Array.from(dropEl.querySelectorAll<HTMLElement>('.org-sug-item'));
  }
  function setHL(idx: number) {
    const items = getItems();
    items.forEach((el, i) => el.classList.toggle('org-sug-item--selected', i === idx));
    highlightIdx = idx;
    if (idx >= 0 && items[idx]) {
      items[idx].scrollIntoView({ block: 'nearest' });
    }
  }
  function close() {
    dropEl.style.display = 'none';
    dropEl.innerHTML = '';
    highlightIdx = -1;
  }
  function renderItems(users: UserItem[], label?: string) {
    highlightIdx = -1;
    if (!users.length) {
      dropEl.innerHTML = '<div class="org-sug-empty">Brak wyników</div>';
      dropEl.style.display = '';
      return;
    }
    const html = users.map(u => {
      const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username;
      const ini = name.split(' ').filter(Boolean).slice(0,2).map((w:string)=>w[0]).join('').toUpperCase();
      return `<div class="org-sug-item" data-uid="${u.id}" data-name="${escHtml(name)}" role="option" tabindex="-1">`
        + `<div class="org-sug-avatar">${escHtml(ini)}</div>`
        + `<div class="org-sug-info"><span class="org-sug-name">${escHtml(name)}</span>`
        + `<span class="org-sug-username">@${escHtml(u.username)}</span></div></div>`;
    }).join('');
    dropEl.innerHTML = label
      ? `<div class="org-sug-section-label">${escHtml(label)}</div>` + html
      : html;
    dropEl.style.display = '';
    dropEl.querySelectorAll<HTMLElement>('.org-sug-item').forEach(item => {
      item.addEventListener('mousedown', (e) => {
        e.preventDefault();
        onSelect({ id: Number(item.dataset.uid), display: item.dataset.name! });
        inputEl.value = item.dataset.name!;
        close();
      });
    });
    // Auto-zaznacz pierwszy wynik — Enter od razu go doda
    setHL(0);
  }

  const excludeParam = tournamentId ? `&exclude_tournament=${tournamentId}` : '';

  inputEl.addEventListener('focus', async () => {
    if (inputEl.value.trim().length >= 2 || dropEl.style.display !== 'none') return;
    try {
      const res = await fetch(`${apiBase}/api/users/?suggest=1${excludeParam}`, { credentials: 'include' });
      if (!res.ok) return;
      const users: UserItem[] = await res.json();
      if (users.length) renderItems(users, 'Ostatnio dołączyli');
    } catch { /* silent */ }
  });

  inputEl.addEventListener('input', () => {
    clearTimeout(timer);
    abort?.abort(); abort = null;
    onSelect({ id: 0, display: '' });
    const q = inputEl.value.trim();
    if (q.length < 2) { close(); if (!q) inputEl.dispatchEvent(new Event('focus')); return; }
    timer = setTimeout(async () => {
      const ctrl = new AbortController(); abort = ctrl;
      try {
        const res = await fetch(`${apiBase}/api/users/?search=${encodeURIComponent(q)}${excludeParam}`, {
          credentials: 'include', signal: ctrl.signal,
        });
        if (!res.ok || abort !== ctrl) return;
        renderItems(await res.json());
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
      }
    }, 300);
  });

  inputEl.addEventListener('keydown', (e) => {
    const items = getItems();
    if (!items.length) return;
    if (e.key === 'ArrowDown')  { e.preventDefault(); setHL(Math.min(highlightIdx+1, items.length-1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHL(Math.max(highlightIdx-1, 0)); }
    else if (e.key === 'Enter' && highlightIdx >= 0) {
      e.preventDefault();
      const item = items[highlightIdx];
      onSelect({ id: Number(item.dataset.uid), display: item.dataset.name! });
      inputEl.value = item.dataset.name!;
      close();
      if (onConfirm) onConfirm();
    } else if (e.key === 'Escape') { close(); }
  });

  inputEl.addEventListener('blur', () => setTimeout(close, 150));
}

export function initParticipantsPanel(cfg: OrgPanelConfig) {
  const { panel, tStatus, apiBase, tournamentId } = cfg;
  const listEl        = panel.querySelector<HTMLElement>('#org-participants-list');
  const msgEl         = panel.querySelector<HTMLElement>('#org-participant-msg');
  const closeRegWraps = Array.from(panel.querySelectorAll<HTMLElement>('#org-close-reg-wrap'));
  const closeRegBtns  = Array.from(panel.querySelectorAll<HTMLButtonElement>('#org-close-reg-btn'));
  const closeRegMsgs  = Array.from(panel.querySelectorAll<HTMLElement>('#org-close-reg-msg'));
  if (!listEl || !msgEl) return;

  const addRow = panel.querySelector<HTMLElement>('.org-add-row');
  const canAdd = tStatus === 'DRF' || tStatus === 'REG';
  if (addRow && !canAdd) addRow.style.display = 'none';

  const matchFormat    = panel.dataset.matchFormat ?? '';
  const tournamentType = panel.dataset.tournamentType ?? '';
  const isDoubles      = matchFormat === 'DBL';
  const isAmrDbl       = isDoubles && tournamentType === 'AMR';
  const sngWrap        = panel.querySelector<HTMLElement>('#org-add-sng-wrap');
  const dblRow         = panel.querySelector<HTMLElement>('#org-add-dbl-row');
  const amrDblNote     = panel.querySelector<HTMLElement>('#org-add-amr-dbl-note');

  if (isAmrDbl) {
    if (amrDblNote) amrDblNote.style.display = 'block';
    if (dblRow) dblRow.style.display = 'none';
  } else if (isDoubles) {
    if (sngWrap) sngWrap.style.display = 'none';
    if (dblRow)  dblRow.style.display = 'block';
  }

  type SSRParticipant = {id:number;display_name:string;seed_number:number|null;status:string};
  const ssrParticipants: SSRParticipant[] =
    JSON.parse(document.getElementById('ssr-participants-data')?.textContent ?? '[]');

  const canRemove = tStatus === 'DRF' || tStatus === 'REG' || tStatus === 'SCH';

  function updateCloseRegBtn() {
    if (!closeRegWraps.length || !panel) return;
    const currentStatus = panel.dataset.tournamentStatus ?? '';
    const activeCount = listEl!.querySelectorAll('.org-participant-row').length;
    const show = currentStatus === 'REG' && activeCount >= 2;
    closeRegWraps.forEach(w => { w.style.display = show ? 'block' : 'none'; });
  }

  function bindRemoveBtn(btn: HTMLButtonElement, row: HTMLElement) {
    btn.addEventListener('click', async () => {
      if (!confirm('Wycofać uczestnika?')) return;
      btn.disabled = true;
      const pid = btn.dataset.pid;
      try {
        const res = await fetch(`${apiBase}/api/tournaments/${tournamentId}/participants/${pid}/`, {
          method: 'DELETE', credentials: 'include',
          headers: { 'X-CSRFToken': getCsrf() },
        });
        const d = await res.json().catch(() => ({}));
        if (res.ok) {
          row.remove();
          if (!listEl!.querySelector('.org-participant-row')) {
            listEl!.innerHTML = '<div class="org-loading">Brak uczestników.</div>';
          }
          msgEl!.textContent = `Wycofano${d.display_name ? ': ' + d.display_name : ''}.`;
          msgEl!.className = 'org-form-msg org-form-msg--ok';
          updateCloseRegBtn();
          setTimeout(() => { msgEl!.textContent = ''; }, 3000);
        } else {
          msgEl!.textContent = d.detail ?? 'Błąd usuwania.';
          msgEl!.className = 'org-form-msg org-form-msg--err';
          btn.disabled = false;
        }
      } catch {
        msgEl!.textContent = 'Błąd sieci.';
        msgEl!.className = 'org-form-msg org-form-msg--err';
        btn.disabled = false;
      }
    });
  }

  function renderParticipants(list: SSRParticipant[]) {
    const active = list.filter(p => p.status !== 'WDN');
    if (!active.length) {
      listEl!.innerHTML = '<div class="org-loading">Brak uczestników.</div>';
      updateCloseRegBtn();
      return;
    }
    listEl!.innerHTML = active.map(p => `
      <div class="org-participant-row" data-pid="${p.id}">
        <div class="tc-avatar tc-avatar-sm" aria-hidden="true">
          ${escHtml(getInitials(p.display_name))}
        </div>
        <span class="org-participant-name">${escHtml(p.display_name)}</span>
        ${p.seed_number ? `<span class="td-seed">#${p.seed_number}</span>` : ''}
        ${canRemove ? `<button class="org-participant-remove" data-pid="${p.id}" type="button" title="Wycofaj uczestnika">✕</button>` : ''}
      </div>`).join('');

    listEl!.querySelectorAll<HTMLButtonElement>('.org-participant-remove').forEach(btn => {
      const row = btn.closest<HTMLElement>('.org-participant-row')!;
      bindRemoveBtn(btn, row);
    });
    updateCloseRegBtn();
  }

  renderParticipants(ssrParticipants);

  function appendParticipantRow(d: {id:number; display_name:string}) {
    const placeholder = listEl!.querySelector('.org-loading');
    if (placeholder) placeholder.remove();
    const row = document.createElement('div');
    row.className = 'org-participant-row';
    row.dataset.pid = String(d.id);
    row.innerHTML = `
      <div class="tc-avatar tc-avatar-sm" aria-hidden="true">${escHtml(getInitials(d.display_name))}</div>
      <span class="org-participant-name">${escHtml(d.display_name)}</span>
      ${canRemove ? `<button class="org-participant-remove" data-pid="${d.id}" type="button" title="Wycofaj">✕</button>` : ''}`;
    listEl!.appendChild(row);
    const removeBtn = row.querySelector<HTMLButtonElement>('.org-participant-remove');
    if (removeBtn) bindRemoveBtn(removeBtn, row);
  }

  // Singiel + AMR debel add flow
  if (!isDoubles || isAmrDbl) {
    const searchEl = panel.querySelector<HTMLInputElement>('#org-add-user-search')!;
    const sugEl    = panel.querySelector<HTMLElement>('#org-user-suggestions')!;
    const addBtn   = panel.querySelector<HTMLButtonElement>('#org-add-user-btn')!;
    let selectedUser: {id:number; display:string} | null = null;

    makeAutocomplete(
      searchEl, sugEl, apiBase,
      (u) => { selectedUser = u.id ? u : null; },
      tournamentId,
      () => addBtn.click(),
    );

    addBtn.addEventListener('click', async () => {
      if (!selectedUser) {
        msgEl!.textContent = 'Wybierz użytkownika z listy podpowiedzi.';
        msgEl!.className = 'org-form-msg org-form-msg--err';
        searchEl.focus(); return;
      }
      addBtn.disabled = true;
      try {
        const res = await fetch(`${apiBase}/api/tournaments/${tournamentId}/participants/`, {
          method: 'POST', credentials: 'include',
          headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: selectedUser.id }),
        });
        const d = await res.json().catch(() => ({}));
        if (res.ok) {
          appendParticipantRow(d);
          msgEl!.textContent = `Dodano: ${d.display_name}`;
          msgEl!.className = 'org-form-msg org-form-msg--ok';
          searchEl.value = ''; selectedUser = null;
          updateCloseRegBtn();
          setTimeout(() => { msgEl!.textContent = ''; }, 3000);
        } else {
          msgEl!.textContent = d.detail ?? 'Błąd dodawania.';
          msgEl!.className = 'org-form-msg org-form-msg--err';
        }
      } catch {
        msgEl!.textContent = 'Błąd sieci.'; msgEl!.className = 'org-form-msg org-form-msg--err';
      }
      addBtn.disabled = false;
    });
  }

  // Debel add flow
  if (isDoubles) {
    const p1El      = panel.querySelector<HTMLInputElement>('#org-add-p1-search')!;
    const p1SugEl   = panel.querySelector<HTMLElement>('#org-p1-suggestions')!;
    const p2El      = panel.querySelector<HTMLInputElement>('#org-add-p2-search')!;
    const p2SugEl   = panel.querySelector<HTMLElement>('#org-p2-suggestions')!;
    const nameEl    = panel.querySelector<HTMLInputElement>('#org-add-dbl-name')!;
    const dblAddBtn = panel.querySelector<HTMLButtonElement>('#org-add-dbl-btn')!;

    let p1: {id:number; display:string} | null = null;
    let p2: {id:number; display:string} | null = null;
    let nameManuallyEdited = false;

    function autoFillName() {
      if (nameManuallyEdited) return;
      const parts: string[] = [];
      if (p1?.display) parts.push(p1.display.split(' ').pop() ?? p1.display);
      if (p2?.display) parts.push(p2.display.split(' ').pop() ?? p2.display);
      nameEl.value = parts.join(' / ');
    }

    nameEl.addEventListener('input', () => {
      nameManuallyEdited = nameEl.value.trim() !== '';
    });
    nameEl.addEventListener('change', () => {
      if (!nameEl.value.trim()) nameManuallyEdited = false;
    });

    makeAutocomplete(p1El, p1SugEl, apiBase, (u) => {
      p1 = u.id ? u : null;
      autoFillName();
    }, tournamentId);
    makeAutocomplete(p2El, p2SugEl, apiBase, (u) => {
      p2 = u.id ? u : null;
      autoFillName();
    }, tournamentId);

    dblAddBtn.addEventListener('click', async () => {
      if (!p1?.id) {
        msgEl!.textContent = 'Wybierz Gracza 1.'; msgEl!.className = 'org-form-msg org-form-msg--err';
        p1El.focus(); return;
      }
      const pairName = nameEl.value.trim();
      if (!pairName) {
        msgEl!.textContent = 'Wpisz nazwę pary.'; msgEl!.className = 'org-form-msg org-form-msg--err';
        nameEl.focus(); return;
      }
      dblAddBtn.disabled = true;
      try {
        const body: Record<string, unknown> = {
          user_id: p1.id,
          display_name: pairName,
        };
        if (p2?.id) body.partner_user_id = p2.id;

        const res = await fetch(`${apiBase}/api/tournaments/${tournamentId}/participants/`, {
          method: 'POST', credentials: 'include',
          headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const d = await res.json().catch(() => ({}));
        if (res.ok) {
          appendParticipantRow(d);
          msgEl!.textContent = `Dodano parę: ${d.display_name}`;
          msgEl!.className = 'org-form-msg org-form-msg--ok';
          p1El.value = ''; p2El.value = ''; nameEl.value = '';
          p1 = null; p2 = null; nameManuallyEdited = false;
          updateCloseRegBtn();
          setTimeout(() => { msgEl!.textContent = ''; }, 3000);
        } else {
          msgEl!.textContent = d.detail ?? 'Błąd dodawania.';
          msgEl!.className = 'org-form-msg org-form-msg--err';
        }
      } catch {
        msgEl!.textContent = 'Błąd sieci.'; msgEl!.className = 'org-form-msg org-form-msg--err';
      }
      dblAddBtn.disabled = false;
    });
  }

  // Close registration buttons
  closeRegBtns.forEach((btn, i) => {
    const closeMsgEl = closeRegMsgs[i] ?? closeRegMsgs[0] ?? null;
    btn.addEventListener('click', async () => {
      if (!window.confirm('Zamknąć zapisy i wygenerować mecze? Tej operacji nie można cofnąć bez utraty meczów.')) return;
      closeRegBtns.forEach(b => { b.disabled = true; });
      if (closeMsgEl) { closeMsgEl.textContent = 'Generowanie…'; closeMsgEl.className = 'org-form-msg'; }
      try {
        const res = await fetch(`${apiBase}/api/tournaments/${tournamentId}/status/`, {
          method: 'PATCH', credentials: 'include',
          headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'SCH' }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          window.location.reload();
        } else {
          if (closeMsgEl) {
            closeMsgEl.textContent = data.detail ?? `Błąd ${res.status}`;
            closeMsgEl.className = 'org-form-msg org-form-msg--err';
          }
          closeRegBtns.forEach(b => { b.disabled = false; });
        }
      } catch {
        if (closeMsgEl) { closeMsgEl.textContent = 'Błąd sieci.'; closeMsgEl.className = 'org-form-msg org-form-msg--err'; }
        closeRegBtns.forEach(b => { b.disabled = false; });
      }
    });
  });
}
