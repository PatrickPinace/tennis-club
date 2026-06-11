import { useState, useEffect } from 'react';
import AddMatchForm from './AddMatchForm';

interface Props {
  myId?: number;
  today?: string;
  addMatchUrl: string;
}

export default function GlobalMatchModals({ myId, today, addMatchUrl }: Props) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showTournamentModal, setShowTournamentModal] = useState(false);
  const [activeTournamentMatches, setActiveTournamentMatches] = useState<any[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [expandedMatchId, setExpandedMatchId] = useState<number | null>(null);
  const [savingMatchId, setSavingMatchId] = useState<number | null>(null);
  const [saveErrors, setSaveErrors] = useState<Record<number, string>>({});
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<Record<number, string>>({});

  const [set1p1, setSet1p1] = useState<Record<number, string>>({});
  const [set1p2, setSet1p2] = useState<Record<number, string>>({});
  const [set2p1, setSet2p1] = useState<Record<number, string>>({});
  const [set2p2, setSet2p2] = useState<Record<number, string>>({});
  const [set3p1, setSet3p1] = useState<Record<number, string>>({});
  const [set3p2, setSet3p2] = useState<Record<number, string>>({});
  const [walkover, setWalkover] = useState<Record<number, boolean>>({});
  const [walkoverWinnerId, setWalkoverWinnerId] = useState<Record<number, string>>({});
  const [matchDates, setMatchDates] = useState<Record<number, string>>({});

  const todayStr = today ?? new Date().toISOString().slice(0, 10);

  const fetchActiveMatches = async () => {
    setLoadingMatches(true);
    setFetchError(null);
    try {
      const res = await fetch('/api/tournaments/my-active-matches/', { credentials: 'include' });
      if (!res.ok) throw new Error(`Błąd: ${res.status}`);
      const data = await res.json();
      setActiveTournamentMatches(data);

      const s1p1: Record<number, string> = {};
      const s1p2: Record<number, string> = {};
      const s2p1: Record<number, string> = {};
      const s2p2: Record<number, string> = {};
      const s3p1: Record<number, string> = {};
      const s3p2: Record<number, string> = {};
      const wdr: Record<number, boolean> = {};
      const wdrWin: Record<number, string> = {};
      const dates: Record<number, string> = {};

      data.forEach((m: any) => {
        s1p1[m.id] = m.set1_p1_score !== null ? String(m.set1_p1_score) : '';
        s1p2[m.id] = m.set1_p2_score !== null ? String(m.set1_p2_score) : '';
        s2p1[m.id] = m.set2_p1_score !== null ? String(m.set2_p1_score) : '';
        s2p2[m.id] = m.set2_p2_score !== null ? String(m.set2_p2_score) : '';
        s3p1[m.id] = m.set3_p1_score !== null ? String(m.set3_p1_score) : '';
        s3p2[m.id] = m.set3_p2_score !== null ? String(m.set3_p2_score) : '';
        wdr[m.id] = false;
        wdrWin[m.id] = '';
        if (m.scheduled_time) {
          try {
            dates[m.id] = new Date(m.scheduled_time).toISOString().slice(0, 16);
          } catch {
            dates[m.id] = '';
          }
        } else {
          dates[m.id] = '';
        }
      });
      setSet1p1(s1p1);
      setSet1p2(s1p2);
      setSet2p1(s2p1);
      setSet2p2(s2p2);
      setSet3p1(s3p1);
      setSet3p2(s3p2);
      setWalkover(wdr);
      setWalkoverWinnerId(wdrWin);
      setMatchDates(dates);
    } catch (err: any) {
      setFetchError(err.message || 'Nie udało się pobrać meczów.');
    } finally {
      setLoadingMatches(false);
    }
  };

  const handleSaveScore = async (match: any) => {
    const mId = match.id;
    setSavingMatchId(mId);
    setSaveErrors(prev => ({ ...prev, [mId]: '' }));
    setSaveSuccessMsg(prev => ({ ...prev, [mId]: '' }));

    const isWalkover = walkover[mId] || false;
    const dateVal = matchDates[mId] || '';

    let payload: any = {};
    if (dateVal) {
      payload.scheduled_time = new Date(dateVal).toISOString();
    } else {
      payload.scheduled_time = new Date().toISOString();
    }

    const teamAName = match.participant1_name + (match.participant3_name ? ` / ${match.participant3_name}` : '');
    const teamBName = match.participant2_name + (match.participant4_name ? ` / ${match.participant4_name}` : '');

    if (isWalkover) {
      const winnerId = walkoverWinnerId[mId];
      if (!winnerId) {
        setSaveErrors(prev => ({ ...prev, [mId]: 'Musisz wybrać zwycięzcę walkowera.' }));
        setSavingMatchId(null);
        return;
      }
      payload.walkover = true;
      payload.winner_participant_id = parseInt(winnerId, 10);
    } else {
      const val1_1 = set1p1[mId] || '';
      const val1_2 = set1p2[mId] || '';
      const val2_1 = set2p1[mId] || '';
      const val2_2 = set2p2[mId] || '';
      const val3_1 = set3p1[mId] || '';
      const val3_2 = set3p2[mId] || '';

      const intVal = (v: string): number | null => {
        const trimmed = v.trim();
        if (trimmed === '') return null;
        const n = parseInt(trimmed, 10);
        return isNaN(n) ? null : n;
      };

      const s1_1 = intVal(val1_1);
      const s1_2 = intVal(val1_2);
      const s2_1 = intVal(val2_1);
      const s2_2 = intVal(val2_2);
      const s3_1 = intVal(val3_1);
      const s3_2 = intVal(val3_2);

      if (s1_1 === null || s1_2 === null) {
        setSaveErrors(prev => ({ ...prev, [mId]: 'Set 1 jest wymagany — wpisz wynik dla obu stron.' }));
        setSavingMatchId(null);
        return;
      }

      const checkTennisSet = (a: number, b: number, n: number): string | null => {
        if (a < 0 || b < 0) return `Set ${n}: wynik nie może być ujemny.`;
        const hi = Math.max(a, b), lo = Math.min(a, b);
        if (hi >= 10) {
          if (hi > 20) return `Set ${n}: super tie-break nie może mieć więcej niż 20 punktów.`;
          if (hi - lo < 2) return `Set ${n}: super tie-break wymaga przewagi ≥ 2 punktów.`;
          if (hi > 10 && lo !== hi - 2) return `Set ${n}: po 10:10 gra trwa do różnicy 2 punktów.`;
          return null;
        }
        if (hi < 6) return `Set ${n}: zwycięzca musi mieć co najmniej 6 gemów.`;
        if (hi === 6 && lo <= 4) return null;
        if (hi === 7 && (lo === 5 || lo === 6)) return null;
        return `Set ${n}: wynik ${a}:${b} jest niemożliwy w standardowym secie tenisowym.`;
      };

      if (match.tournament_type !== 'AMR') {
        const err1 = checkTennisSet(s1_1, s1_2, 1);
        if (err1) {
          setSaveErrors(prev => ({ ...prev, [mId]: err1 }));
          setSavingMatchId(null);
          return;
        }

        if ((s2_1 === null) !== (s2_2 === null)) {
          setSaveErrors(prev => ({ ...prev, [mId]: 'Set 2: wpisz wynik dla obu stron.' }));
          setSavingMatchId(null);
          return;
        } else if (s2_1 !== null && s2_2 !== null) {
          const err2 = checkTennisSet(s2_1, s2_2, 2);
          if (err2) {
            setSaveErrors(prev => ({ ...prev, [mId]: err2 }));
            setSavingMatchId(null);
            return;
          }
        }

        if ((s3_1 === null) !== (s3_2 === null)) {
          setSaveErrors(prev => ({ ...prev, [mId]: 'Set 3: wpisz wynik dla obu stron.' }));
          setSavingMatchId(null);
          return;
        } else if (s3_1 !== null && s3_2 !== null) {
          const err3 = checkTennisSet(s3_1, s3_2, 3);
          if (err3) {
            setSaveErrors(prev => ({ ...prev, [mId]: err3 }));
            setSavingMatchId(null);
            return;
          }
        }
      }

      payload = {
        ...payload,
        set1_p1: s1_1,
        set1_p2: s1_2,
        set2_p1: s2_1,
        set2_p2: s2_2,
        set3_p1: s3_1,
        set3_p2: s3_2,
      };
    }

    try {
      const csrfToken = document.cookie
        .split(';').map(c => c.trim())
        .find(c => c.startsWith('csrftoken='))
        ?.split('=')[1] ?? '';

      const res = await fetch(`/api/tournaments/${match.tournament_id}/matches/${mId}/score/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setSaveSuccessMsg(prev => ({ ...prev, [mId]: 'Zapisano pomyślnie!' }));
        setTimeout(() => {
          setActiveTournamentMatches(prev => prev.filter(m => m.id !== mId));
          setExpandedMatchId(null);
          // If on matches page or dashboard, trigger a reload to update the match history
          window.location.reload();
        }, 1500);
      } else {
        setSaveErrors(prev => ({ ...prev, [mId]: data.detail || data.error || 'Nie udało się zapisać wyniku.' }));
      }
    } catch {
      setSaveErrors(prev => ({ ...prev, [mId]: 'Błąd połączenia z serwerem.' }));
    } finally {
      setSavingMatchId(null);
    }
  };

  useEffect(() => {
    const handleOpenAdd = () => setShowAddModal(true);
    const handleOpenTournament = () => {
      setShowTournamentModal(true);
      fetchActiveMatches();
    };

    window.addEventListener('open-add-match-modal', handleOpenAdd);
    window.addEventListener('open-tournament-matches-modal', handleOpenTournament);

    return () => {
      window.removeEventListener('open-add-match-modal', handleOpenAdd);
      window.removeEventListener('open-tournament-matches-modal', handleOpenTournament);
    };
  }, []);

  return (
    <>
      {showAddModal && myId && (
        <div className="res-popup-backdrop" role="dialog" aria-modal="true"
          onClick={e => { if (e.target === e.currentTarget) setShowAddModal(false); }}>
          <div className="res-popup" style={{ maxWidth: 620 }}>
            <div className="res-popup__header">
              <div>
                <div className="res-popup__title">Dodaj mecz towarzyski</div>
                <div className="res-popup__subtitle">Zapisz wynik rozegranego meczu</div>
              </div>
              <button className="res-popup__close" aria-label="Zamknij" onClick={() => setShowAddModal(false)}>
                <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
                </svg>
              </button>
            </div>
            <div className="res-popup__body">
              <AddMatchForm
                myId={myId}
                today={todayStr}
                matchesUrl={addMatchUrl}
                isModal={true}
                onClose={() => setShowAddModal(false)}
              />
            </div>
          </div>
        </div>
      )}

      {showTournamentModal && (
        <div className="res-popup-backdrop" role="dialog" aria-modal="true"
          onClick={e => { if (e.target === e.currentTarget) setShowTournamentModal(false); }}>
          <div className="res-popup" style={{ maxWidth: 650, width: '100%' }}>
            <div className="res-popup__header">
              <div>
                <div className="res-popup__title">Mecze turniejowe</div>
                <div className="res-popup__subtitle">Wprowadź wynik meczu turniejowego</div>
              </div>
              <button className="res-popup__close" aria-label="Zamknij" onClick={() => setShowTournamentModal(false)}>
                <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd"/>
                </svg>
              </button>
            </div>
            <div className="res-popup__body" style={{ maxHeight: 'var(--modal-body-max-height, 70vh)', overflowY: 'auto', padding: '16px 20px' }}>
              {loadingMatches && <div style={{ textAlign: 'center', padding: '20px', color: 'var(--tc-muted)' }}>Ładowanie meczów...</div>}
              {fetchError && <div style={{ color: 'var(--tc-hot)', padding: '10px 0' }}>{fetchError}</div>}
              
              {!loadingMatches && !fetchError && activeTournamentMatches.length === 0 && (
                <div style={{ textAlign: 'center', padding: '30px 20px', color: 'var(--tc-muted)' }}>
                  Brak aktywnych meczów turniejowych, do których możesz wpisać wynik.
                </div>
              )}

              {!loadingMatches && !fetchError && activeTournamentMatches.map(m => {
                const isExpanded = expandedMatchId === m.id;
                
                const formatNameShort = (fullName: string | null | undefined) => {
                  if (!fullName) return '';
                  const parts = fullName.trim().split(/\s+/);
                  if (parts.length < 2) return fullName;
                  return `${parts[0]} ${parts[parts.length - 1].charAt(0)}.`;
                };

                const teamANameFull = m.participant1_name + (m.participant3_name ? ` / ${m.participant3_name}` : '');
                const teamBNameFull = m.participant2_name + (m.participant4_name ? ` / ${m.participant4_name}` : '');
                const teamANameShort = formatNameShort(m.participant1_name) + (m.participant3_name ? ` / ${formatNameShort(m.participant3_name)}` : '');
                const teamBNameShort = formatNameShort(m.participant2_name) + (m.participant4_name ? ` / ${formatNameShort(m.participant4_name)}` : '');

                const teamAName = m.participant1_name + (m.participant3_name ? ` / ${m.participant3_name}` : '');
                const teamBName = m.participant2_name + (m.participant4_name ? ` / ${m.participant4_name}` : '');

                return (
                  <div key={m.id} style={{
                    background: 'var(--tc-chip-bg)',
                    border: '1px solid var(--tc-card-border)',
                    borderRadius: '10px',
                    marginBottom: '12px',
                    overflow: 'hidden',
                    transition: 'all 0.2s ease'
                  }}>
                    {/* Header bar */}
                    <div 
                      onClick={() => setExpandedMatchId(isExpanded ? null : m.id)}
                      style={{
                        padding: '14px 18px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        cursor: 'pointer',
                        userSelect: 'none'
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--tc-accent)', textTransform: 'uppercase', marginBottom: '2px' }}>
                          🏆 {m.tournament_name}
                        </div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--tc-ink)' }}>
                          <span className="player-name-full">{teamANameFull}</span>
                          <span className="player-name-short">{teamANameShort}</span>
                          {' '}<span style={{ color: 'var(--tc-faint)' }}>vs</span>{' '}
                          <span className="player-name-full">{teamBNameFull}</span>
                          <span className="player-name-short">{teamBNameShort}</span>
                        </div>
                        {m.scheduled_time && (
                          <div style={{ fontSize: '0.7rem', color: 'var(--tc-muted)', marginTop: '2px' }}>
                            Termin: {new Date(m.scheduled_time).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                          </div>
                        )}
                      </div>
                      <div style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        border: '1px solid var(--tc-card-border-soft)',
                        background: '#ffffff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--tc-muted)',
                        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
                      }}>
                        <svg 
                          width="8" height="8" 
                          viewBox="0 0 10 10" 
                          fill="none" 
                          stroke="currentColor" 
                          strokeWidth="1.2" 
                          style={{
                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
                          }}
                        >
                          <path d="M1 3.5l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    </div>

                    {/* Expandable score form */}
                    {isExpanded && (
                      <div style={{
                        padding: '16px 18px',
                        borderTop: '1px solid var(--tc-card-border-soft)',
                        background: 'var(--tc-card-bg)'
                      }}>
                        {saveErrors[m.id] && (
                          <div style={{
                            padding: '8px 12px',
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.2)',
                            borderRadius: '6px',
                            color: 'var(--tc-hot)',
                            fontSize: '0.8rem',
                            marginBottom: '12px'
                          }}>
                            {saveErrors[m.id]}
                          </div>
                        )}
                        {saveSuccessMsg[m.id] && (
                          <div style={{
                            padding: '8px 12px',
                            background: 'var(--tc-accent-soft)',
                            border: '1px solid var(--tc-accent-border)',
                            borderRadius: '6px',
                            color: 'var(--tc-accent)',
                            fontSize: '0.8rem',
                            marginBottom: '12px'
                          }}>
                            {saveSuccessMsg[m.id]}
                          </div>
                        )}

                        <div className="scoreboard-grid" style={{ 
                          background: 'var(--tc-chip-bg)', 
                          border: '1px solid var(--tc-card-border)', 
                          borderRadius: '8px',
                          overflow: 'hidden',
                          marginBottom: '16px',
                          opacity: walkover[m.id] ? 0.4 : 1,
                          pointerEvents: walkover[m.id] ? 'none' : 'auto'
                        }}>
                          <div style={{ padding: '10px 14px', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)', textTransform: 'uppercase' }}>Gracz</div>
                          <div style={{ textAlign: 'center', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)' }}>SET 1</div>
                          <div style={{ textAlign: 'center', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)' }}>SET 2</div>
                          <div style={{ textAlign: 'center', fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)' }}>SET 3</div>

                          <div style={{ padding: '10px 14px', fontSize: '0.88rem', fontWeight: 600, color: 'var(--tc-ink)', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <span className="player-name-full">{teamANameFull}</span>
                            <span className="player-name-short">{teamANameShort}</span>
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set1p1[m.id] || ''}
                              onChange={e => setSet1p1(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set2p1[m.id] || ''}
                              onChange={e => setSet2p1(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set3p1[m.id] || ''}
                              onChange={e => setSet3p1(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>

                          <div style={{ padding: '10px 14px', fontSize: '0.88rem', fontWeight: 600, color: 'var(--tc-ink)', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <span className="player-name-full">{teamBNameFull}</span>
                            <span className="player-name-short">{teamBNameShort}</span>
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set1p2[m.id] || ''}
                              onChange={e => setSet1p2(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set2p2[m.id] || ''}
                              onChange={e => setSet2p2(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                          <div style={{ padding: '6px', display: 'flex', justifyContent: 'center', borderTop: '1px solid var(--tc-card-border-soft)' }}>
                            <input 
                              type="number" min="0" max="99" disabled={walkover[m.id]}
                              value={set3p2[m.id] || ''}
                              onChange={e => setSet3p2(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ width: '42px', height: '32px', textAlign: 'center', background: 'var(--tc-card-bg)', border: '1px solid var(--tc-card-border)', borderRadius: '4px', color: 'var(--tc-ink)', fontWeight: 600 }}
                            />
                          </div>
                        </div>

                        <div className="mobile-stack-grid" style={{ marginBottom: '16px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                            <label style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--tc-muted)', textTransform: 'uppercase' }}>Termin rozegrania</label>
                            <input 
                              type="datetime-local" 
                              value={matchDates[m.id] || ''}
                              onChange={e => setMatchDates(prev => ({ ...prev, [m.id]: e.target.value }))}
                              style={{ 
                                height: '36px', 
                                padding: '0 10px', 
                                background: 'var(--tc-chip-bg)', 
                                border: '1px solid var(--tc-card-border)', 
                                borderRadius: '6px', 
                                color: 'var(--tc-ink)', 
                                fontSize: '0.8rem',
                                fontWeight: 500,
                                fontFamily: 'inherit'
                              }}
                            />
                          </div>

                          <div style={{ 
                            padding: '10px 14px', 
                            background: 'rgba(239, 68, 68, 0.04)', 
                            border: '1px solid rgba(239, 68, 68, 0.1)', 
                            borderRadius: '8px',
                            display: 'flex', 
                            flexDirection: 'column',
                            justifyContent: 'center',
                            gap: '8px'
                          }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, color: 'var(--tc-muted)', margin: 0 }}>
                              <input 
                                type="checkbox" 
                                checked={walkover[m.id] || false}
                                onChange={e => setWalkover(prev => ({ ...prev, [m.id]: e.target.checked }))}
                              />
                              ⚠️ Walkover ( WDR )
                            </label>

                            {walkover[m.id] && (
                              <select 
                                value={walkoverWinnerId[m.id] || ''} 
                                onChange={e => setWalkoverWinnerId(prev => ({ ...prev, [m.id]: e.target.value }))}
                                style={{ 
                                  height: '30px', 
                                  padding: '0 6px', 
                                  background: 'var(--tc-card-bg)', 
                                  border: '1px solid var(--tc-card-border)', 
                                  borderRadius: '4px', 
                                  color: 'var(--tc-ink)',
                                  fontSize: '0.78rem'
                                }}
                              >
                                <option value="">— wybierz zwycięzcę —</option>
                                <option value={m.participant1_id}>{teamAName}</option>
                                <option value={m.participant2_id}>{teamBName}</option>
                              </select>
                            )}
                          </div>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
                          <button 
                            type="button" 
                            disabled={savingMatchId === m.id}
                            onClick={() => handleSaveScore(m)}
                            className="tc-btn tc-btn-primary"
                            style={{ height: '34px', fontSize: '0.8rem', padding: '0 16px' }}
                          >
                            {savingMatchId === m.id ? 'Zapisywanie...' : 'Zapisz wynik'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
