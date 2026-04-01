/**
 * Create Tournament Modal Component
 * Form for creating new tournaments (managers only)
 */

import { useState, useEffect } from 'react';
import { createTournament } from '../../lib/api/tournaments';
import type { CreateTournamentPayload, TournamentType, TournamentFormat, TournamentVisibility, RegistrationMode } from '../../types/tournament';

interface Facility {
  id: number;
  name: string;
}

interface CreateTournamentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CreateTournamentModal({ isOpen, onClose, onSuccess }: CreateTournamentModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);

  const [formData, setFormData] = useState<CreateTournamentPayload>({
    name: '',
    description: '',
    tournament_type: 'single_elimination',
    match_format: 'singles',
    visibility: 'public',
    registration_mode: 'auto',
    start_date: '',
    end_date: '',
    registration_deadline: '',
    min_participants: 4,
    max_participants: 16,
    facility_id: 0,
    rank: 1,
    sets_to_win: 2,
    games_per_set: 6,
    use_seeding: true,
    third_place_match: false
  });

  // Load facilities
  useEffect(() => {
    const loadFacilities = async () => {
      try {
        const response = await fetch('/api/facilities/');
        if (response.ok) {
          const data = await response.json();
          setFacilities(data.facilities || []);
          if (data.facilities && data.facilities.length > 0) {
            setFormData(prev => ({ ...prev, facility_id: data.facilities[0].id }));
          }
        }
      } catch (err) {
        console.error('Failed to load facilities:', err);
      }
    };
    if (isOpen) {
      loadFacilities();
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await createTournament(formData);
      onSuccess();
      onClose();
      // Reset form
      setFormData({
        name: '',
        description: '',
        tournament_type: 'single_elimination',
        match_format: 'singles',
        visibility: 'public',
        registration_mode: 'auto',
        start_date: '',
        end_date: '',
        registration_deadline: '',
        min_participants: 4,
        max_participants: 16,
        facility_id: facilities[0]?.id || 0,
        rank: 1,
        sets_to_win: 2,
        games_per_set: 6,
        use_seeding: true,
        third_place_match: false
      });
    } catch (err: any) {
      console.error('Failed to create tournament:', err);
      setError(err?.body?.error || 'Nie udało się utworzyć turnieju');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-[16px] bg-white shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
          <h2 className="text-[20px] font-bold text-[#111827]">Utwórz nowy turniej</h2>
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

          {/* Basic Info */}
          <div className="space-y-4">
            <h3 className="text-[16px] font-bold text-[#111827]">Podstawowe informacje</h3>

            <div>
              <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                Nazwa turnieju *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                placeholder="np. Turniej Klubowy - Kwiecień 2026"
              />
            </div>

            <div>
              <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                Opis
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                placeholder="Krótki opis turnieju..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Typ turnieju *
                </label>
                <select
                  value={formData.tournament_type}
                  onChange={(e) => setFormData({ ...formData, tournament_type: e.target.value as TournamentType })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                >
                  <option value="single_elimination">Puchar (Single Elimination)</option>
                  <option value="round_robin">Liga (Round Robin)</option>
                </select>
              </div>

              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Format gry *
                </label>
                <select
                  value={formData.match_format}
                  onChange={(e) => setFormData({ ...formData, match_format: e.target.value as TournamentFormat })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                >
                  <option value="singles">Singiel</option>
                  <option value="doubles">Debel</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Widoczność *
                </label>
                <select
                  value={formData.visibility}
                  onChange={(e) => setFormData({ ...formData, visibility: e.target.value as TournamentVisibility })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                >
                  <option value="public">Publiczny</option>
                  <option value="private">Prywatny</option>
                  <option value="invite_only">Tylko zaproszenia</option>
                </select>
              </div>

              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Tryb zapisów *
                </label>
                <select
                  value={formData.registration_mode}
                  onChange={(e) => setFormData({ ...formData, registration_mode: e.target.value as RegistrationMode })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                >
                  <option value="auto">Automatyczne zatwierdzenie</option>
                  <option value="approval_required">Wymaga zatwierdzenia</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                Obiekt *
              </label>
              <select
                value={formData.facility_id}
                onChange={(e) => setFormData({ ...formData, facility_id: parseInt(e.target.value) })}
                className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
              >
                {facilities.map(facility => (
                  <option key={facility.id} value={facility.id}>{facility.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Dates */}
          <div className="space-y-4">
            <h3 className="text-[16px] font-bold text-[#111827]">Terminy</h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Data rozpoczęcia *
                </label>
                <input
                  type="datetime-local"
                  required
                  value={formData.start_date}
                  onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Data zakończenia *
                </label>
                <input
                  type="datetime-local"
                  required
                  value={formData.end_date}
                  onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                Termin zapisów *
              </label>
              <input
                type="datetime-local"
                required
                value={formData.registration_deadline}
                onChange={(e) => setFormData({ ...formData, registration_deadline: e.target.value })}
                className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
              />
            </div>
          </div>

          {/* Participants */}
          <div className="space-y-4">
            <h3 className="text-[16px] font-bold text-[#111827]">Uczestnicy</h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Min. uczestników *
                </label>
                <input
                  type="number"
                  required
                  min="2"
                  value={formData.min_participants}
                  onChange={(e) => setFormData({ ...formData, min_participants: parseInt(e.target.value) })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Max. uczestników *
                </label>
                <input
                  type="number"
                  required
                  min="2"
                  value={formData.max_participants}
                  onChange={(e) => setFormData({ ...formData, max_participants: parseInt(e.target.value) })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                Ranga turnieju *
              </label>
              <select
                value={formData.rank}
                onChange={(e) => setFormData({ ...formData, rank: parseInt(e.target.value) })}
                className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
              >
                <option value="1">⭐ (1)</option>
                <option value="2">⭐⭐ (2)</option>
                <option value="3">⭐⭐⭐ (3)</option>
                <option value="4">⭐⭐⭐⭐ (4)</option>
                <option value="5">⭐⭐⭐⭐⭐ (5)</option>
              </select>
            </div>
          </div>

          {/* Rules */}
          <div className="space-y-4">
            <h3 className="text-[16px] font-bold text-[#111827]">Zasady</h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Sety do wygranej
                </label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={formData.sets_to_win}
                  onChange={(e) => setFormData({ ...formData, sets_to_win: parseInt(e.target.value) })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-[14px] font-semibold text-[#111827] mb-2">
                  Gemów w secie
                </label>
                <input
                  type="number"
                  min="1"
                  value={formData.games_per_set}
                  onChange={(e) => setFormData({ ...formData, games_per_set: parseInt(e.target.value) })}
                  className="w-full rounded-[10px] border border-slate-300 px-4 py-2 text-[14px] focus:border-[#4CAF50] focus:outline-none"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="use_seeding"
                checked={formData.use_seeding}
                onChange={(e) => setFormData({ ...formData, use_seeding: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-[#4CAF50] focus:ring-[#4CAF50]"
              />
              <label htmlFor="use_seeding" className="text-[14px] text-[#111827]">
                Użyj rozstawienia (seeding)
              </label>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="third_place_match"
                checked={formData.third_place_match}
                onChange={(e) => setFormData({ ...formData, third_place_match: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-[#4CAF50] focus:ring-[#4CAF50]"
              />
              <label htmlFor="third_place_match" className="text-[14px] text-[#111827]">
                Mecz o 3. miejsce
              </label>
            </div>
          </div>

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
              {loading ? 'Tworzenie...' : 'Utwórz turniej'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
