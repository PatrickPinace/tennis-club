/**
 * Match Result Modal Component
 * Modal for entering/updating match results (sets and status)
 */

import { useState } from 'react';
import Modal from '../ui/Modal';
import { updateMatchResult } from '../../lib/api/matches';
import type { MatchListItem, MatchStatus } from '../../types/match';

interface MatchResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  match: MatchListItem | null;
  onSuccess: () => void;
}

export default function MatchResultModal({ isOpen, onClose, match, onSuccess }: MatchResultModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize form state
  const [status, setStatus] = useState<MatchStatus>('completed');
  const [set1p1, setSet1p1] = useState<number>(match?.sets[0]?.p1 || 0);
  const [set1p2, setSet1p2] = useState<number>(match?.sets[0]?.p2 || 0);
  const [set2p1, setSet2p1] = useState<number>(match?.sets[1]?.p1 || 0);
  const [set2p2, setSet2p2] = useState<number>(match?.sets[1]?.p2 || 0);
  const [set3p1, setSet3p1] = useState<number | null>(match?.sets[2]?.p1 || null);
  const [set3p2, setSet3p2] = useState<number | null>(match?.sets[2]?.p2 || null);

  if (!match) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await updateMatchResult(match.id, {
        status,
        set1_p1: set1p1,
        set1_p2: set1p2,
        set2_p1: set2p1,
        set2_p2: set2p2,
        set3_p1: set3p1,
        set3_p2: set3p2
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      console.error('Failed to update match:', err);
      setError(err?.body?.error || 'Nie udało się zaktualizować wyniku meczu');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Wprowadź wynik meczu" size="md">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Match info */}
        <div className="rounded-[10px] bg-slate-50 p-4">
          <p className="text-[14px] font-semibold text-[#111827]">
            vs {match.opponent}
          </p>
          <p className="mt-1 text-[13px] text-[#6B7280]">
            {new Date(match.date).toLocaleDateString('pl-PL', {
              day: 'numeric',
              month: 'long',
              year: 'numeric'
            })}
            {match.court && ` • ${match.court.name}`}
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-[10px] border border-red-200 bg-red-50 p-3">
            <p className="text-[13px] font-medium text-red-800">{error}</p>
          </div>
        )}

        {/* Status */}
        <div>
          <label className="mb-2 block text-[14px] font-semibold text-[#111827]">
            Status meczu
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as MatchStatus)}
            className="h-12 w-full rounded-[10px] border border-slate-200 px-4 text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
          >
            <option value="completed">Zakończony</option>
            <option value="in_progress">W trakcie</option>
            <option value="scheduled">Zaplanowany</option>
            <option value="cancelled">Anulowany</option>
          </select>
        </div>

        {/* Sets */}
        {status === 'completed' && (
          <div className="space-y-4">
            <p className="text-[14px] font-semibold text-[#111827]">Wyniki setów</p>

            {/* Set 1 */}
            <div className="flex items-center gap-4">
              <span className="w-16 text-[13px] font-medium text-[#6B7280]">Set 1:</span>
              <input
                type="number"
                min="0"
                max="7"
                value={set1p1}
                onChange={(e) => setSet1p1(parseInt(e.target.value) || 0)}
                className="h-12 w-20 rounded-[10px] border border-slate-200 px-4 text-center text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
                required
              />
              <span className="text-[#6B7280]">:</span>
              <input
                type="number"
                min="0"
                max="7"
                value={set1p2}
                onChange={(e) => setSet1p2(parseInt(e.target.value) || 0)}
                className="h-12 w-20 rounded-[10px] border border-slate-200 px-4 text-center text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
                required
              />
            </div>

            {/* Set 2 */}
            <div className="flex items-center gap-4">
              <span className="w-16 text-[13px] font-medium text-[#6B7280]">Set 2:</span>
              <input
                type="number"
                min="0"
                max="7"
                value={set2p1}
                onChange={(e) => setSet2p1(parseInt(e.target.value) || 0)}
                className="h-12 w-20 rounded-[10px] border border-slate-200 px-4 text-center text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
                required
              />
              <span className="text-[#6B7280]">:</span>
              <input
                type="number"
                min="0"
                max="7"
                value={set2p2}
                onChange={(e) => setSet2p2(parseInt(e.target.value) || 0)}
                className="h-12 w-20 rounded-[10px] border border-slate-200 px-4 text-center text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
                required
              />
            </div>

            {/* Set 3 (optional) */}
            <div className="flex items-center gap-4">
              <span className="w-16 text-[13px] font-medium text-[#6B7280]">Set 3:</span>
              <input
                type="number"
                min="0"
                max="7"
                value={set3p1 || ''}
                onChange={(e) => setSet3p1(e.target.value ? parseInt(e.target.value) : null)}
                placeholder="0"
                className="h-12 w-20 rounded-[10px] border border-slate-200 px-4 text-center text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
              />
              <span className="text-[#6B7280]">:</span>
              <input
                type="number"
                min="0"
                max="7"
                value={set3p2 || ''}
                onChange={(e) => setSet3p2(e.target.value ? parseInt(e.target.value) : null)}
                placeholder="0"
                className="h-12 w-20 rounded-[10px] border border-slate-200 px-4 text-center text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
              />
              <span className="text-[12px] text-[#6B7280]">(opcjonalny)</span>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 border-t border-slate-200 pt-4">
          <button
            type="button"
            onClick={onClose}
            className="h-12 flex-1 rounded-[10px] border border-slate-200 bg-white text-[14px] font-semibold text-[#6B7280] transition-colors hover:bg-slate-50"
          >
            Anuluj
          </button>
          <button
            type="submit"
            disabled={loading}
            className="h-12 flex-1 rounded-[10px] bg-[#4CAF50] text-[14px] font-semibold text-white transition-colors hover:bg-[#43A047] disabled:opacity-50"
          >
            {loading ? 'Zapisywanie...' : 'Zapisz wynik'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
