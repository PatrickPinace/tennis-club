import { useState, useRef, useEffect, useCallback, useMemo } from 'react';

/* ── Types ─────────────────────────────────────────────────────────────────── */

interface MyReservation {
  id: number;
  courtId: number | null;
  court: string;
  facility: string;
  date: string;
  time: string;
  startIso: string;
  endIso: string;
  status: 'pending' | 'confirmed' | 'rejected';
  seriesId: string | null;
}

interface PendingEntry {
  id: number;
  court_name: string | null;
  facility_name: string | null;
  start_time: string;
  end_time: string;
  status: string;
  user_name: string;
}

interface SlotData {
  time: string;
  status: string;
  is_mine: boolean;
}

interface CourtData {
  id: number;
  name: string;
  surface: string | null;
  slots: SlotData[];
}

interface TimelineData {
  courts: CourtData[];
}

interface PopupSlot {
  courtId: number;
  courtName: string;
  date: string;
  startTime: string;
  endTime: string;
}

interface Facility {
  id: number;
  name: string;
}

interface EditTarget {
  reservationId: number;
  seriesId: string | null;
  startTime: string; // HH:MM
  endTime: string;   // HH:MM
  courtId: number;
}

interface Props {
  initialReservations: MyReservation[];
  pendingReservations: PendingEntry[];
  isManager: boolean;
  futureCount: number;
  totalCount: number;
  gridStart: number;
  gridEnd: number;
  todayIso: string;
}

/* ── Helpers ───────────────────────────────────────────────────────────────── */

