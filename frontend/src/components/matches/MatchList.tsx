/**
 * Match List React Component
 * Displays a filterable list of matches with modal support
 */

import { useEffect, useState } from 'react';
import { getMatches } from '../../lib/api/matches';
import MatchResultModal from './MatchResultModal';
import CreateMatchModal from './CreateMatchModal';
import type { MatchListItem, MatchStatus } from '../../types/match';

interface MatchListProps {
  initialStatus?: MatchStatus;
  limit?: number;
  showCreateButton?: boolean;
}

export default function MatchList({ initialStatus, limit = 20, showCreateButton = false }: MatchListProps) {
  const [matches, setMatches] = useState<MatchListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<MatchStatus | 'all'>(initialStatus || 'all');

  // Modal state
  const [selectedMatch, setSelectedMatch] = useState<MatchListItem | null>(null);
  const [showResultModal, setShowResultModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const loadMatches = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = {
        limit,
        ...(selectedStatus !== 'all' && { status: selectedStatus as MatchStatus })
      };
      const response = await getMatches(params);
      setMatches(response.matches);
    } catch (err: any) {
      console.error('Failed to load matches:', err);
      setError(err?.body?.error || 'Nie udało się załadować meczów');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMatches();
  }, [selectedStatus, limit]);

  const handleStatusChange = (status: MatchStatus | 'all') => {
    setSelectedStatus(status);
  };

  const handleMatchClick = (match: MatchListItem) => {
    setSelectedMatch(match);
    setShowResultModal(true);
  };

  const handleModalClose = () => {
    setShowResultModal(false);
    setSelectedMatch(null);
  };

  const handleSuccess = () => {
    loadMatches(); // Reload matches after update
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('pl-PL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  const formatScore = (sets: { p1: number; p2: number }[]) => {
    return sets.map(set => `${set.p1}:${set.p2}`).join(' ');
  };

  const getStatusBadge = (status: MatchStatus) => {
    const config = {
      scheduled: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Zaplanowany' },
      in_progress: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'W trakcie' },
      completed: { bg: 'bg-green-100', text: 'text-green-800', label: 'Zakończony' },
      cancelled: { bg: 'bg-red-100', text: 'text-red-800', label: 'Anulowany' }
    };
    const c = config[status];
    return (
      <span className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-medium ${c.bg} ${c.text}`}>
        {c.label}
      </span>
    );
  };

  const getResultColor = (result: 'won' | 'lost' | null) => {
    if (result === 'won') return 'text-[#4CAF50]';
    if (result === 'lost') return 'text-red-600';
    return 'text-[#6B7280]';
  };

  const getResultText = (result: 'won' | 'lost' | null) => {
    if (result === 'won') return 'Wygrana';
    if (result === 'lost') return 'Przegrana';
    return 'Brak wyniku';
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
          onClick={loadMatches}
          className="mt-4 h-10 rounded-[10px] bg-red-600 px-4 text-[14px] font-semibold text-white hover:bg-red-700"
        >
          Spróbuj ponownie
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header with filter tabs and create button */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex gap-2 overflow-x-auto">
          {['all', 'completed', 'scheduled', 'in_progress', 'cancelled'].map((status) => (
            <button
              key={status}
              onClick={() => handleStatusChange(status as MatchStatus | 'all')}
              className={`h-10 rounded-[10px] px-4 text-[14px] font-semibold transition-colors whitespace-nowrap ${
                selectedStatus === status
                  ? 'bg-[#4CAF50] text-white'
                  : 'bg-white text-[#6B7280] border border-slate-200 hover:bg-slate-50'
              }`}
            >
              {status === 'all' && 'Wszystkie'}
              {status === 'completed' && 'Zakończone'}
              {status === 'scheduled' && 'Zaplanowane'}
              {status === 'in_progress' && 'W trakcie'}
              {status === 'cancelled' && 'Anulowane'}
            </button>
          ))}
        </div>

        {showCreateButton && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="h-10 whitespace-nowrap rounded-[10px] bg-[#4CAF50] px-4 text-[14px] font-semibold text-white transition-colors hover:bg-[#43A047]"
          >
            + Dodaj mecz
          </button>
        )}
      </div>

      {/* Matches grid */}
      {matches.length === 0 ? (
        <div className="rounded-[16px] border border-slate-200 bg-white p-12 text-center">
          <p className="text-[16px] font-medium text-[#6B7280]">
            Brak meczów do wyświetlenia
          </p>
          <p className="mt-2 text-[14px] text-[#6B7280]">
            {selectedStatus !== 'all' ? 'Zmień filtr aby zobaczyć więcej meczów' : 'Dodaj swój pierwszy mecz klikając "Dodaj mecz"'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {matches.map((match) => (
            <div
              key={match.id}
              onClick={() => handleMatchClick(match)}
              className="cursor-pointer rounded-[16px] border border-slate-200 bg-white p-6 shadow-[0_1px_2px_rgba(16,24,40,0.04),0_4px_10px_rgba(16,24,40,0.04)] transition-shadow hover:shadow-lg"
            >
              {/* Header */}
              <div className="mb-4 flex items-start justify-between">
                <div>
                  <p className="text-[13px] font-semibold leading-[18px] text-[#6B7280]">
                    {formatDate(match.date)}
                    {match.court && ` • ${match.court.facility}`}
                  </p>
                  <p className="mt-1 text-[11px] font-normal leading-[16px] text-[#6B7280]">
                    {match.is_doubles ? 'Debl' : 'Singiel'}
                    {match.court && ` • ${match.court.surface}`}
                  </p>
                </div>
                {getStatusBadge(match.status)}
              </div>

              {/* Opponent */}
              <h3 className="mb-2 text-[16px] font-bold leading-[22px] tracking-[-0.01em] text-[#111827]">
                vs {match.opponent}
              </h3>

              {/* Result and score */}
              {match.result && (
                <div className="mt-3">
                  <p className={`text-[14px] font-bold leading-[20px] ${getResultColor(match.result)}`}>
                    {getResultText(match.result)}
                  </p>
                  {match.sets.length > 0 && (
                    <p className="mt-1 text-[18px] font-bold leading-[24px] tracking-[-0.01em] text-[#111827]">
                      {formatScore(match.sets)}
                    </p>
                  )}
                </div>
              )}

              {/* Court */}
              {match.court && (
                <p className="mt-3 text-[13px] font-medium leading-[18px] text-[#6B7280]">
                  {match.court.name}
                </p>
              )}

              {/* Click hint */}
              {match.status !== 'completed' && (
                <p className="mt-3 text-[12px] font-medium text-[#4CAF50]">
                  Kliknij aby wprowadzić wynik →
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      <MatchResultModal
        isOpen={showResultModal}
        onClose={handleModalClose}
        match={selectedMatch}
        onSuccess={handleSuccess}
      />

      <CreateMatchModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleSuccess}
      />
    </div>
  );
}
