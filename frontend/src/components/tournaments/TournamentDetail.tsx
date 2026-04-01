/**
 * Tournament Detail Component
 * Shows tournament info, management controls, participants, bracket
 */

import { useEffect, useState } from 'react';
import {
  getTournamentDetail,
  getTournamentBracket,
  openRegistration,
  closeRegistration,
  confirmParticipants,
  generateBracket,
  startTournament,
  finishTournament,
  cancelTournament,
  joinTournament,
  withdrawFromTournament
} from '../../lib/api/tournaments';
import type { TournamentDetail as TournamentDetailType, TournamentStatus, BracketResponse, BracketMatch } from '../../types/tournament';
import ReportMatchResultModal from './ReportMatchResultModal';

interface TournamentDetailProps {
  tournamentId: number;
  isStaff?: boolean;
}

export default function TournamentDetail({ tournamentId, isStaff = false }: TournamentDetailProps) {
  const [tournament, setTournament] = useState<TournamentDetailType | null>(null);
  const [bracket, setBracket] = useState<BracketResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'info' | 'participants' | 'bracket'>('info');
  const [selectedMatch, setSelectedMatch] = useState<BracketMatch | null>(null);
  const [showResultModal, setShowResultModal] = useState(false);

  const loadTournament = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getTournamentDetail(tournamentId);
      setTournament(data);

      // Load bracket if available
      if (['bracket_ready', 'in_progress', 'finished'].includes(data.status)) {
        try {
          const bracketData = await getTournamentBracket(tournamentId);
          setBracket(bracketData);
        } catch (err) {
          console.error('Failed to load bracket:', err);
        }
      }
    } catch (err: any) {
      console.error('Failed to load tournament:', err);
      setError(err?.body?.error || 'Nie udało się załadować turnieju');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTournament();
  }, [tournamentId]);

  const handleAction = async (action: () => Promise<any>, successMessage: string) => {
    setActionLoading(true);
    try {
      await action();
      alert(successMessage);
      await loadTournament();
    } catch (err: any) {
      alert(err?.body?.error || 'Operacja nie powiodła się');
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: TournamentStatus) => {
    const config: Record<TournamentStatus, { bg: string; text: string; label: string }> = {
      draft: { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Szkic' },
      registration_open: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Zapisy otwarte' },
      registration_closed: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'Zapisy zamknięte' },
      participants_confirmed: { bg: 'bg-purple-100', text: 'text-purple-800', label: 'Skład potwierdzony' },
      bracket_ready: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Drabinka gotowa' },
      in_progress: { bg: 'bg-green-100', text: 'text-green-800', label: 'W trakcie' },
      finished: { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Zakończony' },
      cancelled: { bg: 'bg-red-100', text: 'text-red-800', label: 'Odwołany' }
    };
    const c = config[status];
    return (
      <span className={`inline-flex items-center justify-center rounded-full px-3 py-1 text-sm font-medium ${c.bg} ${c.text}`}>
        {c.label}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#4CAF50] border-t-transparent"></div>
      </div>
    );
  }

  if (error || !tournament) {
    return (
      <div className="rounded-[16px] border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-[14px] font-medium text-red-800">{error || 'Nie znaleziono turnieju'}</p>
        <button
          onClick={() => window.location.href = '/app/tournaments'}
          className="mt-4 h-10 rounded-[10px] bg-red-600 px-4 text-[14px] font-semibold text-white hover:bg-red-700"
        >
          Wróć do listy turniejów
        </button>
      </div>
    );
  }

  const isManager = isStaff; // In real app, check if user is tournament manager
  const isRegistrationOpen = tournament.status === 'registration_open';
  const canJoin = isRegistrationOpen && !tournament.is_participant && tournament.participant_count < tournament.max_participants;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => window.location.href = '/app/tournaments'}
            className="mb-3 text-[14px] text-[#6B7280] hover:text-[#111827]"
          >
            ← Wróć do turniejów
          </button>
          <h1 className="text-[28px] font-bold text-[#111827]">{tournament.name}</h1>
          <div className="mt-2 flex items-center gap-3">
            {getStatusBadge(tournament.status)}
            <span className="text-[14px] text-[#6B7280]">
              {new Date(tournament.start_date).toLocaleDateString('pl-PL')}
            </span>
          </div>
        </div>

        {/* User Actions */}
        {canJoin && (
          <button
            onClick={() => handleAction(
              () => joinTournament(tournamentId),
              'Zapisano do turnieju!'
            )}
            disabled={actionLoading}
            className="h-10 rounded-[10px] bg-[#4CAF50] px-4 text-[14px] font-semibold text-white hover:bg-[#43A047] disabled:opacity-50"
          >
            Zapisz się
          </button>
        )}

        {tournament.is_participant && isRegistrationOpen && (
          <button
            onClick={() => handleAction(
              () => withdrawFromTournament(tournamentId),
              'Wypisano z turnieju'
            )}
            disabled={actionLoading}
            className="h-10 rounded-[10px] bg-red-600 px-4 text-[14px] font-semibold text-white hover:bg-red-700 disabled:opacity-50"
          >
            Zrezygnuj
          </button>
        )}
      </div>

      {/* Management Panel (Staff only) */}
      {isManager && tournament.status !== 'cancelled' && tournament.status !== 'finished' && (
        <div className="rounded-[16px] border border-[#4CAF50]/20 bg-[#4CAF50]/5 p-6">
          <h2 className="mb-4 text-[18px] font-bold text-[#111827]">Panel zarządzania</h2>
          <div className="flex flex-wrap gap-2">
            {tournament.status === 'draft' && (
              <button
                onClick={() => handleAction(
                  () => openRegistration(tournamentId),
                  'Zapisy zostały otwarte'
                )}
                disabled={actionLoading}
                className="h-10 rounded-[10px] bg-[#4CAF50] px-4 text-[14px] font-semibold text-white hover:bg-[#43A047] disabled:opacity-50"
              >
                Otwórz zapisy
              </button>
            )}

            {tournament.status === 'registration_open' && (
              <button
                onClick={() => handleAction(
                  () => closeRegistration(tournamentId),
                  'Zapisy zostały zamknięte'
                )}
                disabled={actionLoading}
                className="h-10 rounded-[10px] bg-orange-600 px-4 text-[14px] font-semibold text-white hover:bg-orange-700 disabled:opacity-50"
              >
                Zamknij zapisy
              </button>
            )}

            {tournament.status === 'registration_closed' && (
              <button
                onClick={() => handleAction(
                  () => confirmParticipants(tournamentId),
                  'Skład został zatwierdzony'
                )}
                disabled={actionLoading}
                className="h-10 rounded-[10px] bg-purple-600 px-4 text-[14px] font-semibold text-white hover:bg-purple-700 disabled:opacity-50"
              >
                Zatwierdź skład ({tournament.participant_count} uczestników)
              </button>
            )}

            {tournament.status === 'participants_confirmed' && (
              <button
                onClick={() => handleAction(
                  () => generateBracket(tournamentId),
                  'Drabinka została wygenerowana'
                )}
                disabled={actionLoading}
                className="h-10 rounded-[10px] bg-yellow-600 px-4 text-[14px] font-semibold text-white hover:bg-yellow-700 disabled:opacity-50"
              >
                Wygeneruj drabinkę
              </button>
            )}

            {tournament.status === 'bracket_ready' && (
              <button
                onClick={() => handleAction(
                  () => startTournament(tournamentId),
                  'Turniej został rozpoczęty'
                )}
                disabled={actionLoading}
                className="h-10 rounded-[10px] bg-[#4CAF50] px-4 text-[14px] font-semibold text-white hover:bg-[#43A047] disabled:opacity-50"
              >
                Rozpocznij turniej
              </button>
            )}

            {tournament.status === 'in_progress' && (
              <button
                onClick={() => handleAction(
                  () => finishTournament(tournamentId),
                  'Turniej został zakończony'
                )}
                disabled={actionLoading}
                className="h-10 rounded-[10px] bg-blue-600 px-4 text-[14px] font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Zakończ turniej
              </button>
            )}

            {tournament.status !== 'finished' && (
              <button
                onClick={() => {
                  const reason = prompt('Podaj powód odwołania turnieju:');
                  if (reason) {
                    handleAction(
                      () => cancelTournament(tournamentId, reason),
                      'Turniej został odwołany'
                    );
                  }
                }}
                disabled={actionLoading}
                className="h-10 rounded-[10px] bg-red-600 px-4 text-[14px] font-semibold text-white hover:bg-red-700 disabled:opacity-50"
              >
                Anuluj turniej
              </button>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab('info')}
            className={`pb-3 text-[14px] font-semibold border-b-2 transition-colors ${
              activeTab === 'info'
                ? 'border-[#4CAF50] text-[#4CAF50]'
                : 'border-transparent text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            Informacje
          </button>
          <button
            onClick={() => setActiveTab('participants')}
            className={`pb-3 text-[14px] font-semibold border-b-2 transition-colors ${
              activeTab === 'participants'
                ? 'border-[#4CAF50] text-[#4CAF50]'
                : 'border-transparent text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            Uczestnicy ({tournament.participant_count})
          </button>
          {bracket && (
            <button
              onClick={() => setActiveTab('bracket')}
              className={`pb-3 text-[14px] font-semibold border-b-2 transition-colors ${
                activeTab === 'bracket'
                  ? 'border-[#4CAF50] text-[#4CAF50]'
                  : 'border-transparent text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              Drabinka
            </button>
          )}
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'info' && (
        <div className="rounded-[16px] border border-slate-200 bg-white p-6">
          <div className="space-y-4">
            <div>
              <h3 className="text-[14px] font-semibold text-[#6B7280]">Opis</h3>
              <p className="mt-1 text-[16px] text-[#111827]">{tournament.description || 'Brak opisu'}</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3 className="text-[14px] font-semibold text-[#6B7280]">Typ turnieju</h3>
                <p className="mt-1 text-[16px] text-[#111827]">
                  {tournament.tournament_type === 'single_elimination' ? 'Puchar' : 'Liga'}
                </p>
              </div>

              <div>
                <h3 className="text-[14px] font-semibold text-[#6B7280]">Format</h3>
                <p className="mt-1 text-[16px] text-[#111827]">
                  {tournament.match_format === 'singles' ? 'Singiel' : 'Debl'}
                </p>
              </div>

              <div>
                <h3 className="text-[14px] font-semibold text-[#6B7280]">Data rozpoczęcia</h3>
                <p className="mt-1 text-[16px] text-[#111827]">
                  {new Date(tournament.start_date).toLocaleString('pl-PL')}
                </p>
              </div>

              <div>
                <h3 className="text-[14px] font-semibold text-[#6B7280]">Data zakończenia</h3>
                <p className="mt-1 text-[16px] text-[#111827]">
                  {new Date(tournament.end_date).toLocaleString('pl-PL')}
                </p>
              </div>

              {tournament.registration_deadline && (
                <div>
                  <h3 className="text-[14px] font-semibold text-[#6B7280]">Termin zapisów</h3>
                  <p className="mt-1 text-[16px] text-[#111827]">
                    {new Date(tournament.registration_deadline).toLocaleString('pl-PL')}
                  </p>
                </div>
              )}

              {tournament.facility && (
                <div>
                  <h3 className="text-[14px] font-semibold text-[#6B7280]">Obiekt</h3>
                  <p className="mt-1 text-[16px] text-[#111827]">{tournament.facility.name}</p>
                </div>
              )}

              <div>
                <h3 className="text-[14px] font-semibold text-[#6B7280]">Ranga</h3>
                <p className="mt-1 text-[16px] text-[#111827]">{'⭐'.repeat(tournament.rank)}</p>
              </div>

              <div>
                <h3 className="text-[14px] font-semibold text-[#6B7280]">Organizator</h3>
                <p className="mt-1 text-[16px] text-[#111827]">{tournament.created_by.username}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'participants' && (
        <div className="rounded-[16px] border border-slate-200 bg-white p-6">
          <div className="space-y-3">
            {tournament.participants.map((participant, index) => (
              <div
                key={participant.id}
                className="flex items-center justify-between rounded-[10px] border border-slate-200 p-4"
              >
                <div className="flex items-center gap-3">
                  <span className="text-[18px] font-bold text-[#6B7280]">#{index + 1}</span>
                  <div>
                    <p className="text-[16px] font-semibold text-[#111827]">{participant.display_name}</p>
                    {participant.seed && (
                      <p className="text-[13px] text-[#6B7280]">Rozstawienie: {participant.seed}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {participant.status === 'confirmed' && (
                    <span className="text-[13px] font-semibold text-green-600">Potwierdzony</span>
                  )}
                  {participant.status === 'pending' && (
                    <span className="text-[13px] font-semibold text-yellow-600">Oczekuje</span>
                  )}
                  {participant.status === 'winner' && (
                    <span className="text-[16px]">🏆</span>
                  )}
                </div>
              </div>
            ))}

            {tournament.participants.length === 0 && (
              <p className="py-8 text-center text-[14px] text-[#6B7280]">
                Brak uczestników
              </p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'bracket' && bracket && (
        <div className="rounded-[16px] border border-slate-200 bg-white p-6">
          {/* Report Result Modal */}
          {selectedMatch && (
            <ReportMatchResultModal
              isOpen={showResultModal}
              onClose={() => {
                setShowResultModal(false);
                setSelectedMatch(null);
              }}
              onSuccess={() => {
                loadTournament();
                setShowResultModal(false);
                setSelectedMatch(null);
              }}
              matchId={selectedMatch.id}
              player1={selectedMatch.player1 || 'TBD'}
              player2={selectedMatch.player2 || 'TBD'}
            />
          )}

          <div className="overflow-x-auto">
            <div className="space-y-6">
              {Object.entries(
                bracket.bracket.reduce((acc, match) => {
                  if (!acc[match.round]) acc[match.round] = [];
                  acc[match.round].push(match);
                  return acc;
                }, {} as Record<number, typeof bracket.bracket>)
              ).map(([round, matches]) => (
                <div key={round}>
                  <h3 className="mb-3 text-[16px] font-bold text-[#111827]">
                    {round === '1' && 'Runda 1'}
                    {round === '2' && 'Runda 2'}
                    {round === '3' && 'Ćwierćfinały'}
                    {round === '4' && 'Półfinały'}
                    {round === '5' && 'Finał'}
                  </h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {matches.map((match) => (
                      <div
                        key={match.id}
                        className="rounded-[10px] border border-slate-200 p-4"
                      >
                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-[12px] font-semibold text-[#6B7280]">
                            Mecz {match.position}
                          </span>
                          {isManager && match.status !== 'completed' && match.player1 && match.player2 && (
                            <button
                              onClick={() => {
                                setSelectedMatch(match);
                                setShowResultModal(true);
                              }}
                              className="text-[12px] font-semibold text-[#4CAF50] hover:text-[#43A047]"
                            >
                              Raportuj wynik
                            </button>
                          )}
                        </div>
                        <div className="space-y-2">
                          <div className={`flex items-center justify-between ${match.winner === match.player1 ? 'font-bold text-green-600' : ''}`}>
                            <span className="text-[14px]">{match.player1 || 'TBD'}</span>
                            {match.sets[0] && <span className="text-[14px]">{match.sets[0].p1}</span>}
                          </div>
                          <div className={`flex items-center justify-between ${match.winner === match.player2 ? 'font-bold text-green-600' : ''}`}>
                            <span className="text-[14px]">{match.player2 || 'TBD'}</span>
                            {match.sets[0] && <span className="text-[14px]">{match.sets[0].p2}</span>}
                          </div>
                        </div>
                        {match.status === 'completed' && match.winner && (
                          <div className="mt-2 pt-2 border-t border-slate-200">
                            <div className="text-[12px] font-semibold text-green-600">
                              🏆 {match.winner}
                            </div>
                            {match.sets.length > 0 && (
                              <div className="mt-1 text-[11px] text-[#6B7280]">
                                {match.sets.map((set, i) => `${set.p1}-${set.p2}`).join(', ')}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
