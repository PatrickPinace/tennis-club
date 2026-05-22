// Organizer standings — load and render standings for RR and AMR tournaments.
import { escHtml } from './helpers';
import type { OrgPanelConfig, StandingsRowRR } from './types';

export function renderStandingsRows(rows: StandingsRowRR[]) {
  const tbody = document.getElementById('org-standings-body');
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="org-loading">Brak danych standings.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td style="text-align:center;font-weight:700;">${r.position}</td>
      <td>${escHtml(r.display_name)}</td>
      <td class="col-num" style="font-weight:700;">${Number(r.points).toFixed(1).replace('.0','')}</td>
      <td class="col-num">${r.matches_played}</td>
      <td class="col-num">${r.wins}</td>
      <td class="col-num">${r.losses}</td>
      <td class="col-num">${r.win_rate != null ? r.win_rate + '%' : '—'}</td>
      <td class="col-num">${r.sets_won}:${r.sets_lost}</td>
    </tr>`).join('');
}

export async function loadStandings(cfg: OrgPanelConfig) {
  const tbody = document.getElementById('org-standings-body');
  if (!tbody) return;
  try {
    const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/standings/`, { credentials: 'include' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const rows = await res.json();
    renderStandingsRows(rows);
  } catch {
    const tbody2 = document.getElementById('org-standings-body');
    if (tbody2) tbody2.innerHTML = '<tr><td colspan="8" class="org-loading">Błąd ładowania tabeli.</td></tr>';
  }
}

export async function loadAmericanoStandings(cfg: OrgPanelConfig) {
  const tbody = document.getElementById('amr-standings-body');
  if (!tbody) return;
  try {
    const res = await fetch(`${cfg.apiBase}/api/tournaments/${cfg.tournamentId}/detail/`, { credentials: 'include' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rows: Array<{ participant_id: number; display_name: string; points: number; matches_played: number }> =
      data.standings ?? [];
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:12px;color:var(--text-dim);">Brak wyników.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map((r, idx) => `
      <tr>
        <td><span class="rank-pos${idx < 3 ? ` rank-pos--${idx + 1}` : ''}">${idx + 1}</span></td>
        <td><div class="td-player">
          <div class="tc-avatar tc-avatar-sm" aria-hidden="true">
            ${escHtml(r.display_name.split(' ').filter(Boolean).slice(0, 2).map(w => w[0]).join(''))}
          </div>
          <span class="td-player__name">${escHtml(r.display_name)}</span>
        </div></td>
        <td class="col-num td-pts">${r.points}</td>
        <td class="col-num col-muted">${r.matches_played}</td>
      </tr>`).join('');
  } catch {
    if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="org-loading">Błąd ładowania tabeli.</td></tr>';
  }
}
