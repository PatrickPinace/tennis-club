/**
 * Tournament List React Component
 * Displays a filterable list of tournaments
 */

import { useEffect, useState } from 'react';
import { getTournaments, registerForTournament, withdrawFromTournament, joinTournament } from '../../lib/api/tournaments';
import type { TournamentListItem, TournamentStatus } from '../../types/tournament';
import CreateTournamentModal from './CreateTournamentModal';

interface TournamentListProps {
  initialStatus?: TournamentStatus;
  initialMyOnly?: boolean;
  limit?: number;
  isStaff?: boolean;
}

export default function TournamentList({ initialStatus, initialMyOnly = false, limit = 20, isStaff = false }: TournamentListProps) {
  const [tournaments, setTournaments] = useState<TournamentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<TournamentStatus | 'all'>(initialStatus || 'all');
  const [myOnly, setMyOnly] = useState(initialMyOnly);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const loadTournaments = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        limit,
        ...(selectedStatus !== 'all' && { status: selectedStatus as TournamentStatus }),
        ...(myOnly && { my: true })
      };
      const response = await getTournaments(params);
      setTournaments(response.tournaments);
    } catch (err: any) {
      console.error('Failed to load tournaments:', err);
      setError(err?.body?.error || 'Nie udało się załadować turniejów');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTournaments();
  }, [selectedStatus, myOnly, limit]);

  const handleStatusChange = (status: TournamentStatus | 'all') => {
    setSelectedStatus(status);
  };

  const handleRegister = async (tournamentId: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click
    try {
      await joinTournament(tournamentId);
      await loadTournaments(); // Reload to show updated status
    } catch (err: any) {
      alert(err?.body?.error || 'Nie udało się zapisać do turnieju');
    }
  };

  const handleWithdraw = async (tournamentId: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click
    if (!confirm('Czy na pewno chcesz zrezygnować z udziału w turnieju?')) {
      return;
    }
    try {
      await withdrawFromTournament(tournamentId);
      await loadTournaments(); // Reload to show updated status
    } catch (err: any) {
      alert(err?.body?.error || 'Nie udało się zrezygnować z turnieju');
    }
  };

  const formatDateRange = (startDate: string, endDate: string) => {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const startDay = start.getDate();
    const endDay = end.getDate();
    const startMonth = start.toLocaleDateString('pl-PL', { month: 'short' });
    const endMonth = end.toLocaleDateString('pl-PL', { month: 'short' });

    if (startMonth === endMonth) {
      return `${startDay}-${endDay} ${startMonth}`;
    }
    return `${startDay} ${startMonth} - ${endDay} ${endMonth}`;
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
      <span className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}>
        {c.label}
      </span>
    );
  };

  const handleCardClick = (tournamentId: number) => {
    window.location.href = `/app/tournaments/${tournamentId}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#4CAF50] border-t-transparent"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-[16px] border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-[14px] font-medium text-red-800">{error}</p>
        <button
          onClick={loadTournaments}
          className="mt-4 h-10 rounded-[10px] bg-red-600 px-4 text-[14px] font-semibold text-white hover:bg-red-700"
        >
          Spróbuj ponownie
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header with Create Button */}
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-[24px] font-bold text-[#111827]">Turnieje</h1>
        {isStaff && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="h-10 rounded-[10px] bg-[#4CAF50] px-4 text-[14px] font-semibold text-white hover:bg-[#43A047]"
          >
            + Utwórz turniej
          </button>
        )}
      </div>

      {/* Create Tournament Modal */}
      <CreateTournamentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={loadTournaments}
      />

      {/* Filter tabs */}
      <div className="mb-6 flex gap-2 overflow-x-auto">
        <button
          onClick={() => setMyOnly(!myOnly)}
          className={`h-10 rounded-[10px] px-4 text-[14px] font-semibold transition-colors whitespace-nowrap ${
            myOnly
              ? 'bg-[#4CAF50] text-white'
              : 'bg-white text-[#6B7280] border border-slate-200 hover:bg-slate-50'
          }`}
        >
          Moje turnieje
        </button>
        <div className="h-10 w-px bg-slate-300"></div>
        {['all', 'registration_open', 'in_progress', 'bracket_ready', 'finished'].map((status) => (
          <button
            key={status}
            onClick={() => handleStatusChange(status as TournamentStatus | 'all')}
            className={`h-10 rounded-[10px] px-4 text-[14px] font-semibold transition-colors whitespace-nowrap ${
              selectedStatus === status
                ? 'bg-[#4CAF50] text-white'
                : 'bg-white text-[#6B7280] border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {status === 'all' && 'Wszystkie'}
            {status === 'registration_open' && 'Zapisy'}
            {status === 'in_progress' && 'W trakcie'}
            {status === 'bracket_ready' && 'Gotowe'}
            {status === 'finished' && 'Zakończone'}
          </button>
        ))}
      </div>

      {/* Tournaments grid */}
      {tournaments.length === 0 ? (
        <div className="rounded-[16px] border border-slate-200 bg-white p-12 text-center">
          <p className="text-[16px] font-medium text-[#6B7280]">
            Brak turniejów do wyświetlenia
          </p>
          <p className="mt-2 text-[14px] text-[#6B7280]">
            {myOnly ? 'Nie uczestniczysz w żadnych turniejach' : 'Zmień filtr aby zobaczyć więcej turniejów'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {tournaments.map((tournament) => {
            const isRegistrationOpen = tournament.status === 'registration_open';
            const isFull = tournament.participant_count >= tournament.max_participants;
            const typeLabel = tournament.tournament_type === 'round_robin' ? 'Liga' : 'Puchar';
            const formatLabel = tournament.match_format === 'singles' ? 'Singiel' : 'Debel';

            return (
              <div
                key={tournament.id}
                onClick={() => handleCardClick(tournament.id)}
                className="cursor-pointer rounded-[16px] border border-slate-200 bg-white p-6 shadow-[0_1px_2px_rgba(16,24,40,0.04),0_4px_10px_rgba(16,24,40,0.04)] transition-shadow hover:shadow-lg"
              >
                {/* Header */}
                <div className="mb-4 flex items-start justify-between">
                  <div className="mr-4 flex-1">
                    <h3 className="mb-1 text-[18px] font-bold leading-[24px] tracking-[-0.01em] text-[#111827]">
                      {tournament.name}
                    </h3>
                    <p className="text-[13px] font-semibold leading-[18px] text-[#6B7280]">
                      {formatDateRange(tournament.start_date, tournament.end_date)}
                    </p>
                  </div>
                  {getStatusBadge(tournament.status)}
                </div>

                {/* Info */}
                <div className="mb-4 space-y-2">
                  <div className="flex items-center gap-2 text-[13px] text-[#6B7280]">
                    <span className="font-semibold">{typeLabel}</span>
                    <span>•</span>
                    <span className="font-semibold">{formatLabel}</span>
                    {tournament.facility && (
                      <>
                        <span>•</span>
                        <span>{tournament.facility.name}</span>
                      </>
                    )}
                  </div>

                  <div className="flex items-center gap-2 text-[13px] text-[#6B7280]">
                    <span>Ranga:</span>
                    <span className="font-semibold">{'⭐'.repeat(tournament.rank)}</span>
                  </div>

                  <div className="text-[13px] text-[#6B7280]">
                    <span>Uczestnicy: </span>
                    <span className="font-semibold text-[#111827]">
                      {tournament.participant_count}/{tournament.max_participants}
                    </span>
                    {isFull && <span className="ml-2 font-semibold text-red-600">(Pełny)</span>}
                  </div>
                </div>

                {/* User participation */}
                {tournament.is_participant && tournament.user_participant && (
                  <div className="mt-4 rounded-[10px] border border-[#4CAF50]/20 bg-[#4CAF50]/10 p-3">
                    <p className="text-[13px] font-semibold text-[#4CAF50]">Jesteś uczestnikiem</p>
                    {tournament.user_participant.seed && (
                      <p className="mt-1 text-[12px] text-[#6B7280]">
                        Rozstawienie: {tournament.user_participant.seed}
                      </p>
                    )}
                    {tournament.status === 'registration_open' && (
                      <button
                        onClick={(e) => handleWithdraw(tournament.id, e)}
                        className="mt-2 h-8 w-full rounded-[8px] bg-red-600 text-[12px] font-semibold text-white hover:bg-red-700"
                      >
                        Zrezygnuj
                      </button>
                    )}
                  </div>
                )}

                {/* Registration */}
                {!tournament.is_participant && isRegistrationOpen && !isFull && (
                  <div className="mt-4">
                    <button
                      onClick={(e) => handleRegister(tournament.id, e)}
                      className="h-10 w-full rounded-[10px] bg-[#4CAF50] text-[14px] font-semibold text-white transition-colors hover:bg-[#43A047]"
                    >
                      Zapisz się
                    </button>
                  </div>
                )}

                {/* Winner */}
                {tournament.status === 'finished' && tournament.winner && (
                  <div className="mt-4 rounded-[10px] border border-yellow-200 bg-yellow-50 p-3">
                    <p className="text-[13px] font-semibold text-yellow-900">
                      🏆 Zwycięzca: {tournament.winner.display_name}
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
