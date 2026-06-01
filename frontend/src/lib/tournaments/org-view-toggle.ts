// Organizer view toggle — list/matrix view switch.
import type { OrgPanelConfig } from './types';
import type { MatchState } from './org-matches';
import { buildMatrix } from './org-matrix';

export function initViewToggle(cfg: OrgPanelConfig, state: MatchState) {
  const toggle = document.getElementById('matches-view-toggle');
  if (!toggle) return;

  const roundEls  = document.querySelectorAll<HTMLElement>('.td-round');
  const matrixWrap = document.getElementById('rr-matrix-wrap');
  if (!matrixWrap) return;

  let matrixBuilt = false;

  toggle.querySelectorAll<HTMLButtonElement>('.view-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      toggle.querySelectorAll('.view-toggle__btn').forEach(b => b.classList.remove('view-toggle__btn--active'));
      btn.classList.add('view-toggle__btn--active');

      if (view === 'matrix') {
        roundEls.forEach(el => el.style.display = 'none');
        matrixWrap.style.display = '';
        if (!matrixBuilt) { buildMatrix(cfg, state); matrixBuilt = true; }
      } else {
        roundEls.forEach(el => el.style.display = '');
        matrixWrap.style.display = 'none';
      }
    });
  });
}
