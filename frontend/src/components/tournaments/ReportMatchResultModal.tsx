/**
 * Report Match Result Modal
 * Form for reporting match results (managers only)
 */

import { useState } from 'react';
import { reportMatchResult } from '../../lib/api/tournaments';
import type { ReportMatchResultPayload } from '../../types/tournament';

interface ReportMatchResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  matchId: number;
  player1: string;
  player2: string;
}

export default function ReportMatchResultModal({
  isOpen,
  onClose,
  onSuccess,
  matchId,
  player1,
  player2
}: ReportMatchResultModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useSet3, setUseSet3] = useState(false);

  const [formData, setFormData] = useState<ReportMatchResultPayload>({
    set1_p1: 0,
    set1_p2: 0,
    set2_p1: 0,
    set2_p2: 0,
    set3_p1: undefined,
    set3_p2: undefined
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload: ReportMatchResultPayload = {
        set1_p1: formData.set1_p1,
        set1_p2: formData.set1_p2,
        set2_p1: formData.set2_p1,
        set2_p2: formData.set2_p2
      };

      if (useSet3) {
        payload.set3_p1 = formData.set3_p1;
        payload.set3_p2 = formData.set3_p2;
      }

      await reportMatchResult(matchId, payload);
      onSuccess();
      onClose();
      // Reset form
      setFormData({
        set1_p1: 0,
        set1_p2: 0,
        set2_p1: 0,
        set2_p2: 0,
        set3_p1: undefined,
        set3_p2: undefined
      });
      setUseSet3(false);
    } catch (err: any) {
      console.error('Failed to report result:', err);
      setError(err?.body?.error || 'Nie udało się raportować wyniku');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-[16px] bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="text-[20px] font-bold text-[#111827]">Raportuj wynik meczu</h2>
          <button
            onClick={onClose}
            className="rounded-[8px] p-2 text-[#6B7280] hover:bg-slate-100"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="rounded-[10px] border border-red-200 bg-red-50 p-4">
              <p className="text-[14px] font-medium text-red-800">{error}</p>
            </div>
          )}

          {/* Players */}
          <div className="space-y-2">
            <div className="flex items-center justify-between rounded-[10px] bg-blue-50 p-3">
              <span className="text-[16px] font-bold text-blue-900">{player1}</span>
            </div>
            <div className="flex items-center justify-between rounded-[10px] bg-red-50 p-3">
              <span className="text-[16px] font-bold text-red-900">{player2}</span>
            </div>
          </div>

          {/* Set 1 */}
          <div>
            <h3 className="mb-2 text-[16px] font-bold text-[#111827]">Set 1 *</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  {player1}
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  max="7"
                  value={formData.set1_p1}
                  onChange={(e) => setFormData({ ...formData, set1_p1: parseInt(e.target.value) || 0 })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[18px] text-center font-bold focus:border-[#4CAF50] focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  {player2}
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  max="7"
                  value={formData.set1_p2}
                  onChange={(e) => setFormData({ ...formData, set1_p2: parseInt(e.target.value) || 0 })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[18px] text-center font-bold focus:border-[#4CAF50] focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Set 2 */}
          <div>
            <h3 className="mb-2 text-[16px] font-bold text-[#111827]">Set 2 *</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  {player1}
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  max="7"
                  value={formData.set2_p1}
                  onChange={(e) => setFormData({ ...formData, set2_p1: parseInt(e.target.value) || 0 })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[18px] text-center font-bold focus:border-[#4CAF50] focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  {player2}
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  max="7"
                  value={formData.set2_p2}
                  onChange={(e) => setFormData({ ...formData, set2_p2: parseInt(e.target.value) || 0 })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[18px] text-center font-bold focus:border-[#4CAF50] focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Set 3 Toggle */}
          <div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={useSet3}
                onChange={(e) => setUseSet3(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-[#4CAF50] focus:ring-[#4CAF50]"
              />
              <span className="text-[14px] font-semibold text-[#111827]">
                Dodaj Set 3 (remis 1-1)
              </span>
            </label>
          </div>

          {/* Set 3 (conditional) */}
          {useSet3 && (
            <div>
              <h3 className="mb-2 text-[16px] font-bold text-[#111827]">Set 3</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                    {player1}
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="7"
                    value={formData.set3_p1 || 0}
                    onChange={(e) => setFormData({ ...formData, set3_p1: parseInt(e.target.value) || 0 })}
                    className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[18px] text-center font-bold focus:border-[#4CAF50] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                    {player2}
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="7"
                    value={formData.set3_p2 || 0}
                    onChange={(e) => setFormData({ ...formData, set3_p2: parseInt(e.target.value) || 0 })}
                    className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[18px] text-center font-bold focus:border-[#4CAF50] focus:outline-none"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 h-10 rounded-[10px] border border-slate-300 text-[14px] font-semibold text-[#111827] hover:bg-slate-50 disabled:opacity-50"
            >
              Anuluj
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 h-10 rounded-[10px] bg-[#4CAF50] text-[14px] font-semibold text-white hover:bg-[#43A047] disabled:opacity-50"
            >
              {loading ? 'Zapisywanie...' : 'Zapisz wynik'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
