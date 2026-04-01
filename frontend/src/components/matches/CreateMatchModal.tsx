/**
 * Create Match Modal Component
 * Modal for creating a new match
 */

import { useState, useEffect } from 'react';
import Modal from '../ui/Modal';
import { createMatch } from '../../lib/api/matches';

interface CreateMatchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
}

interface Court {
  id: number;
  number: number;
  surface: string;
  facility: {
    id: number;
    name: string;
  };
}

export default function CreateMatchModal({ isOpen, onClose, onSuccess }: CreateMatchModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [courts, setCourts] = useState<Court[]>([]);

  // Form state
  const [player2Id, setPlayer2Id] = useState<number | ''>('');
  const [matchDate, setMatchDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [courtId, setCourtId] = useState<number | ''>('');
  const [description, setDescription] = useState('Mecz towarzyski');

  // Load users and courts when modal opens
  useEffect(() => {
    if (isOpen) {
      loadUsers();
      loadCourts();
    }
  }, [isOpen]);

  const loadUsers = async () => {
    try {
      // For now, we'll use a simple fetch to get users
      // You might want to create a dedicated API endpoint for this
      const response = await fetch('http://localhost:8000/api/users/', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users || []);
      }
    } catch (err) {
      console.error('Failed to load users:', err);
    }
  };

  const loadCourts = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/courts/', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setCourts(data || []);
      }
    } catch (err) {
      console.error('Failed to load courts:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!player2Id) {
      setError('Wybierz przeciwnika');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await createMatch({
        player2_id: Number(player2Id),
        match_date: matchDate,
        ...(courtId && { court_id: Number(courtId) }),
        description
      });

      onSuccess();
      onClose();

      // Reset form
      setPlayer2Id('');
      setMatchDate(new Date().toISOString().split('T')[0]);
      setCourtId('');
      setDescription('Mecz towarzyski');
    } catch (err: any) {
      console.error('Failed to create match:', err);
      setError(err?.body?.error || 'Nie udało się utworzyć meczu');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Dodaj nowy mecz" size="md">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Error */}
        {error && (
          <div className="rounded-[10px] border border-red-200 bg-red-50 p-3">
            <p className="text-[13px] font-medium text-red-800">{error}</p>
          </div>
        )}

        {/* Opponent */}
        <div>
          <label className="mb-2 block text-[14px] font-semibold text-[#111827]">
            Przeciwnik *
          </label>
          <select
            value={player2Id}
            onChange={(e) => setPlayer2Id(e.target.value ? Number(e.target.value) : '')}
            className="h-12 w-full rounded-[10px] border border-slate-200 px-4 text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
            required
          >
            <option value="">Wybierz przeciwnika</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.first_name && user.last_name
                  ? `${user.first_name} ${user.last_name} (${user.username})`
                  : user.username}
              </option>
            ))}
          </select>
          {users.length === 0 && (
            <p className="mt-1 text-[12px] text-[#6B7280]">Ładowanie użytkowników...</p>
          )}
        </div>

        {/* Date */}
        <div>
          <label className="mb-2 block text-[14px] font-semibold text-[#111827]">
            Data meczu *
          </label>
          <input
            type="date"
            value={matchDate}
            onChange={(e) => setMatchDate(e.target.value)}
            className="h-12 w-full rounded-[10px] border border-slate-200 px-4 text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
            required
          />
        </div>

        {/* Court (optional) */}
        <div>
          <label className="mb-2 block text-[14px] font-semibold text-[#111827]">
            Kort (opcjonalnie)
          </label>
          <select
            value={courtId}
            onChange={(e) => setCourtId(e.target.value ? Number(e.target.value) : '')}
            className="h-12 w-full rounded-[10px] border border-slate-200 px-4 text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
          >
            <option value="">Brak</option>
            {courts.map((court) => (
              <option key={court.id} value={court.id}>
                Kort {court.number} - {court.facility.name} ({court.surface})
              </option>
            ))}
          </select>
        </div>

        {/* Description */}
        <div>
          <label className="mb-2 block text-[14px] font-semibold text-[#111827]">
            Opis
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Mecz towarzyski"
            className="h-12 w-full rounded-[10px] border border-slate-200 px-4 text-[14px] text-[#111827] focus:border-[#4CAF50] focus:outline-none focus:ring-2 focus:ring-[#4CAF50]/20"
          />
        </div>

        {/* Info */}
        <div className="rounded-[10px] bg-blue-50 p-3">
          <p className="text-[13px] text-blue-800">
            💡 Po utworzeniu meczu będziesz mógł wprowadzić wyniki klikając na kartę meczu.
          </p>
        </div>

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
            {loading ? 'Tworzenie...' : 'Utwórz mecz'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