function getCsrf(): string {
  return document.cookie
    .split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

function addMinutes(time: string, min: number): string {
  const [h, m] = time.split(':').map(Number);
  const total = h * 60 + m + min;
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function timeToMin(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

function isoFromDate(d: Date): string { return d.toISOString().slice(0, 10); }

const DAY_NAMES_LONG = ['Niedziela','Poniedziałek','Wtorek','Środa','Czwartek','Piątek','Sobota'];
const DAY_NAMES_SHORT = ['niedz.','pon.','wt.','śr.','czw.','pt.','sob.'];
const MONTH_NAMES = ['stycznia','lutego','marca','kwietnia','maja','czerwca','lipca','sierpnia','września','października','listopada','grudnia'];

function fmtDateLabel(iso: string): string {
  try { return new Date(iso + 'T12:00:00').toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' }); }
  catch { return iso; }
}

function fmtDateShort(iso: string): string {
  try { return new Date(iso).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return iso; }
}

function fmtTimeStr(iso: string): string {
  try { return new Date(iso).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
}

function fmtDateTime(iso: string): string {
  try { return new Date(iso).toLocaleString('pl-PL', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
}

function buildSlots(gridStart: number, gridEnd: number): string[] {
  const slots: string[] = [];
  for (let h = gridStart; h < gridEnd; h++) {
    slots.push(`${String(h).padStart(2, '0')}:00`);
    slots.push(`${String(h).padStart(2, '0')}:30`);
  }
  return slots;
}

function buildWeekDays(offset: number): { iso: string; label: string; sub: string; isToday: boolean; isPast: boolean }[] {
  const today = new Date();
  const todayStr = isoFromDate(today);
  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() + offset * 7 + i);
    const iso = isoFromDate(d);
    days.push({
      iso,
      label: iso === todayStr ? 'Dziś' : DAY_NAMES_LONG[d.getDay()],
      sub: `${DAY_NAMES_SHORT[d.getDay()]} ${d.getDate()}`,
      isToday: iso === todayStr,
      isPast: iso < todayStr,
    });
  }
  return days;
}

/* ── Sub-components ────────────────────────────────────────────────────────── */

function Toast({ message, type, visible }: { message: string; type: string; visible: boolean }) {
  if (!visible) return null;
  const icons: Record<string, string> = { success: '✓', error: '✕', warning: '⚠' };
  return (
    <div className={`res-toast res-toast--${type}`} role="alert" aria-live="polite">
      <span className="res-toast__icon">{icons[type] ?? ''}</span>
      <span>{message}</span>
    </div>
  );
}

function ReservationPopup({
  slot,
  onClose,
  onConfirm,
  loading,
  error,
}: {
  slot: PopupSlot | null;
  onClose: () => void;
  onConfirm: (recurring: boolean, weeks: number) => void;
  loading: boolean;
  error: { msg: string; type: 'error' | 'conflict' } | null;
}) {
  const [recurring, setRecurring] = useState(false);
  const [weeks, setWeeks] = useState(4);

  useEffect(() => {
    if (slot) {
      setRecurring(false);
      setWeeks(4);
    }
  }, [slot]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!slot) return null;

  const dur = timeToMin(slot.endTime) - timeToMin(slot.startTime);
  const dateStr = fmtDateLabel(slot.date);

  return (
    <div className="res-popup-backdrop" role="dialog" aria-modal="true" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="res-popup">
        <div className="res-popup__header">
          <div>
            <div className="res-popup__title">Rezerwacja kortu</div>
            <div className="res-popup__subtitle">Sprawdź szczegóły i potwierdź</div>
          </div>
          <button className="res-popup__close" aria-label="Zamknij" onClick={onClose}>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/></svg>
          </button>
        </div>
        <div className="res-popup__detail">
          <div className="res-popup__row"><span className="res-popup__row-icon">🎾</span><span className="res-popup__row-label">Kort</span><span className="res-popup__row-value">{slot.courtName}</span></div>
          <div className="res-popup__row"><span className="res-popup__row-icon">📅</span><span className="res-popup__row-label">Data</span><span className="res-popup__row-value">{dateStr}</span></div>
          <div className="res-popup__row"><span className="res-popup__row-icon">⏰</span><span className="res-popup__row-label">Godzina</span><span className="res-popup__row-value">{slot.startTime}–{slot.endTime}<span className="res-popup__duration">{dur} min</span></span></div>
        </div>
        <div className="res-popup__recurring">
          <label className="recurring-toggle">
            <input type="checkbox" checked={recurring} onChange={e => setRecurring(e.target.checked)} />
            <span className="recurring-toggle__label">Rezerwacja cykliczna (co tydzień)</span>
          </label>
          {recurring && (
            <div className="recurring-weeks-row" style={{ marginTop: 10 }}>
              <label className="recurring-weeks-label" htmlFor="res-recurring-weeks">Liczba tygodni:</label>
              <select id="res-recurring-weeks" className="recurring-weeks-select" value={weeks} onChange={e => setWeeks(Number(e.target.value))}>
                <option value={2}>2 tygodnie</option>
                <option value={3}>3 tygodnie</option>
                <option value={4}>4 tygodnie</option>
                <option value={6}>6 tygodni</option>
                <option value={8}>8 tygodni</option>
                <option value={12}>12 tygodni</option>
              </select>
            </div>
          )}
        </div>
        <div className="res-popup__notice">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd"/></svg>
          Rezerwacja będzie oczekiwać na zatwierdzenie przez właściciela obiektu.
        </div>
        <div className="res-popup__actions">
          <button className="tr-btn-primary" style={{ flex: 1, padding: '10px 18px' }} disabled={loading} onClick={() => onConfirm(recurring, weeks)}>
            {loading ? (recurring ? 'Rezerwuję serię…' : 'Rezerwuję…') : 'Zarezerwuj'}
          </button>
          <button className="rv-action-ghost" onClick={onClose}>Anuluj</button>
        </div>
        {error && (
          <div className={`res-popup__msg res-popup__msg--${error.type}`} role="alert">
            <span>{error.type === 'conflict' ? '⚠' : '✕'}</span> {error.msg}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Grid row (single court) ───────────────────────────────────────────── */

function CourtRow({
  court,
  allSlots,
  currentDate,
  todayIso,
  onSlotSelect,
}: {
  court: CourtData;
  allSlots: string[];
  currentDate: string;
  todayIso: string;
  onSlotSelect: (slot: PopupSlot) => void;
}) {
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragEnd, setDragEnd] = useState<number | null>(null);
  const isDragging = useRef(false);

  function isSlotPast(time: string): boolean {
    if (currentDate > todayIso) return false;
    if (currentDate < todayIso) return true;
    const now = new Date();
    const [sh, sm] = time.split(':').map(Number);
    const slotDate = new Date(todayIso + 'T00:00:00');
    slotDate.setHours(sh, sm, 0, 0);
    return slotDate <= now;
  }

  function slotState(s: SlotData | undefined): string {
    if (!s) return 'past';
    if (s.is_mine) return 'mine';
    if (s.status !== 'FREE') return 'taken';
    if (isSlotPast(s.time)) return 'past';
    return 'free';
  }

  const freeIndices = useMemo(() => {
    const indices: number[] = [];
    court.slots.forEach((s, i) => { if (slotState(s) === 'free') indices.push(i); });
    return indices;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [court.slots, currentDate]);

  const handleMouseDown = (idx: number) => {
    isDragging.current = true;
    setDragStart(idx);
    setDragEnd(idx);
  };

  const handleMouseMove = (idx: number) => {
    if (!isDragging.current) return;
    setDragEnd(idx);
  };

  const handleMouseUp = () => {
    if (!isDragging.current || dragStart === null || dragEnd === null) return;
    isDragging.current = false;

    const lo = Math.min(dragStart, dragEnd);
    const hi = Math.max(dragStart, dragEnd);
    const startSlot = court.slots[lo];
    const endSlot = court.slots[hi];
    if (startSlot && endSlot) {
      onSlotSelect({
        courtId: court.id,
        courtName: court.name,
        date: currentDate,
        startTime: startSlot.time,
        endTime: addMinutes(endSlot.time, 30),
      });
    }
    setDragStart(null);
    setDragEnd(null);
  };

  useEffect(() => {
    const handler = () => {
      if (isDragging.current) {
        isDragging.current = false;
        setDragStart(null);
        setDragEnd(null);
      }
    };
    document.addEventListener('mouseup', handler);
    return () => document.removeEventListener('mouseup', handler);
  }, []);

  const isInDragRange = (idx: number): boolean => {
    if (dragStart === null || dragEnd === null) return false;
    const lo = Math.min(dragStart, dragEnd);
    const hi = Math.max(dragStart, dragEnd);
    return idx >= lo && idx <= hi && freeIndices.includes(idx);
  };

  const cols = allSlots.length;
  const colTemplate = `120px repeat(${cols}, minmax(34px, 1fr))`;

  return (
    <div
      className="rv-court-row"
      style={{ display: 'grid', gridTemplateColumns: colTemplate }}
      data-court-id={court.id}
      onMouseUp={handleMouseUp}
    >
      <div className="rv-court-label">
        <div className="rv-court-label__name">{court.name}</div>
        <div className="rv-court-label__surface">{court.surface ?? ''}</div>
      </div>
      {court.slots.map((s, idx) => {
        const st = slotState(s);
        const isHalf = s.time.endsWith(':30');
        const extraClass = isHalf ? ' rv-slot--half' : ' rv-slot--hour';
        const isDrag = isInDragRange(idx);

        if (st === 'free') {
          const endTime = addMinutes(s.time, 30);
          return (
            <div
              key={idx}
              className={`rv-slot rv-slot--free${extraClass}${isDrag ? ' rv-slot--drag' : ''}`}
              role="button"
              tabIndex={0}
              title={`${s.time}–${endTime}`}
              onMouseDown={() => handleMouseDown(idx)}
              onMouseMove={() => handleMouseMove(idx)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSlotSelect({
                    courtId: court.id,
                    courtName: court.name,
                    date: currentDate,
                    startTime: s.time,
                    endTime,
                  });
                }
              }}
            />
          );
        }

        const label = st === 'mine' ? 'TY' : st === 'taken' ? '×' : '';
        return (
          <div
            key={idx}
            className={`rv-slot rv-slot--${st}${extraClass}`}
            title={st === 'mine' ? `Twoja rezerwacja ${s.time}` : st === 'taken' ? `Zajęty ${s.time}` : ''}
          >
            {label}
          </div>
        );
      })}
    </div>
  );
}

/* ── Manager panel ─────────────────────────────────────────────────────── */

function ManagerPanel({
  reservations: initial,
  onRefresh,
}: {
  reservations: PendingEntry[];
  onRefresh: () => void;
}) {
  const [items, setItems] = useState(initial);
  const [toastMsg, setToastMsg] = useState('');

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3000);
  };

  const handleAction = async (resId: number, action: 'approve' | 'reject') => {
    try {
      const res = await fetch(`/api/courts/reservations/${resId}/status/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        setItems(prev => prev.filter(r => r.id !== resId));
        showToast(action === 'approve' ? 'Zatwierdzona.' : 'Odrzucona.');
        onRefresh();
      } else {
        showToast('Błąd.');
      }
    } catch {
      showToast('Brak połączenia.');
    }
  };

  if (items.length === 0) return null;

  return (
    <section className="rv-manager" id="owner-section">
      <div className="rv-manager__header">
        <span className="rv-manager__title">Oczekujące rezerwacje</span>
        <span className="rv-manager__badge">{items.length} oczekuje</span>
      </div>
      <div className="owner-res-list">
        {items.map(r => (
          <div key={r.id} className="rv-manager-row">
            <div className="rv-manager-row__info">
              <div className="rv-manager-row__who">{r.user_name}</div>
              <div className="rv-manager-row__what">{r.court_name ?? 'Kort'}{r.facility_name && ` · ${r.facility_name}`}</div>
              <div className="rv-manager-row__when">{fmtDateTime(r.start_time)}–{fmtTimeStr(r.end_time)}</div>
            </div>
            <div className="rv-manager-row__actions">
              <button className="tr-btn-primary" style={{ padding: '6px 14px', fontSize: '0.78rem' }} onClick={() => handleAction(r.id, 'approve')}>Zatwierdź</button>
              <button className="rv-action-ghost" onClick={() => handleAction(r.id, 'reject')}>Odrzuć</button>
            </div>
          </div>
        ))}
      </div>
      {toastMsg && <Toast message={toastMsg} type="success" visible />}
    </section>
  );
}

/* ── My reservations list ──────────────────────────────────────────────── */

function MyReservationsList({
  reservations,
  onCancelled,
  onEdit,
  showToast: toastFn,
}: {
  reservations: MyReservation[];
  onCancelled: () => void;
  onEdit: (target: EditTarget) => void;
  showToast: (msg: string, type: string) => void;
}) {
  const [cancelConfirmId, setCancelConfirmId] = useState<number | null>(null);

  const now = new Date();
  const future = reservations.filter(r => new Date(r.endIso) > now);

  const badgeConfig = (status: string, isFuture: boolean) => {
    if (status === 'confirmed') return { cls: 'rv-badge--confirmed', label: 'potwierdzona', canCancel: isFuture };
    if (status === 'rejected') return { cls: 'rv-badge--rejected', label: 'odrzucona', canCancel: false };
    return { cls: 'rv-badge--pending', label: 'oczekuje', canCancel: isFuture };
  };

  const cancelSingle = async (resId: number) => {
    try {
      const res = await fetch(`/api/courts/reservations/${resId}/`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf() },
      });
      if (res.ok || res.status === 204) {
        setCancelConfirmId(null);
        toastFn('Rezerwacja anulowana.', 'success');
        onCancelled();
      } else {
        const d = await res.json().catch(() => ({}));
        toastFn(d.detail || 'Błąd.', 'error');
        setCancelConfirmId(null);
      }
    } catch {
      toastFn('Brak połączenia.', 'error');
      setCancelConfirmId(null);
    }
  };

  const cancelSeries = async (resId: number, seriesId: string) => {
    try {
      const res = await fetch(`/api/courts/series/${seriesId}/`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrf() },
      });
      if (res.ok) {
        const d = await res.json().catch(() => ({}));
        setCancelConfirmId(null);
        toastFn(`Anulowano ${d.cancelled ?? ''} rezerwacji.`, 'success');
        onCancelled();
      } else {
        toastFn('Błąd.', 'error');
        setCancelConfirmId(null);
      }
    } catch {
      toastFn('Brak połączenia.', 'error');
      setCancelConfirmId(null);
    }
  };

  return (
    <section className="rv-my-card">
      <div className="rv-my-header">
        <div className="rv-my-header__left">
          <span className="rv-card-dot" aria-hidden="true" />
          <span className="rv-my-title">MOJE REZERWACJE</span>
          <span className="rv-my-badge">{future.length}</span>
        </div>
      </div>
      <div>
        {future.length === 0 ? (
          <div className="rv-empty-row">Nie masz nadchodzących rezerwacji.</div>
        ) : future.map(r => {
          const isFut = new Date(r.endIso) > now;
          const cfg = badgeConfig(r.status, isFut);
          const isConfirming = cancelConfirmId === r.id;

          return (
            <div key={r.id} className="rv-res-row">
              <span className="rv-res-dot" aria-hidden="true" />
              <div className="rv-res-info">
                <div className="rv-res-when">{r.date} · {r.time}</div>
                <div className="rv-res-detail">{r.status === 'confirmed' ? 'Singiel' : 'Oczekuje'}</div>
              </div>
              <div className="rv-res-court">{r.court}{r.facility ? ` · ${r.facility}` : ''}</div>
              {!isConfirming && <span className={`rv-badge ${cfg.cls}`}>{cfg.label}</span>}
              {!isConfirming && cfg.canCancel && r.courtId !== null && (
                <button className="rv-edit-btn" onClick={() => onEdit({
                  reservationId: r.id,
                  seriesId: r.seriesId,
                  startTime: fmtTimeStr(r.startIso),
                  endTime: fmtTimeStr(r.endIso),
                  courtId: r.courtId!,
                })}>Edytuj</button>
              )}
              {!isConfirming && cfg.canCancel && (
                <button className="rv-cancel-btn" onClick={() => setCancelConfirmId(r.id)}>Anuluj</button>
              )}
              {isConfirming && (
                <div className="my-res-inline-confirm">
                  <span className="my-res-inline-confirm__label">{r.seriesId ? 'Anulować:' : 'Na pewno?'}</span>
                  {r.seriesId ? (
                    <>
                      <button className="tr-btn-primary" style={{ padding: '4px 10px', fontSize: '0.72rem' }} onClick={() => cancelSeries(r.id, r.seriesId!)}>Całą serię</button>
                      <button className="rv-action-ghost" style={{ fontSize: '0.7rem', padding: '4px 8px' }} onClick={() => cancelSingle(r.id)}>Tylko tę</button>
                    </>
                  ) : (
                    <button className="tr-btn-primary" style={{ padding: '4px 10px', fontSize: '0.72rem', background: 'var(--tc-hot)' }} onClick={() => cancelSingle(r.id)}>Tak, anuluj</button>
                  )}
                  <button className="rv-action-ghost" style={{ padding: '4px 8px', fontSize: '0.7rem' }} onClick={() => setCancelConfirmId(null)}>Cofnij</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ── Edit reservation popup ────────────────────────────────────────────── */

function EditPopup({
  target,
  onClose,
  onSaved,
  showToast,
}: {
  target: EditTarget;
  onClose: () => void;
  onSaved: () => void;
  showToast: (msg: string, type: string) => void;
}) {
  const [startTime, setStartTime] = useState(target.startTime);
  const [endTime, setEndTime] = useState(target.endTime);
  const [scope, setScope] = useState<'single' | 'series'>('single');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleSave = async () => {
    setLoading(true);
    setError(null);

    const body = { start_time: startTime, end_time: endTime, court_id: target.courtId };
    const isSeriesEdit = scope === 'series' && target.seriesId;
    const url = isSeriesEdit
      ? `/api/courts/series/${target.seriesId}/edit/`
      : `/api/courts/reservations/${target.reservationId}/edit/`;

    try {
      const res = await fetch(url, {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        onClose();
        const msg = isSeriesEdit
          ? `Zaktualizowano ${data.updated ?? ''} rezerwacji serii.`
          : 'Rezerwacja zaktualizowana.';
        showToast(msg, 'success');
        onSaved();
      } else if (res.status === 409) {
        setError(data.detail || 'Konflikt terminu — slot jest już zajęty.');
      } else {
        setError(data.detail || `Błąd (${res.status}).`);
      }
    } catch {
      setError('Brak połączenia z serwerem.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="res-popup-backdrop" role="dialog" aria-modal="true" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="res-popup">
        <div className="res-popup__header">
          <div>
            <div className="res-popup__title">Edytuj rezerwację</div>
            <div className="res-popup__subtitle">Zmień godzinę rezerwacji</div>
          </div>
          <button className="res-popup__close" aria-label="Zamknij" onClick={onClose}>
            <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/></svg>
          </button>
        </div>

        <div style={{ padding: '16px 20px 0' }}>
          <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--tc-sub)', marginBottom: 4 }}>Od</label>
              <input
                type="time"
                step={1800}
                value={startTime}
                onChange={e => setStartTime(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--tc-card-border)', background: 'var(--tc-input-bg)', color: 'var(--tc-ink)', fontSize: '0.9rem', boxSizing: 'border-box' as const }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--tc-sub)', marginBottom: 4 }}>Do</label>
              <input
                type="time"
                step={1800}
                value={endTime}
                onChange={e => setEndTime(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--tc-card-border)', background: 'var(--tc-input-bg)', color: 'var(--tc-ink)', fontSize: '0.9rem', boxSizing: 'border-box' as const }}
              />
            </div>
          </div>

          {target.seriesId && (
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--tc-sub)', marginBottom: 6 }}>Zakres zmiany</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  onClick={() => setScope('single')}
                  style={{ flex: 1, padding: '7px 10px', borderRadius: 8, border: `1px solid ${scope === 'single' ? 'var(--tc-accent)' : 'var(--tc-card-border)'}`, background: scope === 'single' ? 'var(--tc-accent-soft)' : 'var(--tc-chip-bg)', color: scope === 'single' ? 'var(--tc-accent)' : 'var(--tc-sub)', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  Tylko ta
                </button>
                <button
                  type="button"
                  onClick={() => setScope('series')}
                  style={{ flex: 1, padding: '7px 10px', borderRadius: 8, border: `1px solid ${scope === 'series' ? 'var(--tc-accent)' : 'var(--tc-card-border)'}`, background: scope === 'series' ? 'var(--tc-accent-soft)' : 'var(--tc-chip-bg)', color: scope === 'series' ? 'var(--tc-accent)' : 'var(--tc-sub)', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  Cała przyszła seria
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="res-popup__actions">
          <button className="tr-btn-primary" style={{ flex: 1, padding: '10px 18px' }} disabled={loading} onClick={handleSave}>
            {loading ? 'Zapisuję…' : 'Zapisz'}
          </button>
          <button className="rv-action-ghost" onClick={onClose}>Anuluj</button>
        </div>

        {error && (
          <div className="res-popup__msg res-popup__msg--error" role="alert">
            <span>✕</span> {error}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Facility picker ────────────────────────────────────────────────────── */

function FacilityPicker({
  facilities,
  selectedId,
  onSelect,
}: {
  facilities: Facility[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  if (facilities.length <= 1) return null;
  return (
    <div className="rv-facility-picker">
      {facilities.map(f => (
        <button
          key={f.id}
          className={`rv-facility-btn${f.id === selectedId ? ' rv-facility-btn--active' : ''}`}
          onClick={() => onSelect(f.id)}
        >
          {f.name}
        </button>
      ))}
    </div>
  );
}

/* ── Main component ────────────────────────────────────────────────────── */

export default function CourtReservations({
  initialReservations,
  pendingReservations,
  isManager,
  futureCount,
  totalCount,
  gridStart,
  gridEnd,
  todayIso,
}: Props) {
  const SLOTS = useMemo(() => buildSlots(gridStart, gridEnd), [gridStart, gridEnd]);

  const [weekOffset, setWeekOffset] = useState(0);
  const [currentDate, setCurrentDate] = useState(todayIso);
  const [gridState, setGridState] = useState<'loading' | 'empty' | 'error' | 'grid'>('loading');
  const [gridData, setGridData] = useState<CourtData[] | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const facilityIdRef = useRef<number | null>(null);

  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [selectedFacilityId, setSelectedFacilityId] = useState<number | null>(null);
  const [editTarget, setEditTarget] = useState<EditTarget | null>(null);

  const [popupSlot, setPopupSlot] = useState<PopupSlot | null>(null);
  const [popupLoading, setPopupLoading] = useState(false);
  const [popupError, setPopupError] = useState<{ msg: string; type: 'error' | 'conflict' } | null>(null);

  const [toastMsg, setToastMsg] = useState('');
  const [toastType, setToastType] = useState('success');
  const [toastVisible, setToastVisible] = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [myReservations, setMyReservations] = useState<MyReservation[]>(initialReservations);

  // Stats from grid data
  const stats = useMemo(() => {
    if (!gridData) return { free: 0, total: 0, courts: 0 };
    let free = 0, total = 0;
    gridData.forEach(c => {
      c.slots.forEach(s => {
        total++;
        if (!s.is_mine && s.status === 'FREE') {
          if (currentDate > todayIso || (() => {
            const now = new Date();
            const [sh, sm] = s.time.split(':').map(Number);
            const slotDate = new Date(todayIso + 'T00:00:00');
            slotDate.setHours(sh, sm, 0, 0);
            return slotDate > now;
          })()) free++;
        }
      });
    });
    return { free, total, courts: gridData.length };
  }, [gridData, currentDate, todayIso]);

  const showToast = useCallback((msg: string, type = 'success') => {
    setToastMsg(msg);
    setToastType(type);
    setToastVisible(true);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToastVisible(false), 4000);
  }, []);

  const loadTimeline = useCallback(async (date?: string) => {
    const fid = facilityIdRef.current;
    if (!fid) { setGridState('empty'); return; }
    setGridState('loading');
    try {
      const res = await fetch(`/api/courts/timeline/${fid}/?date=${date ?? currentDate}`, { credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TimelineData = await res.json();
      if (!data.courts || data.courts.length === 0) {
        setGridState('empty');
        return;
      }
      setGridData(data.courts);
      setGridState('grid');
    } catch (e) {
      setErrorMsg(`Nie udało się załadować grafiku. (${(e as Error).message})`);
      setGridState('error');
    }
  }, [currentDate]);

  const reloadMyReservations = useCallback(async () => {
    try {
      const res = await fetch('/api/courts/reservations/', { credentials: 'include' });
      if (!res.ok) return;
      const list = await res.json();
      const now = new Date();
      setMyReservations(list.map((r: any) => ({
        id: r.id,
        courtId: r.court_id ?? null,
        court: r.court_name ?? 'Kort',
        facility: r.facility_name ?? '',
        date: fmtDateShort(r.start_time),
        time: `${fmtTimeStr(r.start_time)}–${fmtTimeStr(r.end_time)}`,
        startIso: r.start_time,
        endIso: r.end_time,
        status: r.status.toLowerCase(),
        seriesId: r.series_id ?? null,
      })));
    } catch {}
  }, []);

  // Init — load facilities then timeline
  useEffect(() => {
    (async () => {
      setGridState('loading');
      try {
        const res = await fetch('/api/courts/facilities/', { credentials: 'include' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const facilityList: Facility[] = await res.json();
        if (!facilityList || facilityList.length === 0) { setGridState('empty'); return; }
        setFacilities(facilityList);
        const firstId = facilityList[0].id;
        facilityIdRef.current = firstId;
        setSelectedFacilityId(firstId);
        const tRes = await fetch(`/api/courts/timeline/${firstId}/?date=${todayIso}`, { credentials: 'include' });
        if (!tRes.ok) throw new Error(`HTTP ${tRes.status}`);
        const tData: TimelineData = await tRes.json();
        if (!tData.courts || tData.courts.length === 0) { setGridState('empty'); return; }
        setGridData(tData.courts);
        setGridState('grid');
      } catch (e) {
        setErrorMsg(`Nie udało się załadować obiektów. (${(e as Error).message})`);
        setGridState('error');
      }
    })();
  }, [todayIso]);

  // Week days
  const weekDays = useMemo(() => buildWeekDays(weekOffset), [weekOffset]);

  // Ensure currentDate stays in the current week range
  useEffect(() => {
    const weekDates = weekDays.map(d => d.iso);
    if (!weekDates.includes(currentDate)) {
      const first = weekDays.find(d => !d.isPast) ?? weekDays[0];
      setCurrentDate(first.iso);
      loadTimeline(first.iso);
    }
  }, [weekDays, currentDate, loadTimeline]);

  const weekLabel = useMemo(() => {
    if (weekOffset === 0) return 'Ten tydzień';
    const first = weekDays[0], last = weekDays[6];
    const firstD = new Date(first.iso + 'T12:00:00');
    const lastD = new Date(last.iso + 'T12:00:00');
    return `${firstD.getDate()} ${MONTH_NAMES[firstD.getMonth()]} – ${lastD.getDate()} ${MONTH_NAMES[lastD.getMonth()]}`;
  }, [weekDays, weekOffset]);

  const handleDayClick = (iso: string) => {
    setCurrentDate(iso);
    loadTimeline(iso);
  };

  const handleWeekPrev = () => {
    if (weekOffset <= 0) return;
    setWeekOffset(w => w - 1);
  };

  const handleWeekNext = () => {
    setWeekOffset(w => w + 1);
  };

  // Slot selection → open popup
  const handleSlotSelect = (slot: PopupSlot) => {
    if (slot.date < todayIso) return;
    setPopupSlot(slot);
    setPopupError(null);
    setPopupLoading(false);
  };

  const handlePopupConfirm = async (recurring: boolean, weeks: number) => {
    if (!popupSlot) return;
    setPopupLoading(true);
    setPopupError(null);

    const body: Record<string, unknown> = {
      court_id: popupSlot.courtId,
      date: popupSlot.date,
      start_time: popupSlot.startTime,
      end_time: popupSlot.endTime,
    };
    if (recurring) { body.recurring = true; body.weeks = weeks; }

    try {
      const res = await fetch('/api/courts/reserve/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setPopupSlot(null);
        showToast(recurring ? `Seria ${data.count} rezerwacji złożona.` : 'Rezerwacja złożona — oczekuje na zatwierdzenie.', 'success');
        await Promise.all([loadTimeline(), reloadMyReservations()]);
      } else if (res.status === 409) {
        setPopupError({ msg: data.detail || 'Ten slot jest już zajęty.', type: 'conflict' });
      } else if (res.status === 400) {
        setPopupError({ msg: data.detail || 'Nieprawidłowe dane.', type: 'error' });
      } else {
        setPopupError({ msg: data.detail || `Błąd serwera (${res.status}).`, type: 'error' });
      }
    } catch {
      setPopupError({ msg: 'Brak połączenia z serwerem.', type: 'error' });
    } finally {
      setPopupLoading(false);
    }
  };

  const handleReservationCancelled = () => {
    reloadMyReservations();
    loadTimeline();
  };

  const handleFacilitySelect = (id: number) => {
    facilityIdRef.current = id;
    setSelectedFacilityId(id);
    loadTimeline(currentDate);
  };

  const colTemplate = `120px repeat(${SLOTS.length}, minmax(34px, 1fr))`;
  const isToday = currentDate === todayIso;

  return (
    <>
      {/* Stat cards */}
      <div className="rv-stats">
        <div className="rv-stat rv-stat--accent">
          <div className="rv-stat__label">{isToday ? 'WOLNE SLOTY DZIŚ' : 'WOLNE SLOTY'}</div>
          <div className="rv-stat__val" style={{ color: 'var(--tc-accent)' }}>
            {gridState === 'grid' ? stats.free : '—'}
          </div>
          <div className="rv-stat__sub">
            {gridState === 'grid'
              ? (stats.free === 0
                ? (isToday ? 'brak wolnych na dziś' : 'brak wolnych w tym dniu')
                : `z ${stats.total} slotów łącznie`)
              : 'ładowanie…'}
          </div>
        </div>
        <div className="rv-stat">
          <div className="rv-stat__label">TWOJE REZERWACJE</div>
          <div className="rv-stat__val">{myReservations.filter(r => new Date(r.endIso) > new Date()).length}</div>
          <div className="rv-stat__sub">na ten tydzień</div>
        </div>
        <div className="rv-stat">
          <div className="rv-stat__label">KORTY OTWARTE</div>
          <div className="rv-stat__val">{gridState === 'grid' ? stats.courts : '—'}</div>
          <div className="rv-stat__sub">{gridState === 'grid' ? 'dostępne korty' : 'ładowanie…'}</div>
        </div>
        <div className="rv-stat">
          <div className="rv-stat__label">TWOJE ZUŻYTE GODZINY</div>
          <div className="rv-stat__val">{totalCount}</div>
          <div className="rv-stat__sub">rezerwacji łącznie</div>
        </div>
      </div>

      {/* Facility picker — widoczny tylko gdy > 1 facility */}
      <FacilityPicker
        facilities={facilities}
        selectedId={selectedFacilityId}
        onSelect={handleFacilitySelect}
      />

      {/* Week nav */}
      <div className="rv-week-nav">
        <button className="rv-week-btn" aria-label="Poprzedni tydzień" disabled={weekOffset <= 0} onClick={handleWeekPrev}>
          <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd"/></svg>
        </button>
        <span className="rv-week-label">{weekLabel}</span>
        <button className="rv-week-btn" aria-label="Następny tydzień" onClick={handleWeekNext}>
          <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"/></svg>
        </button>
      </div>

      {/* Day picker */}
      <div className="rv-days">
        {weekDays.map(d => (
          <button
            key={d.iso}
            className={`rv-day${d.iso === currentDate ? ' rv-day--active' : ''}${d.isPast ? ' rv-day--past' : ''}`}
            disabled={d.isPast}
            onClick={() => handleDayClick(d.iso)}
          >
            <span className="rv-day__label">{d.label}</span>
            <span className="rv-day__sub">{d.sub}</span>
          </button>
        ))}
      </div>

      {/* Manager panel */}
      {isManager && (
        <ManagerPanel
          reservations={pendingReservations}
          onRefresh={() => loadTimeline()}
        />
      )}

      {/* Grid card */}
      <section className="rv-grid-card">
        <div className="rv-grid-header">
          <span className="rv-grid-title">DOSTĘPNOŚĆ KORTÓW</span>
          <div className="rv-legend">
            <div className="rv-legend__item"><div className="rv-legend__swatch rv-legend__swatch--mine" />Twoje</div>
            <div className="rv-legend__item"><div className="rv-legend__swatch rv-legend__swatch--free" />Wolne</div>
            <div className="rv-legend__item"><div className="rv-legend__swatch rv-legend__swatch--taken" />Zajęte</div>
            <div className="rv-legend__item"><div className="rv-legend__swatch rv-legend__swatch--past" />Minione</div>
          </div>
        </div>

        {gridState === 'loading' && <div className="rv-state">Ładowanie grafiku…</div>}
        {gridState === 'empty' && <div className="rv-state">Brak obiektów z włączoną rezerwacją online.</div>}
        {gridState === 'error' && <div className="rv-state rv-state--error">{errorMsg}</div>}

        {gridState === 'grid' && gridData && (
          <div className="rv-grid-scroll">
            <div className="rv-grid-table">
              {/* Hour header */}
              <div className="rv-hour-header" style={{ display: 'grid', gridTemplateColumns: colTemplate }}>
                <div className="rv-hour-header__court">KORT</div>
                {SLOTS.map((t, i) => {
                  const isHour = t.endsWith(':00');
                  return (
                    <div key={i} className={`rv-hour-header__label rv-hour-header__label--${isHour ? 'full' : 'half'}`}>
                      {isHour ? t : ''}
                    </div>
                  );
                })}
              </div>
              {/* Court rows */}
              {gridData.map(court => (
                <CourtRow
                  key={court.id}
                  court={court}
                  allSlots={SLOTS}
                  currentDate={currentDate}
                  todayIso={todayIso}
                  onSlotSelect={handleSlotSelect}
                />
              ))}
            </div>
          </div>
        )}

        <div className="rv-grid-footer">
          <div className="rv-grid-footer__hint">
            Kliknij lub <strong>przeciągnij myszą</strong> po wolnych slotach, aby wybrać zakres godzin.
          </div>
        </div>
      </section>

      {/* My reservations */}
      <MyReservationsList
        reservations={myReservations}
        onCancelled={handleReservationCancelled}
        onEdit={setEditTarget}
        showToast={showToast}
      />

      {/* Edit popup */}
      {editTarget && (
        <EditPopup
          target={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => { reloadMyReservations(); loadTimeline(); }}
          showToast={showToast}
        />
      )}

      {/* Toast */}
      <Toast message={toastMsg} type={toastType} visible={toastVisible} />

      {/* Popup */}
      <ReservationPopup
        slot={popupSlot}
        onClose={() => setPopupSlot(null)}
        onConfirm={handlePopupConfirm}
        loading={popupLoading}
        error={popupError}
      />
    </>
  );
}
